package chipyard.fpga.nexysvideo

import chisel3._
import chisel3.experimental.IntParam
import chisel3.util._
import freechips.rocketchip.amba.axi4._
import freechips.rocketchip.diplomacy._
import freechips.rocketchip.util.ElaborationArtefacts
import org.chipsalliance.cde.config.{Field, Parameters}

import java.nio.file.{Files, Paths}
import scala.collection.JavaConverters._

case object EnableNexysVideoFullChain extends Field[Boolean](false)

object FullChainAXIMMIOAddressMap {
  val Base       = 0x60000000L
  val WindowSize = 0x00010000L
}

private object FullChainRTLSource {
  private val relativeDir =
    "addition/FullChain_ForWeijie_260511/FullChain_ForWeijie_260511/RTL/RTL"

  private def locateDir(): java.nio.file.Path = {
    val candidates = Seq(
      Paths.get(relativeDir),
      Paths.get("..", relativeDir),
      Paths.get("..", "..", relativeDir))
    candidates.find(Files.isDirectory(_)).getOrElse {
      throw new IllegalArgumentException(s"Unable to locate FullChain RTL directory: $relativeDir")
    }
  }

  val verilogFiles: Seq[String] = {
    val stream = Files.list(locateDir())
    try {
      stream.iterator.asScala
        .filter(path => Files.isRegularFile(path) && path.toString.endsWith(".v"))
        .map(_.toAbsolutePath.toString)
        .toSeq
        .sorted
    } finally {
      stream.close()
    }
  }
}

class FullChainAXIDMABlackBox extends BlackBox {
  override def desiredName: String = "full_chain_axi_dma"

  val io = IO(new Bundle {
    val s_axi_lite_aclk = Input(Clock())
    val m_axi_mm2s_aclk = Input(Clock())
    val m_axi_s2mm_aclk = Input(Clock())
    val axi_resetn      = Input(Bool())

    val s_axi_lite_awvalid = Input(Bool())
    val s_axi_lite_awready = Output(Bool())
    val s_axi_lite_awaddr  = Input(UInt(10.W))

    val s_axi_lite_wvalid = Input(Bool())
    val s_axi_lite_wready = Output(Bool())
    val s_axi_lite_wdata  = Input(UInt(32.W))

    val s_axi_lite_bresp  = Output(UInt(2.W))
    val s_axi_lite_bvalid = Output(Bool())
    val s_axi_lite_bready = Input(Bool())

    val s_axi_lite_arvalid = Input(Bool())
    val s_axi_lite_arready = Output(Bool())
    val s_axi_lite_araddr  = Input(UInt(10.W))

    val s_axi_lite_rvalid = Output(Bool())
    val s_axi_lite_rready = Input(Bool())
    val s_axi_lite_rdata  = Output(UInt(32.W))
    val s_axi_lite_rresp  = Output(UInt(2.W))

    val m_axi_mm2s_araddr  = Output(UInt(32.W))
    val m_axi_mm2s_arlen   = Output(UInt(8.W))
    val m_axi_mm2s_arsize  = Output(UInt(3.W))
    val m_axi_mm2s_arburst = Output(UInt(2.W))
    val m_axi_mm2s_arprot  = Output(UInt(3.W))
    val m_axi_mm2s_arcache = Output(UInt(4.W))
    val m_axi_mm2s_arvalid = Output(Bool())
    val m_axi_mm2s_arready = Input(Bool())
    val m_axi_mm2s_rdata   = Input(UInt(64.W))
    val m_axi_mm2s_rresp   = Input(UInt(2.W))
    val m_axi_mm2s_rlast   = Input(Bool())
    val m_axi_mm2s_rvalid  = Input(Bool())
    val m_axi_mm2s_rready  = Output(Bool())

    val mm2s_prmry_reset_out_n = Output(Bool())
    val m_axis_mm2s_tdata      = Output(UInt(32.W))
    val m_axis_mm2s_tkeep      = Output(UInt(4.W))
    val m_axis_mm2s_tvalid     = Output(Bool())
    val m_axis_mm2s_tready     = Input(Bool())
    val m_axis_mm2s_tlast      = Output(Bool())

    val m_axi_s2mm_awaddr  = Output(UInt(32.W))
    val m_axi_s2mm_awlen   = Output(UInt(8.W))
    val m_axi_s2mm_awsize  = Output(UInt(3.W))
    val m_axi_s2mm_awburst = Output(UInt(2.W))
    val m_axi_s2mm_awprot  = Output(UInt(3.W))
    val m_axi_s2mm_awcache = Output(UInt(4.W))
    val m_axi_s2mm_awvalid = Output(Bool())
    val m_axi_s2mm_awready = Input(Bool())
    val m_axi_s2mm_wdata   = Output(UInt(64.W))
    val m_axi_s2mm_wstrb   = Output(UInt(8.W))
    val m_axi_s2mm_wlast   = Output(Bool())
    val m_axi_s2mm_wvalid  = Output(Bool())
    val m_axi_s2mm_wready  = Input(Bool())
    val m_axi_s2mm_bresp   = Input(UInt(2.W))
    val m_axi_s2mm_bvalid  = Input(Bool())
    val m_axi_s2mm_bready  = Output(Bool())

    val s2mm_prmry_reset_out_n = Output(Bool())
    val s_axis_s2mm_tdata      = Input(UInt(64.W))
    val s_axis_s2mm_tkeep      = Input(UInt(8.W))
    val s_axis_s2mm_tvalid     = Input(Bool())
    val s_axis_s2mm_tready     = Output(Bool())
    val s_axis_s2mm_tlast      = Input(Bool())

    val mm2s_introut  = Output(Bool())
    val s2mm_introut  = Output(Bool())
    val axi_dma_tstvec = Output(UInt(32.W))
  })

  ElaborationArtefacts.add(
    s"${desiredName}.vivado.tcl",
    s"""create_ip -vendor xilinx.com -library ip -name axi_dma -module_name ${desiredName} -dir $$ipdir -force
       |set_property -dict [list \\
       |  CONFIG.c_include_sg {0} \\
       |  CONFIG.c_sg_include_stscntrl_strm {0} \\
       |  CONFIG.c_include_mm2s {1} \\
       |  CONFIG.c_include_s2mm {1} \\
       |  CONFIG.c_m_axi_mm2s_data_width {64} \\
       |  CONFIG.c_m_axis_mm2s_tdata_width {32} \\
       |  CONFIG.c_s_axis_s2mm_tdata_width {64} \\
       |  CONFIG.c_m_axi_s2mm_data_width {64} \\
       |  CONFIG.c_addr_width {32} \\
       |  CONFIG.c_mm2s_burst_size {8} \\
       |  CONFIG.c_s2mm_burst_size {8} \\
       |] [get_ips ${desiredName}]
       |""".stripMargin)
}

class FullChainAXIAccelBlackBox
    extends BlackBox(Map(
      "C_S_AXI_ADDR_WIDTH" -> IntParam(6),
      "C_S_AXI_DATA_WIDTH" -> IntParam(32)))
    with HasBlackBoxPath {
  override def desiredName: String = "full_chain_axi_accel"

  FullChainRTLSource.verilogFiles.foreach(addPath)

  val io = IO(new Bundle {
    val aclk    = Input(Clock())
    val aresetn = Input(Bool())
    val irq     = Output(Bool())

    val s_axi_control_awaddr  = Input(UInt(6.W))
    val s_axi_control_awprot  = Input(UInt(3.W))
    val s_axi_control_awvalid = Input(Bool())
    val s_axi_control_awready = Output(Bool())
    val s_axi_control_wdata   = Input(UInt(32.W))
    val s_axi_control_wstrb   = Input(UInt(4.W))
    val s_axi_control_wvalid  = Input(Bool())
    val s_axi_control_wready  = Output(Bool())
    val s_axi_control_bresp   = Output(UInt(2.W))
    val s_axi_control_bvalid  = Output(Bool())
    val s_axi_control_bready  = Input(Bool())
    val s_axi_control_araddr  = Input(UInt(6.W))
    val s_axi_control_arprot  = Input(UInt(3.W))
    val s_axi_control_arvalid = Input(Bool())
    val s_axi_control_arready = Output(Bool())
    val s_axi_control_rdata   = Output(UInt(32.W))
    val s_axi_control_rresp   = Output(UInt(2.W))
    val s_axi_control_rvalid  = Output(Bool())
    val s_axi_control_rready  = Input(Bool())

    val s_axis_input_tdata  = Input(UInt(32.W))
    val s_axis_input_tkeep  = Input(UInt(4.W))
    val s_axis_input_tvalid = Input(Bool())
    val s_axis_input_tready = Output(Bool())
    val s_axis_input_tlast  = Input(Bool())

    val m_axis_output_tdata  = Output(UInt(128.W))
    val m_axis_output_tkeep  = Output(UInt(16.W))
    val m_axis_output_tvalid = Output(Bool())
    val m_axis_output_tready = Input(Bool())
    val m_axis_output_tlast  = Output(Bool())
  })
}

class FullChainAXIS128To64 extends Module {
  val io = IO(new Bundle {
    val in = Flipped(Decoupled(new Bundle {
      val data = UInt(128.W)
      val keep = UInt(16.W)
      val last = Bool()
    }))
    val out = Decoupled(new Bundle {
      val data = UInt(64.W)
      val keep = UInt(8.W)
      val last = Bool()
    })
  })

  val sIdle :: sEmitLo :: sEmitHi :: Nil = Enum(3)
  val state = RegInit(sIdle)
  val dataReg = Reg(UInt(128.W))
  val keepReg = Reg(UInt(16.W))
  val lastReg = Reg(Bool())

  io.in.ready := state === sIdle
  io.out.valid := state =/= sIdle
  io.out.bits.data := Mux(state === sEmitLo, dataReg(63, 0), dataReg(127, 64))
  io.out.bits.keep := Mux(state === sEmitLo, keepReg(7, 0), keepReg(15, 8))
  io.out.bits.last := state === sEmitHi && lastReg

  when (state === sIdle && io.in.fire) {
    dataReg := io.in.bits.data
    keepReg := io.in.bits.keep
    lastReg := io.in.bits.last
    state := sEmitLo
  } .elsewhen (state === sEmitLo && io.out.fire) {
    state := sEmitHi
  } .elsewhen (state === sEmitHi && io.out.fire) {
    state := sIdle
  }
}

class FullChainAXI4ToDualLiteBridge(params: RadarAXIDMAControlParams, liteAddrBits: Int = 10)
    extends Module {
  private val full = AXI4BundleParameters(
    addrBits = params.addrBits,
    dataBits = params.dataBits,
    idBits   = params.idBits)
  private val wordSize = log2Ceil(4).U

  val io = IO(new Bundle {
    val in    = Flipped(new AXI4Bundle(full))
    val dma   = new RadarAXI4LiteMasterIO(liteAddrBits)
    val accel = new RadarAXI4LiteMasterIO(6)
  })

  val sIdle :: sWriteCollect :: sWriteIssue :: sWriteResp :: sReadIssue :: sReadResp :: Nil = Enum(6)
  val state = RegInit(sIdle)

  val awCaptured = RegInit(false.B)
  val wCaptured  = RegInit(false.B)
  val awIssued   = RegInit(false.B)
  val wIssued    = RegInit(false.B)
  val awAddrReg  = Reg(UInt(params.addrBits.W))
  val awIdReg    = Reg(UInt(params.idBits.W))
  val awSizeReg  = Reg(UInt(io.in.aw.bits.size.getWidth.W))
  val awLenReg   = Reg(UInt(io.in.aw.bits.len.getWidth.W))
  val wDataReg   = Reg(UInt(params.dataBits.W))
  val wStrbReg   = Reg(UInt((params.dataBits / 8).W))
  val wLastReg   = RegInit(false.B)
  val bRespReg   = Reg(UInt(AXI4Parameters.respBits.W))
  val bRespValid = RegInit(false.B)

  val arIssued   = RegInit(false.B)
  val arAddrReg  = Reg(UInt(params.addrBits.W))
  val arIdReg    = Reg(UInt(params.idBits.W))
  val arSizeReg  = Reg(UInt(io.in.ar.bits.size.getWidth.W))
  val arLenReg   = Reg(UInt(io.in.ar.bits.len.getWidth.W))
  val rDataReg   = Reg(UInt(params.dataBits.W))
  val rRespReg   = Reg(UInt(AXI4Parameters.respBits.W))
  val rRespValid = RegInit(false.B)

  val writeUpperWord = awAddrReg(2)
  val writeLowerStrb = wStrbReg(3, 0)
  val writeUpperStrb = wStrbReg(7, 4)
  val liteWriteData  = Mux(writeUpperWord, wDataReg(63, 32), wDataReg(31, 0))
  val liteWriteStrb  = Mux(writeUpperWord, writeUpperStrb, writeLowerStrb)
  val expectedLaneStrb = Mux(writeUpperWord, "hF0".U(8.W), "h0F".U(8.W))
  val writeForward = awLenReg === 0.U &&
    awSizeReg === wordSize &&
    awAddrReg(1, 0) === 0.U &&
    wLastReg &&
    wStrbReg === expectedLaneStrb &&
    liteWriteStrb === "hF".U
  val writeToAccel = awAddrReg(9, 8) === 2.U
  val writeToDma = !writeToAccel

  val readForward = arLenReg === 0.U &&
    arSizeReg === wordSize &&
    arAddrReg(1, 0) === 0.U
  val readToAccel = arAddrReg(9, 8) === 2.U
  val readToDma = !readToAccel

  io.in.aw.ready := false.B
  io.in.w.ready  := false.B
  io.in.ar.ready := false.B

  io.in.b.valid := state === sWriteResp && bRespValid
  io.in.b.bits.id := awIdReg
  io.in.b.bits.resp := bRespReg
  io.in.b.bits.user := DontCare

  io.in.r.valid := state === sReadResp && rRespValid
  io.in.r.bits.id := arIdReg
  io.in.r.bits.data := rDataReg
  io.in.r.bits.resp := rRespReg
  io.in.r.bits.last := true.B
  io.in.r.bits.user := DontCare

  Seq(io.dma, io.accel).foreach { lite =>
    lite.awvalid := false.B
    lite.awaddr  := 0.U
    lite.wvalid  := false.B
    lite.wdata   := liteWriteData
    lite.wstrb   := liteWriteStrb
    lite.bready  := false.B
    lite.arvalid := false.B
    lite.araddr  := 0.U
    lite.rready  := false.B
  }

  val dmaWriteActive = state === sWriteIssue && writeForward && writeToDma
  val accelWriteActive = state === sWriteIssue && writeForward && writeToAccel
  io.dma.awvalid := dmaWriteActive && awCaptured && !awIssued
  io.dma.awaddr := awAddrReg(liteAddrBits - 1, 0)
  io.dma.wvalid := dmaWriteActive && wCaptured && !wIssued
  io.dma.bready := dmaWriteActive && !bRespValid
  io.accel.awvalid := accelWriteActive && awCaptured && !awIssued
  io.accel.awaddr := awAddrReg(5, 0)
  io.accel.wvalid := accelWriteActive && wCaptured && !wIssued
  io.accel.bready := accelWriteActive && !bRespValid

  val dmaReadActive = state === sReadIssue && readForward && readToDma
  val accelReadActive = state === sReadIssue && readForward && readToAccel
  io.dma.arvalid := dmaReadActive && !arIssued
  io.dma.araddr := arAddrReg(liteAddrBits - 1, 0)
  io.dma.rready := dmaReadActive && !rRespValid
  io.accel.arvalid := accelReadActive && !arIssued
  io.accel.araddr := arAddrReg(5, 0)
  io.accel.rready := accelReadActive && !rRespValid

  val activeWriteAwReady = Mux(writeToAccel, io.accel.awready, io.dma.awready)
  val activeWriteWReady  = Mux(writeToAccel, io.accel.wready,  io.dma.wready)
  val activeWriteBValid  = Mux(writeToAccel, io.accel.bvalid,  io.dma.bvalid)
  val activeWriteBResp   = Mux(writeToAccel, io.accel.bresp,   io.dma.bresp)
  val activeReadArReady  = Mux(readToAccel,  io.accel.arready, io.dma.arready)
  val activeReadRValid   = Mux(readToAccel,  io.accel.rvalid,  io.dma.rvalid)
  val activeReadRData    = Mux(readToAccel,  io.accel.rdata,   io.dma.rdata)
  val activeReadRResp    = Mux(readToAccel,  io.accel.rresp,   io.dma.rresp)

  switch (state) {
    is (sIdle) {
      when (io.in.aw.valid || io.in.w.valid) {
        io.in.aw.ready := true.B
        io.in.w.ready := true.B
        when (io.in.aw.fire) {
          awCaptured := true.B
          awAddrReg := io.in.aw.bits.addr
          awIdReg := io.in.aw.bits.id
          awSizeReg := io.in.aw.bits.size
          awLenReg := io.in.aw.bits.len
        }
        when (io.in.w.fire) {
          wCaptured := true.B
          wDataReg := io.in.w.bits.data
          wStrbReg := io.in.w.bits.strb
          wLastReg := io.in.w.bits.last
        }
        state := Mux(io.in.aw.valid && io.in.w.valid, sWriteIssue, sWriteCollect)
      } .otherwise {
        io.in.ar.ready := true.B
        when (io.in.ar.fire) {
          arAddrReg := io.in.ar.bits.addr
          arIdReg := io.in.ar.bits.id
          arSizeReg := io.in.ar.bits.size
          arLenReg := io.in.ar.bits.len
          state := sReadIssue
        }
      }
    }

    is (sWriteCollect) {
      io.in.aw.ready := !awCaptured
      io.in.w.ready := !wCaptured
      when (io.in.aw.fire) {
        awCaptured := true.B
        awAddrReg := io.in.aw.bits.addr
        awIdReg := io.in.aw.bits.id
        awSizeReg := io.in.aw.bits.size
        awLenReg := io.in.aw.bits.len
      }
      when (io.in.w.fire) {
        wCaptured := true.B
        wDataReg := io.in.w.bits.data
        wStrbReg := io.in.w.bits.strb
        wLastReg := io.in.w.bits.last
      }
      when ((awCaptured || io.in.aw.fire) && (wCaptured || io.in.w.fire)) {
        state := sWriteIssue
      }
    }

    is (sWriteIssue) {
      val awHandshake = (io.dma.awvalid && io.dma.awready) || (io.accel.awvalid && io.accel.awready)
      val wHandshake = (io.dma.wvalid && io.dma.wready) || (io.accel.wvalid && io.accel.wready)
      val nextAwIssued = awIssued || awHandshake
      val nextWIssued = wIssued || wHandshake
      val canCaptureB = !bRespValid && writeForward && nextAwIssued && nextWIssued && activeWriteBValid

      when (awHandshake) { awIssued := true.B }
      when (wHandshake) { wIssued := true.B }

      when (!writeForward && !bRespValid) {
        bRespReg := AXI4Parameters.RESP_SLVERR
        bRespValid := true.B
        state := sWriteResp
      } .elsewhen (canCaptureB) {
        bRespReg := activeWriteBResp
        bRespValid := true.B
        awIssued := nextAwIssued
        wIssued := nextWIssued
        state := sWriteResp
      }
    }

    is (sWriteResp) {
      when (io.in.b.fire) {
        awCaptured := false.B
        wCaptured := false.B
        awIssued := false.B
        wIssued := false.B
        wLastReg := false.B
        bRespValid := false.B
        state := sIdle
      }
    }

    is (sReadIssue) {
      val arHandshake = (io.dma.arvalid && io.dma.arready) || (io.accel.arvalid && io.accel.arready)
      val nextArIssued = arIssued || arHandshake
      val canCaptureR = !rRespValid && readForward && nextArIssued && activeReadRValid

      when (arHandshake) { arIssued := true.B }
      when (!readForward && !rRespValid) {
        rDataReg := 0.U
        rRespReg := AXI4Parameters.RESP_SLVERR
        rRespValid := true.B
        state := sReadResp
      } .elsewhen (canCaptureR) {
        rDataReg := Mux(arAddrReg(2), Cat(activeReadRData, 0.U(32.W)), Cat(0.U(32.W), activeReadRData))
        rRespReg := activeReadRResp
        rRespValid := true.B
        arIssued := nextArIssued
        state := sReadResp
      }
    }

    is (sReadResp) {
      when (io.in.r.fire) {
        arIssued := false.B
        rRespValid := false.B
        state := sIdle
      }
    }
  }
}

class FullChainAXIDMA(implicit p: Parameters) extends LazyModule {
  val controlParams = RadarAXIDMAControlParams()

  val mm2sNode = AXI4MasterNode(Seq(AXI4MasterPortParameters(
    masters = Seq(AXI4MasterParameters(
      name = "fullchain-dma-mm2s",
      id   = IdRange(0, 1),
      aligned = false)))))

  val s2mmNode = AXI4MasterNode(Seq(AXI4MasterPortParameters(
    masters = Seq(AXI4MasterParameters(
      name = "fullchain-dma-s2mm",
      id   = IdRange(0, 1),
      aligned = false)))))

  lazy val module = new Impl

  class Impl extends LazyRawModuleImp(this) {
    val debug = IO(Output(new Bundle {
      val mm2sStreamFireSeen = Bool()
      val s2mmStreamFireSeen = Bool()
      val fullChainIrqSeen   = Bool()
      val dmaMm2sIOCSeen     = Bool()
      val dmaS2mmIOCSeen     = Bool()
    }))
    val ctrlClock = IO(Input(Clock()))
    val ctrlResetN = IO(Input(Bool()))
    val ctrl = IO(Flipped(new AXI4Bundle(AXI4BundleParameters(
      addrBits = controlParams.addrBits,
      dataBits = controlParams.dataBits,
      idBits   = controlParams.idBits))))

    val dma = Module(new FullChainAXIDMABlackBox)
    val accel = Module(new FullChainAXIAccelBlackBox)
    val outputDownsizer = withClockAndReset(ctrlClock, (!ctrlResetN).asAsyncReset) {
      Module(new FullChainAXIS128To64)
    }
    val ctrlBridge = withClockAndReset(ctrlClock, (!ctrlResetN).asAsyncReset) {
      Module(new FullChainAXI4ToDualLiteBridge(controlParams))
    }

    val (mm2s, _) = mm2sNode.out(0)
    val (s2mm, _) = s2mmNode.out(0)

    dma.io.s_axi_lite_aclk := ctrlClock
    dma.io.m_axi_mm2s_aclk := ctrlClock
    dma.io.m_axi_s2mm_aclk := ctrlClock
    dma.io.axi_resetn      := ctrlResetN

    accel.io.aclk := ctrlClock
    accel.io.aresetn := ctrlResetN

    ctrlBridge.io.in <> ctrl

    dma.io.s_axi_lite_awvalid := ctrlBridge.io.dma.awvalid
    ctrlBridge.io.dma.awready := dma.io.s_axi_lite_awready
    dma.io.s_axi_lite_awaddr  := ctrlBridge.io.dma.awaddr
    dma.io.s_axi_lite_wvalid  := ctrlBridge.io.dma.wvalid
    ctrlBridge.io.dma.wready  := dma.io.s_axi_lite_wready
    dma.io.s_axi_lite_wdata   := ctrlBridge.io.dma.wdata
    ctrlBridge.io.dma.bvalid  := dma.io.s_axi_lite_bvalid
    dma.io.s_axi_lite_bready  := ctrlBridge.io.dma.bready
    ctrlBridge.io.dma.bresp   := dma.io.s_axi_lite_bresp
    dma.io.s_axi_lite_arvalid := ctrlBridge.io.dma.arvalid
    ctrlBridge.io.dma.arready := dma.io.s_axi_lite_arready
    dma.io.s_axi_lite_araddr  := ctrlBridge.io.dma.araddr
    ctrlBridge.io.dma.rvalid  := dma.io.s_axi_lite_rvalid
    dma.io.s_axi_lite_rready  := ctrlBridge.io.dma.rready
    ctrlBridge.io.dma.rdata   := dma.io.s_axi_lite_rdata
    ctrlBridge.io.dma.rresp   := dma.io.s_axi_lite_rresp

    accel.io.s_axi_control_awvalid := ctrlBridge.io.accel.awvalid
    ctrlBridge.io.accel.awready := accel.io.s_axi_control_awready
    accel.io.s_axi_control_awaddr := ctrlBridge.io.accel.awaddr
    accel.io.s_axi_control_awprot := 0.U
    accel.io.s_axi_control_wvalid := ctrlBridge.io.accel.wvalid
    ctrlBridge.io.accel.wready := accel.io.s_axi_control_wready
    accel.io.s_axi_control_wdata := ctrlBridge.io.accel.wdata
    accel.io.s_axi_control_wstrb := ctrlBridge.io.accel.wstrb
    ctrlBridge.io.accel.bvalid := accel.io.s_axi_control_bvalid
    accel.io.s_axi_control_bready := ctrlBridge.io.accel.bready
    ctrlBridge.io.accel.bresp := accel.io.s_axi_control_bresp
    accel.io.s_axi_control_arvalid := ctrlBridge.io.accel.arvalid
    ctrlBridge.io.accel.arready := accel.io.s_axi_control_arready
    accel.io.s_axi_control_araddr := ctrlBridge.io.accel.araddr
    accel.io.s_axi_control_arprot := 0.U
    ctrlBridge.io.accel.rvalid := accel.io.s_axi_control_rvalid
    accel.io.s_axi_control_rready := ctrlBridge.io.accel.rready
    ctrlBridge.io.accel.rdata := accel.io.s_axi_control_rdata
    ctrlBridge.io.accel.rresp := accel.io.s_axi_control_rresp

    accel.io.s_axis_input_tdata := dma.io.m_axis_mm2s_tdata
    accel.io.s_axis_input_tkeep := dma.io.m_axis_mm2s_tkeep
    accel.io.s_axis_input_tvalid := dma.io.m_axis_mm2s_tvalid
    dma.io.m_axis_mm2s_tready := accel.io.s_axis_input_tready
    accel.io.s_axis_input_tlast := dma.io.m_axis_mm2s_tlast

    outputDownsizer.io.in.bits.data := accel.io.m_axis_output_tdata
    outputDownsizer.io.in.bits.keep := accel.io.m_axis_output_tkeep
    outputDownsizer.io.in.bits.last := accel.io.m_axis_output_tlast
    outputDownsizer.io.in.valid := accel.io.m_axis_output_tvalid
    accel.io.m_axis_output_tready := outputDownsizer.io.in.ready

    dma.io.s_axis_s2mm_tdata := outputDownsizer.io.out.bits.data
    dma.io.s_axis_s2mm_tkeep := outputDownsizer.io.out.bits.keep
    dma.io.s_axis_s2mm_tvalid := outputDownsizer.io.out.valid
    outputDownsizer.io.out.ready := dma.io.s_axis_s2mm_tready
    dma.io.s_axis_s2mm_tlast := outputDownsizer.io.out.bits.last

    val (mm2sStreamFireSeen, s2mmStreamFireSeen, fullChainIrqSeen, dmaMm2sIOCSeen, dmaS2mmIOCSeen) =
      withClockAndReset(ctrlClock, (!ctrlResetN).asAsyncReset) {
        val mm2sSeen = RegInit(false.B)
        val s2mmSeen = RegInit(false.B)
        val irqSeen = RegInit(false.B)
        val mm2sIOCSeen = RegInit(false.B)
        val s2mmIOCSeen = RegInit(false.B)

        when (dma.io.m_axis_mm2s_tvalid && dma.io.m_axis_mm2s_tready) { mm2sSeen := true.B }
        when (dma.io.s_axis_s2mm_tvalid && dma.io.s_axis_s2mm_tready) { s2mmSeen := true.B }
        when (accel.io.irq) { irqSeen := true.B }
        when (dma.io.axi_dma_tstvec(4)) { mm2sIOCSeen := true.B }
        when (dma.io.axi_dma_tstvec(5)) { s2mmIOCSeen := true.B }
        (mm2sSeen, s2mmSeen, irqSeen, mm2sIOCSeen, s2mmIOCSeen)
      }

    debug.mm2sStreamFireSeen := mm2sStreamFireSeen
    debug.s2mmStreamFireSeen := s2mmStreamFireSeen
    debug.fullChainIrqSeen := fullChainIrqSeen
    debug.dmaMm2sIOCSeen := dmaMm2sIOCSeen
    debug.dmaS2mmIOCSeen := dmaS2mmIOCSeen

    mm2s.aw.valid := false.B
    mm2s.aw.bits  := DontCare
    mm2s.w.valid  := false.B
    mm2s.w.bits   := DontCare
    mm2s.b.ready  := false.B

    mm2s.ar.valid      := dma.io.m_axi_mm2s_arvalid
    mm2s.ar.bits.id    := 0.U
    mm2s.ar.bits.addr  := dma.io.m_axi_mm2s_araddr
    mm2s.ar.bits.len   := dma.io.m_axi_mm2s_arlen
    mm2s.ar.bits.size  := dma.io.m_axi_mm2s_arsize
    mm2s.ar.bits.burst := dma.io.m_axi_mm2s_arburst
    mm2s.ar.bits.lock  := 0.U
    mm2s.ar.bits.cache := dma.io.m_axi_mm2s_arcache
    mm2s.ar.bits.prot  := dma.io.m_axi_mm2s_arprot
    mm2s.ar.bits.qos   := 0.U
    dma.io.m_axi_mm2s_arready := mm2s.ar.ready

    dma.io.m_axi_mm2s_rdata  := mm2s.r.bits.data
    dma.io.m_axi_mm2s_rresp  := mm2s.r.bits.resp
    dma.io.m_axi_mm2s_rlast  := mm2s.r.bits.last
    dma.io.m_axi_mm2s_rvalid := mm2s.r.valid
    mm2s.r.ready             := dma.io.m_axi_mm2s_rready

    s2mm.ar.valid := false.B
    s2mm.ar.bits  := DontCare
    s2mm.r.ready  := false.B

    s2mm.aw.valid      := dma.io.m_axi_s2mm_awvalid
    s2mm.aw.bits.id    := 0.U
    s2mm.aw.bits.addr  := dma.io.m_axi_s2mm_awaddr
    s2mm.aw.bits.len   := dma.io.m_axi_s2mm_awlen
    s2mm.aw.bits.size  := dma.io.m_axi_s2mm_awsize
    s2mm.aw.bits.burst := dma.io.m_axi_s2mm_awburst
    s2mm.aw.bits.lock  := 0.U
    s2mm.aw.bits.cache := dma.io.m_axi_s2mm_awcache
    s2mm.aw.bits.prot  := dma.io.m_axi_s2mm_awprot
    s2mm.aw.bits.qos   := 0.U
    dma.io.m_axi_s2mm_awready := s2mm.aw.ready

    s2mm.w.valid     := dma.io.m_axi_s2mm_wvalid
    s2mm.w.bits.data := dma.io.m_axi_s2mm_wdata
    s2mm.w.bits.strb := dma.io.m_axi_s2mm_wstrb
    s2mm.w.bits.last := dma.io.m_axi_s2mm_wlast
    dma.io.m_axi_s2mm_wready := s2mm.w.ready

    dma.io.m_axi_s2mm_bresp  := s2mm.b.bits.resp
    dma.io.m_axi_s2mm_bvalid := s2mm.b.valid
    s2mm.b.ready             := dma.io.m_axi_s2mm_bready
  }
}
