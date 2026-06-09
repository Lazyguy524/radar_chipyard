// See LICENSE for license details.
package chipyard.fpga.nexysvideo

import chisel3._
import chisel3.util._
import org.chipsalliance.cde.config.{Config, Parameters}
import org.chipsalliance.diplomacy.lazymodule.LazyModule
import freechips.rocketchip.tile.{BuildRoCC, HasCoreParameters, LazyRoCC, LazyRoCCModuleImp, OpcodeSet}

class WithXradarRoCC(op: OpcodeSet = OpcodeSet.custom0) extends Config((site, here, up) => {
  case BuildRoCC => up(BuildRoCC) ++ Seq((p: Parameters) => {
    val xradar = LazyModule(new XradarRoCC(op)(p))
    xradar
  })
})

class XradarRoCC(opcodes: OpcodeSet)(implicit p: Parameters) extends LazyRoCC(opcodes) {
  override lazy val module = new XradarRoCCModuleImp(this)
}

class XradarRoCCModuleImp(outer: XradarRoCC)(implicit p: Parameters)
    extends LazyRoCCModuleImp(outer) with HasCoreParameters {
  private def laneI8(value: UInt, lane: Int): SInt = value(8 * lane + 7, 8 * lane).asSInt

  val sIdle :: sMul :: sSum :: sResp :: Nil = Enum(4)
  val state = RegInit(sIdle)

  val rdReg = Reg(UInt(5.W))
  val isRqdot4Reg = Reg(Bool())
  val rs1Reg = Reg(UInt(xLen.W))
  val rs2Reg = Reg(UInt(xLen.W))
  val p0Reg = Reg(SInt(16.W))
  val p1Reg = Reg(SInt(16.W))
  val p2Reg = Reg(SInt(16.W))
  val p3Reg = Reg(SInt(16.W))
  val dotReg = Reg(SInt(20.W))

  val p0 = laneI8(rs1Reg, 0) * laneI8(rs2Reg, 0)
  val p1 = laneI8(rs1Reg, 1) * laneI8(rs2Reg, 1)
  val p2 = laneI8(rs1Reg, 2) * laneI8(rs2Reg, 2)
  val p3 = laneI8(rs1Reg, 3) * laneI8(rs2Reg, 3)
  val dot = p0Reg +& p1Reg +& p2Reg +& p3Reg
  val dot32 = Wire(SInt(32.W))
  dot32 := dotReg
  val rqdot4Result = if (xLen == 32) {
    dot32.asUInt
  } else {
    Cat(Fill(xLen - 32, dot32(31)), dot32.asUInt)
  }

  val result = Mux(isRqdot4Reg, rqdot4Result, 0.U(xLen.W))

  io.cmd.ready := state === sIdle
  io.resp.valid := state === sResp
  io.resp.bits.rd := rdReg
  io.resp.bits.data := result

  when(state === sIdle && io.cmd.fire) {
    rdReg := io.cmd.bits.inst.rd
    isRqdot4Reg := io.cmd.bits.inst.funct === 0.U
    rs1Reg := io.cmd.bits.rs1
    rs2Reg := io.cmd.bits.rs2
    when(io.cmd.bits.inst.xd) {
      state := sMul
    }
  }.elsewhen(state === sMul) {
    p0Reg := p0
    p1Reg := p1
    p2Reg := p2
    p3Reg := p3
    state := sSum
  }.elsewhen(state === sSum) {
    dotReg := dot
    state := sResp
  }.elsewhen(state === sResp && io.resp.fire) {
    state := sIdle
  }

  io.mem.req.valid := false.B
  io.mem.req.bits := DontCare
  io.busy := state =/= sIdle
  io.interrupt := false.B
}
