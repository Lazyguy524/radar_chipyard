package chipyard.radar.candidate20260917

import chisel3._
import chisel3.util._

/** Verification-only top: actual isolated Feature21 and QMLP, with feature tap. */
class CandidateTop extends Module {
  val io = IO(new Bundle {
    val abort = Input(Bool())
    val in = Flipped(Decoupled(new RadarAXISWord))
    val out = Decoupled(new RadarAXISWord)
    val featureFire = Output(Bool())
    val featureData = Output(UInt(64.W))
    val featureKeep = Output(UInt(8.W))
    val featureLast = Output(Bool())
    val featureStatus = Output(UInt(32.W))
    val qmlpStatus = Output(UInt(32.W))
  })
  val f = Module(new RadarAXISFeature21Preprocessor)
  val q = Module(new RadarAXISQMLP(4, RadarQMLPRomBackend.EmbeddedConstant))
  f.io.ctrlEnable := true.B
  q.io.ctrlEnable := true.B
  f.io.clearCounters := false.B
  q.io.clearCounters := false.B
  f.io.abort := io.abort
  q.io.abort := io.abort
  f.io.in <> io.in
  q.io.in <> f.io.out
  io.out <> q.io.out
  io.featureFire := f.io.out.fire
  io.featureData := f.io.out.bits.data
  io.featureKeep := f.io.out.bits.keep
  io.featureLast := f.io.out.bits.last
  io.featureStatus := f.io.status
  io.qmlpStatus := q.io.status
}

object CandidateEmit extends App {
  circt.stage.ChiselStage.emitSystemVerilogFile(
    new CandidateTop,
    Array("--target-dir", "."),
    Array("--disable-all-randomization", "--strip-debug-info"))
}
