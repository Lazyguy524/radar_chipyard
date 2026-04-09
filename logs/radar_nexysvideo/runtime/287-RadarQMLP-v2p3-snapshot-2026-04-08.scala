package chipyard.fpga.nexysvideo

import chisel3._
import chisel3.util._

import java.nio.file.{Files, Paths}
import scala.io.Source

case class RadarQMLPK3Rcs21Data(
  l1In: Int,
  l1Out: Int,
  l1Multiplier: Int,
  l2In: Int,
  l2Out: Int,
  l2Multiplier: Int,
  l3In: Int,
  l3Out: Int,
  l1Weight: Seq[Int],
  l1Bias: Seq[Int],
  l2Weight: Seq[Int],
  l2Bias: Seq[Int],
  l3Weight: Seq[Int],
  l3Bias: Seq[Int],
  l1OutputScale: Double,
  l2OutputScale: Double,
  l3OutputScale: Double,
  requantShift: Int = 16)

object RadarQMLPK3Rcs21Data {
  private def locate(path: String): String = {
    val candidates = Seq(
      path,
      s"../$path",
      s"../../$path")
    candidates.find(p => Files.exists(Paths.get(p))).getOrElse {
      throw new IllegalArgumentException(s"Unable to locate QMLP release file: $path")
    }
  }

  private def readReleaseText(): String = {
    val path = locate("releases/input_convergence_k3_rcs21_20260406/Radar_mlp_binary_k3_rcs21Params.scala")
    val src = Source.fromFile(path)
    try src.mkString finally src.close()
  }

  private val text = readReleaseText()

  private def intValue(name: String): Int = {
    val pattern = (s"""val\\s+$name\\s*=\\s*([-0-9]+)""").r
    pattern.findFirstMatchIn(text).map(_.group(1).toInt).getOrElse {
      throw new IllegalArgumentException(s"Missing integer field $name in release scala params")
    }
  }

  private def doubleValue(name: String): Double = {
    val pattern = (s"""val\\s+$name\\s*=\\s*([-+0-9.eE]+)""").r
    pattern.findFirstMatchIn(text).map(_.group(1).toDouble).getOrElse {
      throw new IllegalArgumentException(s"Missing double field $name in release scala params")
    }
  }

  private def intSeq(name: String): Seq[Int] = {
    val pattern = (s"""(?s)val\\s+$name\\s*=\\s*Seq\\((.*?)\\)""").r
    pattern.findFirstMatchIn(text).map { m =>
      m.group(1)
        .split(",")
        .iterator
        .map(_.trim)
        .filter(_.nonEmpty)
        .map(_.toInt)
        .toSeq
    }.getOrElse {
      throw new IllegalArgumentException(s"Missing sequence field $name in release scala params")
    }
  }

  private val requantShift = 16

  private def multiplier(inputScale: Double, weightScale: Double, outputScale: Double): Int = {
    math.round((inputScale * weightScale / outputScale) * (1 << requantShift)).toInt
  }

  val data: RadarQMLPK3Rcs21Data = RadarQMLPK3Rcs21Data(
    l1In = intValue("l1In"),
    l1Out = intValue("l1Out"),
    l1Multiplier = multiplier(doubleValue("l1InputScale"), doubleValue("l1WeightScale"), doubleValue("l1OutputScale")),
    l2In = intValue("l2In"),
    l2Out = intValue("l2Out"),
    l2Multiplier = multiplier(doubleValue("l2InputScale"), doubleValue("l2WeightScale"), doubleValue("l2OutputScale")),
    l3In = intValue("l3In"),
    l3Out = intValue("l3Out"),
    l1Weight = intSeq("l1Weight"),
    l1Bias = intSeq("l1Bias"),
    l2Weight = intSeq("l2Weight"),
    l2Bias = intSeq("l2Bias"),
    l3Weight = intSeq("l3Weight"),
    l3Bias = intSeq("l3Bias"),
    l1OutputScale = doubleValue("l1OutputScale"),
    l2OutputScale = doubleValue("l2OutputScale"),
    l3OutputScale = doubleValue("l3OutputScale"),
    requantShift = requantShift)
}

class RadarAXISQMLP extends Module {
  private val qmlp = RadarQMLPK3Rcs21Data.data
  // v2.2: back off lane parallelism to recover board-level stability while
  // preserving the staged PE/MAC structure introduced in v2/v2.1.
  private val peLanes = 2

  require(qmlp.l1Weight.size == qmlp.l1Out * qmlp.l1In, "L1 weight shape mismatch")
  require(qmlp.l2Weight.size == qmlp.l2Out * qmlp.l2In, "L2 weight shape mismatch")
  require(qmlp.l3Weight.size == qmlp.l3Out * qmlp.l3In, "L3 weight shape mismatch")

  private val Seq(
    sIdle, sRecv,
    sL1Load, sL1Mac, sL1Quant, sL1Write,
    sL2Load, sL2Mac, sL2Quant, sL2Write,
    sL3Load, sL3Mac, sL3Write, sL3Pack,
    sEmit) = Enum(15)

  val io = IO(new Bundle {
    val ctrlEnable = Input(Bool())
    val clearCounters = Input(Bool())

    val in = Flipped(Decoupled(new RadarAXISWord))
    val out = Decoupled(new RadarAXISWord)

    val inBeats = Output(UInt(32.W))
    val outBeats = Output(UInt(32.W))
    val frameCount = Output(UInt(32.W))
    val lastKeep = Output(UInt(8.W))
    val runCycles = Output(UInt(32.W))
    val lastLogit0 = Output(SInt(32.W))
    val lastLogit1 = Output(SInt(32.W))
    val status = Output(UInt(32.W))
    val capabilities = Output(UInt(32.W))
  })

  private val l1Biases = VecInit(qmlp.l1Bias.map(v => v.S(32.W)))
  private val l2Biases = VecInit(qmlp.l2Bias.map(v => v.S(32.W)))
  private val l3Biases = VecInit(qmlp.l3Bias.map(v => v.S(32.W)))

  private val l1Rows = VecInit(qmlp.l1Weight.grouped(qmlp.l1In).map(row => VecInit(row.map(_.S(8.W)))).toSeq)
  private val l2Rows = VecInit(qmlp.l2Weight.grouped(qmlp.l2In).map(row => VecInit(row.map(_.S(8.W)))).toSeq)
  private val l3Rows = VecInit(qmlp.l3Weight.grouped(qmlp.l3In).map(row => VecInit(row.map(_.S(8.W)))).toSeq)

  private def bankRoundShift(value: SInt, shift: Int): SInt = {
    val width = value.getWidth
    val absValue = Wire(UInt(width.W))
    absValue := Mux(value < 0.S, (-value).asUInt, value.asUInt)
    val qAbs = absValue >> shift
    val remMask = ((BigInt(1) << shift) - 1).U(width.W)
    val rem = absValue & remMask
    val half = (BigInt(1) << (shift - 1)).U(width.W)
    val roundUp = (rem > half) || ((rem === half) && qAbs(0))
    val roundedAbs = qAbs + roundUp
    Mux(value < 0.S, -roundedAbs.zext.asSInt, roundedAbs.zext.asSInt)
  }

  private def requantReluClamp(acc: SInt, multiplier: Int): SInt = {
    val product = (acc * multiplier.S(32.W)).asSInt
    val rounded = bankRoundShift(product, qmlp.requantShift)
    val relu = Mux(rounded < 0.S, 0.S, rounded)
    Mux(relu > 127.S, 127.S, relu)
  }

  private def sumTree(values: Seq[SInt]): SInt = values.tail.foldLeft(values.head) { (acc, v) => acc +& v }

  val state = RegInit(sIdle)
  val inputVec = Reg(Vec(21, SInt(8.W)))
  val l1OutVec = Reg(Vec(64, SInt(8.W)))
  val l2OutVec = Reg(Vec(32, SInt(8.W)))
  val logitsVec = Reg(Vec(2, SInt(32.W)))
  val l1RowReg = Reg(Vec(21, SInt(8.W)))
  val l2RowReg = Reg(Vec(64, SInt(8.W)))
  val l3RowReg = Reg(Vec(32, SInt(8.W)))

  val recvBeatCount = RegInit(0.U(3.W))

  val outIdx = RegInit(0.U(6.W))
  val inIdx = RegInit(0.U(7.W))
  val accReg = RegInit(0.S(32.W))
  val quantReg = Reg(SInt(8.W))

  val outValidReg = RegInit(false.B)
  val outBitsReg = Reg(new RadarAXISWord)

  val inBeatsReg = RegInit(0.U(32.W))
  val outBeatsReg = RegInit(0.U(32.W))
  val framesReg = RegInit(0.U(32.W))
  val lastKeepReg = RegInit(0.U(8.W))
  val runCyclesReg = RegInit(0.U(32.W))
  val lastLogit0Reg = RegInit(0.S(32.W))
  val lastLogit1Reg = RegInit(0.S(32.W))

  private val l1TileDone = (inIdx + peLanes.U) >= qmlp.l1In.U
  private val l2TileDone = (inIdx + peLanes.U) >= qmlp.l2In.U
  private val l3TileDone = (inIdx + peLanes.U) >= qmlp.l3In.U

  private val l1PartialSum = Wire(SInt(32.W))
  private val l2PartialSum = Wire(SInt(32.W))
  private val l3PartialSum = Wire(SInt(32.W))

  l1PartialSum := sumTree(Seq.tabulate(peLanes) { lane =>
    val idx = inIdx + lane.U(7.W)
    val valid = idx < qmlp.l1In.U
    val data = Mux(valid, inputVec(idx(4, 0)), 0.S(8.W))
    val weight = Mux(valid, l1RowReg(idx(4, 0)), 0.S(8.W))
    (data * weight).asSInt.pad(32)
  })

  l2PartialSum := sumTree(Seq.tabulate(peLanes) { lane =>
    val idx = inIdx + lane.U(7.W)
    val valid = idx < qmlp.l2In.U
    val data = Mux(valid, l1OutVec(idx(5, 0)), 0.S(8.W))
    val weight = Mux(valid, l2RowReg(idx(5, 0)), 0.S(8.W))
    (data * weight).asSInt.pad(32)
  })

  l3PartialSum := sumTree(Seq.tabulate(peLanes) { lane =>
    val idx = inIdx + lane.U(7.W)
    val valid = idx < qmlp.l3In.U
    val data = Mux(valid, l2OutVec(idx(4, 0)), 0.S(8.W))
    val weight = Mux(valid, l3RowReg(idx(4, 0)), 0.S(8.W))
    (data * weight).asSInt.pad(32)
  })

  when (io.clearCounters) {
    inBeatsReg := 0.U
    outBeatsReg := 0.U
    framesReg := 0.U
    lastKeepReg := 0.U
    runCyclesReg := 0.U
  }

  when (state =/= sIdle && state =/= sRecv && state =/= sEmit) {
    runCyclesReg := runCyclesReg + 1.U
  }

  io.in.ready := (state === sIdle || state === sRecv) && io.ctrlEnable
  io.out.valid := outValidReg
  io.out.bits := outBitsReg

  when (state === sIdle) {
    recvBeatCount := 0.U
    when (!io.ctrlEnable) {
      for (i <- 0 until 21) {
        inputVec(i) := 0.S
      }
    }
  }

  when (io.in.fire) {
    val baseByte = Cat(recvBeatCount(1, 0), 0.U(3.W))
    for (i <- 0 until 8) {
      val sampleIndex = (baseByte + i.U(5.W))(4, 0)
      when (io.in.bits.keep(i) && (baseByte + i.U(5.W)) < 21.U) {
        inputVec(sampleIndex) := io.in.bits.data(8 * i + 7, 8 * i).asSInt
      }
    }
    recvBeatCount := recvBeatCount + 1.U
    inBeatsReg := inBeatsReg + 1.U
    lastKeepReg := io.in.bits.keep
    when (io.in.bits.last) {
      framesReg := framesReg + 1.U
    }
    when (recvBeatCount === 3.U || io.in.bits.last) {
      state := sL1Load
      outIdx := 0.U
      inIdx := 0.U
    } .otherwise {
      state := sRecv
    }
  }

  when (state === sL1Load) {
    for (i <- 0 until qmlp.l1In) {
      l1RowReg(i) := l1Rows(outIdx)(i)
    }
    inIdx := 0.U
    accReg := l1Biases(outIdx)
    state := sL1Mac
  }

  when (state === sL1Mac) {
    val nextAcc = accReg + l1PartialSum
    when (l1TileDone) {
      accReg := nextAcc
      state := sL1Quant
    } .otherwise {
      accReg := nextAcc
      inIdx := inIdx + peLanes.U
    }
  }

  when (state === sL1Quant) {
    quantReg := requantReluClamp(accReg, qmlp.l1Multiplier).asUInt(7, 0).asSInt
    state := sL1Write
  }

  when (state === sL1Write) {
    l1OutVec(outIdx(5, 0)) := quantReg
    when (outIdx === (qmlp.l1Out - 1).U) {
      state := sL2Load
      outIdx := 0.U
    } .otherwise {
      outIdx := outIdx + 1.U
      state := sL1Load
    }
  }

  when (state === sL2Load) {
    for (i <- 0 until qmlp.l2In) {
      l2RowReg(i) := l2Rows(outIdx(4, 0))(i)
    }
    inIdx := 0.U
    accReg := l2Biases(outIdx(4, 0))
    state := sL2Mac
  }

  when (state === sL2Mac) {
    val nextAcc = accReg + l2PartialSum
    when (l2TileDone) {
      accReg := nextAcc
      state := sL2Quant
    } .otherwise {
      accReg := nextAcc
      inIdx := inIdx + peLanes.U
    }
  }

  when (state === sL2Quant) {
    quantReg := requantReluClamp(accReg, qmlp.l2Multiplier).asUInt(7, 0).asSInt
    state := sL2Write
  }

  when (state === sL2Write) {
    l2OutVec(outIdx(4, 0)) := quantReg
    when (outIdx === (qmlp.l2Out - 1).U) {
      state := sL3Load
      outIdx := 0.U
    } .otherwise {
      outIdx := outIdx + 1.U
      state := sL2Load
    }
  }

  when (state === sL3Load) {
    for (i <- 0 until qmlp.l3In) {
      l3RowReg(i) := l3Rows(outIdx(0))(i)
    }
    inIdx := 0.U
    accReg := l3Biases(outIdx(0))
    state := sL3Mac
  }

  when (state === sL3Mac) {
    val nextAcc = accReg + l3PartialSum
    when (l3TileDone) {
      accReg := nextAcc
      state := sL3Write
    } .otherwise {
      accReg := nextAcc
      inIdx := inIdx + peLanes.U
    }
  }

  when (state === sL3Write) {
    logitsVec(outIdx(0)) := accReg
    when (outIdx === (qmlp.l3Out - 1).U) {
      lastLogit0Reg := logitsVec(0)
      lastLogit1Reg := accReg
      state := sL3Pack
    } .otherwise {
      outIdx := outIdx + 1.U
      state := sL3Load
    }
  }

  when (state === sL3Pack) {
      outBitsReg.data := Cat(lastLogit1Reg.asUInt, lastLogit0Reg.asUInt)
      outBitsReg.keep := "hff".U
      outBitsReg.last := true.B
      outValidReg := true.B
      state := sEmit
  }

  when (io.out.fire) {
    outBeatsReg := outBeatsReg + 1.U
    outValidReg := false.B
    state := sIdle
  }

  io.inBeats := inBeatsReg
  io.outBeats := outBeatsReg
  io.frameCount := framesReg
  io.lastKeep := lastKeepReg
  io.runCycles := runCyclesReg
  io.lastLogit0 := lastLogit0Reg
  io.lastLogit1 := lastLogit1Reg
  io.status := Cat(
    0.U(22.W),
    outValidReg,
    io.out.ready,
    io.out.valid,
    io.in.ready,
    io.in.valid,
    io.ctrlEnable,
    state)
  io.capabilities := "h00000411".U
}
