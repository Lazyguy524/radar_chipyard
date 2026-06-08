package chipyard.fpga.nexysvideo

import chisel3._
import chisel3.util._

import java.nio.charset.StandardCharsets
import java.nio.file.{Files, Paths}
import scala.io.Source

case class RadarQMLPReleaseData(
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

object RadarQMLPReleaseData {
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
    val path = locate("releases/input_convergence_k3_rcs21_20260406/rcs_fix_k7_rcs21_20260414/Radar_mlp_binary_k7_rcs21_rcsfixParams.scala")
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

  val data: RadarQMLPReleaseData = RadarQMLPReleaseData(
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

  private def twos(value: Int, width: Int): BigInt = {
    val modulus = BigInt(1) << width
    if (value < 0) modulus + BigInt(value) else BigInt(value)
  }

  private def packWeightWords(weights: Seq[Int], rows: Int, cols: Int, lanes: Int): Seq[BigInt] = {
    val wordsPerRow = (cols + lanes - 1) / lanes
    (0 until rows).flatMap { row =>
      (0 until wordsPerRow).map { word =>
        (0 until lanes).foldLeft(BigInt(0)) { (acc, lane) =>
          val col = word * lanes + lane
          val value = if (col < cols) weights(row * cols + col) else 0
          acc | (twos(value, 8) << (8 * lane))
        }
      }
    }
  }

  private def emitHexFile(name: String, values: Seq[BigInt], width: Int): String = {
    val dir = Paths.get("generated-src", "radar_qmlp_mem")
    Files.createDirectories(dir)
    val path = dir.resolve(name)
    val mask = (BigInt(1) << width) - 1
    val digits = (width + 3) / 4
    val body = values.map { value =>
      val clipped = value & mask
      clipped.toString(16).reverse.padTo(digits, '0').reverse
    }.mkString("\n") + "\n"
    val bytes = body.getBytes(StandardCharsets.US_ASCII)
    if (!Files.exists(path) || !java.util.Arrays.equals(Files.readAllBytes(path), bytes)) {
      Files.write(path, bytes)
    }
    path.toAbsolutePath.toString
  }

  val peLanes = 4
  val l1WeightWordsPerRow: Int = (data.l1In + peLanes - 1) / peLanes
  val l2WeightWordsPerRow: Int = (data.l2In + peLanes - 1) / peLanes
  val l3WeightWordsPerRow: Int = (data.l3In + peLanes - 1) / peLanes

  lazy val l1WeightHex: String =
    emitHexFile("qmlp_k7_l1_weight_words.hex", packWeightWords(data.l1Weight, data.l1Out, data.l1In, peLanes), 32)
  lazy val l2WeightHex: String =
    emitHexFile("qmlp_k7_l2_weight_words.hex", packWeightWords(data.l2Weight, data.l2Out, data.l2In, peLanes), 32)
  lazy val l3WeightHex: String =
    emitHexFile("qmlp_k7_l3_weight_words.hex", packWeightWords(data.l3Weight, data.l3Out, data.l3In, peLanes), 32)
  lazy val l1BiasHex: String =
    emitHexFile("qmlp_k7_l1_bias.hex", data.l1Bias.map(v => twos(v, 32)), 32)
  lazy val l2BiasHex: String =
    emitHexFile("qmlp_k7_l2_bias.hex", data.l2Bias.map(v => twos(v, 32)), 32)
  lazy val l3BiasHex: String =
    emitHexFile("qmlp_k7_l3_bias.hex", data.l3Bias.map(v => twos(v, 32)), 32)
}

class RadarQMLPAsyncRom(moduleName: String, depth: Int, width: Int, initFile: String)
    extends BlackBox with HasBlackBoxInline {
  private val addrWidth = math.max(1, log2Ceil(depth))

  override def desiredName: String = moduleName

  val io = IO(new Bundle {
    val addr = Input(UInt(addrWidth.W))
    val data = Output(UInt(width.W))
  })

  setInline(
    s"$moduleName.sv",
    s"""module $moduleName(
       |  input  [${addrWidth - 1}:0] addr,
       |  output [${width - 1}:0] data
       |);
       |
       |  (* rom_style = "distributed" *) reg [${width - 1}:0] Memory [0:${depth - 1}];
       |
       |  initial begin
       |    $$readmemh("$initFile", Memory);
       |  end
       |
       |  assign data = Memory[addr];
       |endmodule
       |""".stripMargin)
}

class RadarAXISQMLP extends Module {
  private val qmlp = RadarQMLPReleaseData.data
  // v2.5: keep the 4-lane PE array, but replace small constant requant
  // multiplies with shift-add logic to reduce DSP/layout disturbance.
  private val peLanes = RadarQMLPReleaseData.peLanes
  private val l1WeightWordsPerRow = RadarQMLPReleaseData.l1WeightWordsPerRow
  private val l2WeightWordsPerRow = RadarQMLPReleaseData.l2WeightWordsPerRow
  private val l3WeightWordsPerRow = RadarQMLPReleaseData.l3WeightWordsPerRow
  private val axisBytes = 8
  private val inputWordCount = 4
  private val l1ActWordCount = (qmlp.l1Out + axisBytes - 1) / axisBytes
  private val l2ActWordCount = (qmlp.l2Out + axisBytes - 1) / axisBytes

  require(qmlp.l1Weight.size == qmlp.l1Out * qmlp.l1In, "L1 weight shape mismatch")
  require(qmlp.l2Weight.size == qmlp.l2Out * qmlp.l2In, "L2 weight shape mismatch")
  require(qmlp.l3Weight.size == qmlp.l3Out * qmlp.l3In, "L3 weight shape mismatch")
  require(qmlp.l3Out == 2, "Radar QMLP output packer expects two logits")

  private val Seq(
    sIdle, sRecv,
    sL1Load, sL1Prep, sL1Mac, sL1QuantMul, sL1QuantRound, sL1Write,
    sL2Load, sL2Prep, sL2Mac, sL2QuantMul, sL2QuantRound, sL2Write,
    sL3Load, sL3Prep, sL3Mac, sL3Write, sL3Pack,
    sEmit) = Enum(20)

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

  private def romAddrWidth(depth: Int): Int = math.max(1, log2Ceil(depth))
  private def makeRom(name: String, depth: Int, initFile: String): RadarQMLPAsyncRom = {
    Module(new RadarQMLPAsyncRom(name, depth, 32, initFile))
  }

  private val l1WeightRom = makeRom("RadarQMLPL1WeightRom", qmlp.l1Out * l1WeightWordsPerRow, RadarQMLPReleaseData.l1WeightHex)
  private val l2WeightRom = makeRom("RadarQMLPL2WeightRom", qmlp.l2Out * l2WeightWordsPerRow, RadarQMLPReleaseData.l2WeightHex)
  private val l3WeightRom = makeRom("RadarQMLPL3WeightRom", qmlp.l3Out * l3WeightWordsPerRow, RadarQMLPReleaseData.l3WeightHex)
  private val l1BiasRom = makeRom("RadarQMLPL1BiasRom", qmlp.l1Out, RadarQMLPReleaseData.l1BiasHex)
  private val l2BiasRom = makeRom("RadarQMLPL2BiasRom", qmlp.l2Out, RadarQMLPReleaseData.l2BiasHex)
  private val l3BiasRom = makeRom("RadarQMLPL3BiasRom", qmlp.l3Out, RadarQMLPReleaseData.l3BiasHex)

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

  private def reluClamp8(value: SInt): SInt = {
    val relu = Mux(value < 0.S, 0.S, value)
    Mux(relu > 127.S, 127.S, relu)
  }

  private def constMultiplyShiftAdd(value: SInt, constant: Int, outWidth: Int): SInt = {
    require(constant >= 0, "Only non-negative requant multipliers are supported")
    if (constant == 0) {
      0.S(outWidth.W)
    } else {
      val termSeq = (0 until 32).collect {
        case shift if ((constant >> shift) & 1) == 1 =>
          fitSInt((value << shift).asSInt, outWidth)
      }
      balancedFixedWidthSum(termSeq, outWidth)
    }
  }

  private def fitSInt(value: SInt, width: Int): SInt =
    value.pad(width).asUInt(width - 1, 0).asSInt

  private def balancedFixedWidthSum(values: Seq[SInt], outWidth: Int): SInt = {
    require(values.nonEmpty, "Cannot sum an empty sequence")
    if (values.length == 1) {
      fitSInt(values.head, outWidth)
    } else {
      val next = values.grouped(2).map {
        case Seq(a, b) => fitSInt((a +& b).asSInt, outWidth)
        case Seq(a) => fitSInt(a, outWidth)
      }.toSeq
      balancedFixedWidthSum(next, outWidth)
    }
  }

  private def sumTree(values: Seq[SInt]): SInt = {
    require(values.nonEmpty, "Cannot sum an empty sequence")
    if (values.length == 1) {
      values.head
    } else {
      val next = values.grouped(2).map {
        case Seq(a, b) => (a +& b).asSInt
        case Seq(a) => a
      }.toSeq
      sumTree(next)
    }
  }

  private def zeroWords(count: Int): Vec[UInt] = VecInit(Seq.fill(count)(0.U(64.W)))

  private def replaceWordByte(word: UInt, byteIdx: UInt, byte: UInt): UInt = {
    val shift = byteIdx << 3
    val mask = (255.U(64.W) << shift)(63, 0)
    val byteWide = Cat(0.U(56.W), byte(7, 0))
    ((word & ~mask) | ((byteWide << shift)(63, 0))).asUInt
  }

  private def mergeAxisWord(current: UInt, beat: RadarAXISWord): UInt = {
    Cat((0 until axisBytes).reverse.map { lane =>
      Mux(beat.keep(lane), beat.data(8 * lane + 7, 8 * lane), current(8 * lane + 7, 8 * lane))
    })
  }

  private def writeWordBank(current: Vec[UInt], wordIdx: UInt, word: UInt): Vec[UInt] = {
    VecInit(Seq.tabulate(current.length) { i =>
      Mux(wordIdx === i.U, word, current(i))
    })
  }

  private def inputAfterBeat(current: Vec[UInt], beat: RadarAXISWord, beatBase: UInt): Vec[UInt] = {
    val wordIdx = beatBase(1, 0)
    writeWordBank(current, wordIdx, mergeAxisWord(current(wordIdx), beat))
  }

  private def readS8WordBank(current: Vec[UInt], idx: UInt): SInt = {
    val bankWidth = math.max(1, log2Ceil(current.length))
    val wordIdx = (idx >> 3)(bankWidth - 1, 0)
    val byteIdx = idx(2, 0)
    ((current(wordIdx) >> (byteIdx << 3))(7, 0)).asSInt
  }

  private def writeS8WordBank(current: Vec[UInt], idx: UInt, value: SInt): Vec[UInt] = {
    val bankWidth = math.max(1, log2Ceil(current.length))
    val wordIdx = (idx >> 3)(bankWidth - 1, 0)
    val byteValue = value.asUInt(7, 0).asSInt
    writeWordBank(current, wordIdx, replaceWordByte(current(wordIdx), idx(2, 0), byteValue.asUInt))
  }

  private def weightLane(word: UInt, lane: Int): SInt = {
    word(8 * lane + 7, 8 * lane).asSInt
  }

  private def weightWordIndex: UInt = inIdx >> log2Ceil(peLanes)

  val state = RegInit(sIdle)
  val inputWords = RegInit(zeroWords(inputWordCount))
  val l1OutWords = RegInit(zeroWords(l1ActWordCount))
  val l2OutWords = RegInit(zeroWords(l2ActWordCount))
  val pendingLogit0Reg = RegInit(0.S(32.W))

  val recvBeatCount = RegInit(0.U(3.W))
  val sampleLastReg = RegInit(false.B)

  val outIdx = RegInit(0.U(6.W))
  val inIdx = RegInit(0.U(7.W))
  val accReg = RegInit(0.S(32.W))
  val biasStageReg = RegInit(0.S(32.W))
  val macDataRegs = RegInit(VecInit(Seq.fill(peLanes)(0.S(8.W))))
  val macWeightRegs = RegInit(VecInit(Seq.fill(peLanes)(0.S(8.W))))
  val quantProductReg = Reg(SInt(64.W))
  val quantRoundedReg = Reg(SInt(64.W))

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
  private val recvBeatBase = Mux(state === sIdle, 0.U, recvBeatCount)

  private val l1WeightAddr = outIdx * l1WeightWordsPerRow.U(romAddrWidth(qmlp.l1Out * l1WeightWordsPerRow).W) + weightWordIndex
  private val l2WeightAddr = outIdx(4, 0) * l2WeightWordsPerRow.U(romAddrWidth(qmlp.l2Out * l2WeightWordsPerRow).W) + weightWordIndex
  private val l3WeightAddr = outIdx(0) * l3WeightWordsPerRow.U(romAddrWidth(qmlp.l3Out * l3WeightWordsPerRow).W) + weightWordIndex

  l1WeightRom.io.addr := l1WeightAddr
  l2WeightRom.io.addr := l2WeightAddr
  l3WeightRom.io.addr := l3WeightAddr
  l1BiasRom.io.addr := outIdx
  l2BiasRom.io.addr := outIdx(4, 0)
  l3BiasRom.io.addr := outIdx(0)

  private val l1WeightWord = l1WeightRom.io.data
  private val l2WeightWord = l2WeightRom.io.data
  private val l3WeightWord = l3WeightRom.io.data
  private val l1Bias = l1BiasRom.io.data.asSInt
  private val l2Bias = l2BiasRom.io.data.asSInt
  private val l3Bias = l3BiasRom.io.data.asSInt

  private def layerDataLanes(words: Vec[UInt], layerIn: Int): Vec[SInt] = {
    val lanes = Wire(Vec(peLanes, SInt(8.W)))
    for (lane <- 0 until peLanes) {
      val idx = inIdx + lane.U(7.W)
      val valid = idx < layerIn.U
      lanes(lane) := Mux(valid, readS8WordBank(words, idx), 0.S(8.W))
    }
    lanes
  }

  private def layerWeightLanes(weightWord: UInt, layerIn: Int): Vec[SInt] = {
    val lanes = Wire(Vec(peLanes, SInt(8.W)))
    for (lane <- 0 until peLanes) {
      val idx = inIdx + lane.U(7.W)
      val valid = idx < layerIn.U
      lanes(lane) := Mux(valid, weightLane(weightWord, lane), 0.S(8.W))
    }
    lanes
  }

  private val l1StageData = layerDataLanes(inputWords, qmlp.l1In)
  private val l2StageData = layerDataLanes(l1OutWords, qmlp.l2In)
  private val l3StageData = layerDataLanes(l2OutWords, qmlp.l3In)
  private val l1StageWeight = layerWeightLanes(l1WeightWord, qmlp.l1In)
  private val l2StageWeight = layerWeightLanes(l2WeightWord, qmlp.l2In)
  private val l3StageWeight = layerWeightLanes(l3WeightWord, qmlp.l3In)

  private val macPartialSum = sumTree(Seq.tabulate(peLanes) { lane =>
    (macDataRegs(lane) * macWeightRegs(lane)).asSInt.pad(32)
  })

  io.in.ready := (state === sIdle || state === sRecv) && io.ctrlEnable
  io.out.valid := outValidReg
  io.out.bits := outBitsReg

  val nextState = WireDefault(state)
  val nextRecvBeatCount = WireDefault(recvBeatCount)
  val nextSampleLast = WireDefault(sampleLastReg)
  val nextOutIdx = WireDefault(outIdx)
  val nextInIdx = WireDefault(inIdx)
  val nextAcc = WireDefault(accReg)
  val nextBiasStage = WireDefault(biasStageReg)
  val nextMacData = WireDefault(macDataRegs)
  val nextMacWeight = WireDefault(macWeightRegs)
  val nextQuantProduct = WireDefault(quantProductReg)
  val nextQuantRounded = WireDefault(quantRoundedReg)
  val nextOutValid = WireDefault(outValidReg)
  val nextOutBits = WireDefault(outBitsReg)
  val nextInputWords = WireDefault(inputWords)
  val nextL1OutWords = WireDefault(l1OutWords)
  val nextL2OutWords = WireDefault(l2OutWords)
  val nextPendingLogit0 = WireDefault(pendingLogit0Reg)
  val nextInBeats = WireDefault(inBeatsReg)
  val nextOutBeats = WireDefault(outBeatsReg)
  val nextFrames = WireDefault(framesReg)
  val nextLastKeep = WireDefault(lastKeepReg)
  val nextRunCycles = WireDefault(runCyclesReg)
  val nextLastLogit0 = WireDefault(lastLogit0Reg)
  val nextLastLogit1 = WireDefault(lastLogit1Reg)

  when (io.clearCounters) {
    nextInBeats := 0.U
    nextOutBeats := 0.U
    nextFrames := 0.U
    nextLastKeep := 0.U
    nextRunCycles := 0.U
  }

  when (state =/= sIdle && state =/= sRecv && state =/= sEmit) {
    nextRunCycles := runCyclesReg + 1.U
  }

  switch (state) {
    is (sIdle) {
      nextRecvBeatCount := 0.U
      nextSampleLast := false.B
      when (!io.ctrlEnable) {
        nextInputWords := zeroWords(inputWordCount)
      }
      when (io.in.fire) {
        nextInputWords := inputAfterBeat(inputWords, io.in.bits, recvBeatBase)
        nextRecvBeatCount := recvBeatBase + 1.U
        nextInBeats := inBeatsReg + 1.U
        nextLastKeep := io.in.bits.keep
        when (io.in.bits.last) {
          nextFrames := framesReg + 1.U
        }
        when (recvBeatBase === 3.U || io.in.bits.last) {
          nextSampleLast := io.in.bits.last
          nextState := sL1Load
          nextOutIdx := 0.U
          nextInIdx := 0.U
        } .otherwise {
          nextState := sRecv
        }
      }
    }

    is (sRecv) {
      when (io.in.fire) {
        nextInputWords := inputAfterBeat(inputWords, io.in.bits, recvBeatBase)
        nextRecvBeatCount := recvBeatBase + 1.U
        nextInBeats := inBeatsReg + 1.U
        nextLastKeep := io.in.bits.keep
        when (io.in.bits.last) {
          nextFrames := framesReg + 1.U
        }
        when (recvBeatBase === 3.U || io.in.bits.last) {
          nextSampleLast := io.in.bits.last
          nextState := sL1Load
          nextOutIdx := 0.U
          nextInIdx := 0.U
        }
      }
    }

    is (sL1Load) {
      nextInIdx := 0.U
      nextBiasStage := l1Bias
      nextState := sL1Prep
    }

    is (sL1Prep) {
      nextMacData := l1StageData
      nextMacWeight := l1StageWeight
      when (inIdx === 0.U) {
        nextAcc := biasStageReg
      }
      nextState := sL1Mac
    }

    is (sL1Mac) {
      val macAcc = accReg + macPartialSum
      nextAcc := macAcc
      when (l1TileDone) {
        nextState := sL1QuantMul
      } .otherwise {
        nextInIdx := inIdx + peLanes.U
        nextState := sL1Prep
      }
    }

    is (sL1QuantMul) {
      nextQuantProduct := constMultiplyShiftAdd(accReg, qmlp.l1Multiplier, 64)
      nextState := sL1QuantRound
    }

    is (sL1QuantRound) {
      nextQuantRounded := bankRoundShift(quantProductReg, qmlp.requantShift)
      nextState := sL1Write
    }

    is (sL1Write) {
      nextL1OutWords := writeS8WordBank(l1OutWords, outIdx(5, 0), reluClamp8(quantRoundedReg))
      when (outIdx === (qmlp.l1Out - 1).U) {
        nextState := sL2Load
        nextOutIdx := 0.U
      } .otherwise {
        nextOutIdx := outIdx + 1.U
        nextState := sL1Load
      }
    }

    is (sL2Load) {
      nextInIdx := 0.U
      nextBiasStage := l2Bias
      nextState := sL2Prep
    }

    is (sL2Prep) {
      nextMacData := l2StageData
      nextMacWeight := l2StageWeight
      when (inIdx === 0.U) {
        nextAcc := biasStageReg
      }
      nextState := sL2Mac
    }

    is (sL2Mac) {
      val macAcc = accReg + macPartialSum
      nextAcc := macAcc
      when (l2TileDone) {
        nextState := sL2QuantMul
      } .otherwise {
        nextInIdx := inIdx + peLanes.U
        nextState := sL2Prep
      }
    }

    is (sL2QuantMul) {
      nextQuantProduct := constMultiplyShiftAdd(accReg, qmlp.l2Multiplier, 64)
      nextState := sL2QuantRound
    }

    is (sL2QuantRound) {
      nextQuantRounded := bankRoundShift(quantProductReg, qmlp.requantShift)
      nextState := sL2Write
    }

    is (sL2Write) {
      nextL2OutWords := writeS8WordBank(l2OutWords, outIdx(4, 0), reluClamp8(quantRoundedReg))
      when (outIdx === (qmlp.l2Out - 1).U) {
        nextState := sL3Load
        nextOutIdx := 0.U
      } .otherwise {
        nextOutIdx := outIdx + 1.U
        nextState := sL2Load
      }
    }

    is (sL3Load) {
      nextInIdx := 0.U
      nextBiasStage := l3Bias
      nextState := sL3Prep
    }

    is (sL3Prep) {
      nextMacData := l3StageData
      nextMacWeight := l3StageWeight
      when (inIdx === 0.U) {
        nextAcc := biasStageReg
      }
      nextState := sL3Mac
    }

    is (sL3Mac) {
      val macAcc = accReg + macPartialSum
      nextAcc := macAcc
      when (l3TileDone) {
        nextState := sL3Write
      } .otherwise {
        nextInIdx := inIdx + peLanes.U
        nextState := sL3Prep
      }
    }

    is (sL3Write) {
      when (outIdx === 0.U) {
        nextPendingLogit0 := accReg
        nextOutIdx := 1.U
        nextState := sL3Load
      } .otherwise {
        nextLastLogit0 := pendingLogit0Reg
        nextLastLogit1 := accReg
        nextState := sL3Pack
      }
    }

    is (sL3Pack) {
      nextOutBits.data := Cat(lastLogit1Reg.asUInt, lastLogit0Reg.asUInt)
      nextOutBits.keep := "hff".U
      nextOutBits.last := sampleLastReg
      nextOutValid := true.B
      nextState := sEmit
    }

    is (sEmit) {
      when (io.out.fire) {
        nextOutBeats := outBeatsReg + 1.U
        nextOutValid := false.B
        nextState := sIdle
      }
    }
  }

  state := nextState
  recvBeatCount := nextRecvBeatCount
  sampleLastReg := nextSampleLast
  outIdx := nextOutIdx
  inIdx := nextInIdx
  accReg := nextAcc
  biasStageReg := nextBiasStage
  macDataRegs := nextMacData
  macWeightRegs := nextMacWeight
  quantProductReg := nextQuantProduct
  quantRoundedReg := nextQuantRounded
  outValidReg := nextOutValid
  outBitsReg := nextOutBits
  inputWords := nextInputWords
  l1OutWords := nextL1OutWords
  l2OutWords := nextL2OutWords
  pendingLogit0Reg := nextPendingLogit0
  inBeatsReg := nextInBeats
  outBeatsReg := nextOutBeats
  framesReg := nextFrames
  lastKeepReg := nextLastKeep
  runCyclesReg := nextRunCycles
  lastLogit0Reg := nextLastLogit0
  lastLogit1Reg := nextLastLogit1

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
