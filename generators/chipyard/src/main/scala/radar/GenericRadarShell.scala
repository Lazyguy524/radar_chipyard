package chipyard.radar

import chisel3._
import chisel3.util._

import org.chipsalliance.cde.config.{Config, Field, Parameters}

import freechips.rocketchip.diplomacy.{AddressSet, IdRange, LazyModule}
import freechips.rocketchip.interrupts.{IntSourceNode, IntSourcePortSimple}
import freechips.rocketchip.prci.{ClockSinkDomain, ClockSinkParameters}
import freechips.rocketchip.regmapper.{RegField, RegFieldDesc}
import freechips.rocketchip.resources.SimpleDevice
import freechips.rocketchip.subsystem.{BaseSubsystem, FBUS, PBUS}
import freechips.rocketchip.tilelink._

case class GenericRadarSlotParams(
  name: String,
  controlBase: BigInt,
  controlSize: BigInt = 0x1000)

case class GenericRadarMemoryRegion(
  name: String,
  base: BigInt,
  size: BigInt)

case class GenericRadarShellParams(
  slots: Seq[GenericRadarSlotParams] = Seq(
    GenericRadarSlotParams("radar-slot0-preproc", 0x04000000L),
    GenericRadarSlotParams("radar-slot1-cluster", 0x04001000L),
    GenericRadarSlotParams("radar-slot2-detector", 0x04002000L)),
  irqStatusBase: BigInt = 0x04003000L,
  irqStatusSize: BigInt = 0x1000,
  memoryRegions: Seq[GenericRadarMemoryRegion] = Seq(
    GenericRadarMemoryRegion("buf_in",    0x81000000L, 0x00800000L),
    GenericRadarMemoryRegion("buf_mid0",  0x81800000L, 0x00800000L),
    GenericRadarMemoryRegion("buf_mid1",  0x82000000L, 0x00800000L),
    GenericRadarMemoryRegion("buf_out",   0x82800000L, 0x00800000L),
    GenericRadarMemoryRegion("desc_ring", 0x83000000L, 0x00100000L))) {
  require(slots.size == 3, "GenericRadarShell currently reserves exactly 3 accelerator slots")
  require(memoryRegions.size >= 5, "GenericRadarShell requires 5 reserved DDR memory regions")
}

case object GenericRadarShellKey extends Field[Option[GenericRadarShellParams]](None)

class GenericRadarShell(beatBytes: Int, val params: GenericRadarShellParams)(implicit p: Parameters)
  extends ClockSinkDomain(ClockSinkParameters())(p) {
  private val shellDevice = new SimpleDevice("generic-radar-shell", Seq("ucbbar,generic-radar-shell0"))
  private val irqDevice = new SimpleDevice("generic-radar-irq-status", Seq("ucbbar,generic-radar-irq-status0"))

  val slotControlNodes = params.slots.map { slot =>
    val device = new SimpleDevice(slot.name, Seq(s"ucbbar,${slot.name}"))
    TLRegisterNode(
      address = Seq(AddressSet(slot.controlBase, slot.controlSize - 1)),
      device = device,
      deviceKey = "reg/control",
      beatBytes = beatBytes)
  }

  val irqStatusNode = TLRegisterNode(
    address = Seq(AddressSet(params.irqStatusBase, params.irqStatusSize - 1)),
    device = irqDevice,
    deviceKey = "reg/control",
    beatBytes = beatBytes)

  val dmaNodes = params.slots.map { slot =>
    TLClientNode(Seq(TLMasterPortParameters.v1(Seq(TLMasterParameters.v1(
      name = s"${slot.name}-dma",
      sourceId = IdRange(0, 1)
    )))))
  }

  val intNode = IntSourceNode(IntSourcePortSimple(num = params.slots.size, resources = shellDevice.int))

  override lazy val module = new Impl {
    withClockAndReset(clock, reset) {
    val slotCount = params.slots.size
    val version = 1.U(32.W)
    val slotCountReg = slotCount.U(32.W)

    val irqPendingVec = Wire(Vec(slotCount, Bool()))
    val busyVec = Wire(Vec(slotCount, Bool()))
    val doneVec = Wire(Vec(slotCount, Bool()))
    val irqEnableVec = Wire(Vec(slotCount, Bool()))
    val errorVec = Wire(Vec(slotCount, Bool()))

    val (intOut, _) = intNode.out(0)

    for ((((slot, node), dmaNode), idx) <- params.slots.zip(slotControlNodes).zip(dmaNodes).zipWithIndex) {
      val (mem, edge) = dmaNode.out(0)
      val dmaBeatBytes = edge.bundle.dataBits / 8
      val dmaLgSize = log2Ceil(dmaBeatBytes).U
      val sIdle :: sGetReq :: sGetResp :: sPutReq :: sPutResp :: sDone :: Nil = Enum(6)

      val ctrl = RegInit(0.U(32.W))
      val srcLo = RegInit(0.U(32.W))
      val srcHi = RegInit(0.U(32.W))
      val dstLo = RegInit(0.U(32.W))
      val dstHi = RegInit(0.U(32.W))
      val lenReg = RegInit(0.U(32.W))
      val cfg0 = RegInit(0.U(32.W))
      val cfg1 = RegInit(0.U(32.W))
      val cfg2 = RegInit(0.U(32.W))
      val cfg3 = RegInit(0.U(32.W))
      val irqEnable = RegInit(false.B)
      val irqPending = RegInit(false.B)
      val busy = RegInit(false.B)
      val done = RegInit(false.B)
      val error = RegInit(false.B)
      val copiedBeats = RegInit(0.U(32.W))

      val dmaState = RegInit(sIdle)
      val currentSrc = Reg(UInt(edge.bundle.addressBits.W))
      val currentDst = Reg(UInt(edge.bundle.addressBits.W))
      val bytesLeft = Reg(UInt(32.W))
      val readData = Reg(UInt(edge.bundle.dataBits.W))

      val alignedLenMask = ~(dmaBeatBytes - 1).U(32.W)
      val alignedLen = lenReg & alignedLenMask
      val dmaEnabled = cfg0(0)
      val startRequested = ctrl(0)

      mem.a.valid := dmaState === sGetReq || dmaState === sPutReq
      mem.a.bits := Mux(
        dmaState === sPutReq,
        edge.Put(fromSource = 0.U, toAddress = currentDst, lgSize = dmaLgSize, data = readData)._2,
        edge.Get(fromSource = 0.U, toAddress = currentSrc, lgSize = dmaLgSize)._2)
      mem.d.ready := dmaState === sGetResp || dmaState === sPutResp

      when (!busy && startRequested) {
        ctrl := ctrl & (~1.U(32.W))
        busy := true.B
        done := false.B
        error := false.B
        irqPending := false.B
        copiedBeats := 0.U
        currentSrc := Cat(srcHi, srcLo)(edge.bundle.addressBits - 1, 0)
        currentDst := Cat(dstHi, dstLo)(edge.bundle.addressBits - 1, 0)
        bytesLeft := alignedLen

        when (!dmaEnabled || alignedLen === 0.U) {
          error := dmaEnabled && (lenReg =/= 0.U) && (alignedLen === 0.U)
          busy := false.B
          done := true.B
          dmaState := sDone
          irqPending := irqEnable
        } .otherwise {
          dmaState := sGetReq
        }
      }

      switch(dmaState) {
        is(sGetReq) {
          when (mem.a.fire) {
            dmaState := sGetResp
          }
        }
        is(sGetResp) {
          when (mem.d.fire) {
            readData := mem.d.bits.data
            dmaState := sPutReq
          }
        }
        is(sPutReq) {
          when (mem.a.fire) {
            dmaState := sPutResp
          }
        }
        is(sPutResp) {
          when (mem.d.fire) {
            copiedBeats := copiedBeats + 1.U
            when (bytesLeft <= dmaBeatBytes.U) {
              busy := false.B
              done := true.B
              dmaState := sDone
              irqPending := irqEnable
            } .otherwise {
              currentSrc := currentSrc + dmaBeatBytes.U
              currentDst := currentDst + dmaBeatBytes.U
              bytesLeft := bytesLeft - dmaBeatBytes.U
              dmaState := sGetReq
            }
          }
        }
        is(sDone) {
          when (!busy) {
            dmaState := sIdle
          }
        }
      }

      val status = Cat(
        0.U(23.W),
        copiedBeats(3, 0),
        error,
        irqPending,
        irqEnable,
        done,
        busy,
        dmaState(2, 0))

      irqPendingVec(idx) := irqPending
      busyVec(idx) := busy
      doneVec(idx) := done
      irqEnableVec(idx) := irqEnable
      errorVec(idx) := error
      intOut(idx) := irqPending && irqEnable

      node.regmap(
        0x00 -> Seq(RegField(32, ctrl, RegFieldDesc("ctrl", s"${slot.name} control register", reset = Some(0)))),
        0x04 -> Seq(RegField.r(32, status, RegFieldDesc("status", s"${slot.name} status register", volatile = true))),
        0x08 -> Seq(RegField(32, srcLo, RegFieldDesc("src_addr_lo", s"${slot.name} source address low"))),
        0x0c -> Seq(RegField(32, srcHi, RegFieldDesc("src_addr_hi", s"${slot.name} source address high"))),
        0x10 -> Seq(RegField(32, dstLo, RegFieldDesc("dst_addr_lo", s"${slot.name} destination address low"))),
        0x14 -> Seq(RegField(32, dstHi, RegFieldDesc("dst_addr_hi", s"${slot.name} destination address high"))),
        0x18 -> Seq(RegField(32, lenReg, RegFieldDesc("len", s"${slot.name} transfer length in bytes"))),
        0x1c -> Seq(RegField(32, cfg0, RegFieldDesc("cfg0", s"${slot.name} config0, bit0 enables loopback DMA"))),
        0x20 -> Seq(RegField(32, cfg1, RegFieldDesc("cfg1", s"${slot.name} config1"))),
        0x24 -> Seq(RegField(32, cfg2, RegFieldDesc("cfg2", s"${slot.name} config2"))),
        0x28 -> Seq(RegField(32, cfg3, RegFieldDesc("cfg3", s"${slot.name} config3"))),
        0x2c -> Seq(RegField(1, irqEnable, RegFieldDesc("irq_enable", s"${slot.name} interrupt enable", reset = Some(0)))),
        0x30 -> Seq(RegField.w1ToClear(1, irqPending, irqPending, Some(RegFieldDesc("irq_status", s"${slot.name} pending interrupt", volatile = true)))),
        0x34 -> Seq(RegField.r(32, copiedBeats, RegFieldDesc("copied_beats", s"${slot.name} completed DMA beats", volatile = true))))
    }

    val pendingBits = Cat(irqPendingVec.reverse)
    val busyBits = Cat(busyVec.reverse)
    val doneBits = Cat(doneVec.reverse)
    val enabledBits = Cat(irqEnableVec.reverse)
    val errorBits = Cat(errorVec.reverse)

    def lo(x: BigInt): UInt = (x & 0xffffffffL).U(32.W)
    def hi(x: BigInt): UInt = ((x >> 32) & 0xffffffffL).U(32.W)

    irqStatusNode.regmap(
      0x00 -> Seq(RegField.r(32, version, RegFieldDesc("version", "Generic radar shell version"))),
      0x04 -> Seq(RegField.r(32, slotCountReg, RegFieldDesc("slot_count", "Number of reserved accelerator slots"))),
      0x08 -> Seq(RegField.r(32, pendingBits.pad(32), RegFieldDesc("pending", "Per-slot pending interrupt bitmap", volatile = true))),
      0x0c -> Seq(RegField.r(32, busyBits.pad(32), RegFieldDesc("busy", "Per-slot busy bitmap", volatile = true))),
      0x10 -> Seq(RegField.r(32, doneBits.pad(32), RegFieldDesc("done", "Per-slot done bitmap", volatile = true))),
      0x14 -> Seq(RegField.r(32, enabledBits.pad(32), RegFieldDesc("irq_enable", "Per-slot interrupt enable bitmap"))),
      0x18 -> Seq(RegField.r(32, errorBits.pad(32), RegFieldDesc("error", "Per-slot error bitmap", volatile = true))),
      0x20 -> Seq(RegField.r(32, lo(params.memoryRegions(0).base), RegFieldDesc("buf_in_base_lo", "Reserved input buffer base low"))),
      0x24 -> Seq(RegField.r(32, hi(params.memoryRegions(0).base), RegFieldDesc("buf_in_base_hi", "Reserved input buffer base high"))),
      0x28 -> Seq(RegField.r(32, lo(params.memoryRegions(1).base), RegFieldDesc("buf_mid0_base_lo", "Reserved mid0 buffer base low"))),
      0x2c -> Seq(RegField.r(32, hi(params.memoryRegions(1).base), RegFieldDesc("buf_mid0_base_hi", "Reserved mid0 buffer base high"))),
      0x30 -> Seq(RegField.r(32, lo(params.memoryRegions(2).base), RegFieldDesc("buf_mid1_base_lo", "Reserved mid1 buffer base low"))),
      0x34 -> Seq(RegField.r(32, hi(params.memoryRegions(2).base), RegFieldDesc("buf_mid1_base_hi", "Reserved mid1 buffer base high"))),
      0x38 -> Seq(RegField.r(32, lo(params.memoryRegions(3).base), RegFieldDesc("buf_out_base_lo", "Reserved output buffer base low"))),
      0x3c -> Seq(RegField.r(32, hi(params.memoryRegions(3).base), RegFieldDesc("buf_out_base_hi", "Reserved output buffer base high"))),
      0x40 -> Seq(RegField.r(32, lo(params.memoryRegions(4).base), RegFieldDesc("desc_ring_base_lo", "Reserved descriptor ring base low"))),
      0x44 -> Seq(RegField.r(32, hi(params.memoryRegions(4).base), RegFieldDesc("desc_ring_base_hi", "Reserved descriptor ring base high"))),
      0x48 -> Seq(RegField.r(32, params.memoryRegions(0).size.U(32.W), RegFieldDesc("buf_in_size", "Reserved input buffer size in bytes"))),
      0x4c -> Seq(RegField.r(32, params.memoryRegions(1).size.U(32.W), RegFieldDesc("buf_mid0_size", "Reserved mid0 buffer size in bytes"))),
      0x50 -> Seq(RegField.r(32, params.memoryRegions(2).size.U(32.W), RegFieldDesc("buf_mid1_size", "Reserved mid1 buffer size in bytes"))),
      0x54 -> Seq(RegField.r(32, params.memoryRegions(3).size.U(32.W), RegFieldDesc("buf_out_size", "Reserved output buffer size in bytes"))),
      0x58 -> Seq(RegField.r(32, params.memoryRegions(4).size.U(32.W), RegFieldDesc("desc_ring_size", "Reserved descriptor ring size in bytes"))))
    }
  }
}

trait CanHavePeripheryGenericRadarShell { this: BaseSubsystem =>
  val genericRadarShell = p(GenericRadarShellKey).map { params =>
    val pbus = locateTLBusWrapper(PBUS)
    val fbus = locateTLBusWrapper(FBUS)
    val shell = LazyModule(new GenericRadarShell(pbus.beatBytes, params))
    shell.clockNode := pbus.fixedClockNode

    params.slots.zip(shell.slotControlNodes).foreach { case (slot, node) =>
      pbus.coupleTo(slot.name) { node := TLFragmenter(pbus.beatBytes, pbus.blockBytes) := _ }
    }
    pbus.coupleTo("generic-radar-irq-status") {
      shell.irqStatusNode := TLFragmenter(pbus.beatBytes, pbus.blockBytes) := _
    }

    params.slots.zip(shell.dmaNodes).foreach { case (slot, dmaNode) =>
      fbus.coupleFrom(s"${slot.name}-dma") { _ := TLBuffer() := dmaNode }
    }

    ibus.fromSync := shell.intNode
    shell
  }
}

class WithGenericRadarShell(params: GenericRadarShellParams = GenericRadarShellParams()) extends Config((site, here, up) => {
  case GenericRadarShellKey => Some(params)
})
