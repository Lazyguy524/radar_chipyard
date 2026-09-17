package chipyard.radar

import chisel3._
import chisel3.util._
import freechips.rocketchip.util.ElaborationArtefacts
import org.chipsalliance.cde.config.{Config, Field}

import java.nio.charset.StandardCharsets
import java.nio.file.{Files, Paths}
import java.security.MessageDigest
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

final case class RadarQMLPArchitecture(peLanes: Int) {
  require(
    RadarQMLPArchitecture.supportedPELanes.contains(peLanes),
    s"Radar QMLP supports ${RadarQMLPArchitecture.supportedPELanes.toSeq.sorted.mkString("/")} PE lanes, got $peLanes")

  val contextCount = 2
  val weightWordWidth = peLanes * 8

  def weightWordsPerRow(inputCount: Int): Int =
    (inputCount + peLanes - 1) / peLanes

  def layerTiles(inputCount: Int, outputCount: Int): Int =
    weightWordsPerRow(inputCount) * outputCount

  def tilesPerSample(release: RadarQMLPReleaseData): Int =
    layerTiles(release.l1In, release.l1Out) +
      layerTiles(release.l2In, release.l2Out) +
      layerTiles(release.l3In, release.l3Out)

  // [31:16] tiles/sample, [15:8] contexts, [7:0] signed-int8 PE lanes.
  def archRegisterValue(release: RadarQMLPReleaseData): BigInt = {
    val tiles = tilesPerSample(release)
    require(tiles < (1 << 16), s"Radar QMLP tile count $tiles does not fit QMLP_ARCH")
    (BigInt(tiles) << 16) | (BigInt(contextCount) << 8) | BigInt(peLanes)
  }
}

object RadarQMLPArchitecture {
  val defaultPELanes = 4
  val supportedPELanes = Set(4, 8)
}

sealed trait RadarQMLPRomBackend {
  def manifestName: String
}

object RadarQMLPRomBackend {
  /** Preserve the established Vivado distributed-ROM implementation. */
  case object FpgaReadmemh extends RadarQMLPRomBackend {
    val manifestName = "fpga-readmemh"
  }

  /** Embed every ROM word in synthesizable RTL for portable VCS/DC handoff. */
  case object EmbeddedConstant extends RadarQMLPRomBackend {
    val manifestName = "embedded-constant"
  }
}

case object RadarQMLPRomBackendKey
    extends Field[RadarQMLPRomBackend](RadarQMLPRomBackend.FpgaReadmemh)

class WithRadarQMLPRomBackend(backend: RadarQMLPRomBackend)
    extends Config((site, here, up) => {
      case RadarQMLPRomBackendKey => backend
    })

class WithRadarQMLPEmbeddedConstantRom
    extends WithRadarQMLPRomBackend(RadarQMLPRomBackend.EmbeddedConstant)

final case class RadarQMLPRomImage(
  logicalName: String,
  moduleName: String,
  fileName: String,
  width: Int,
  values: Seq[BigInt]) {
  require(logicalName.nonEmpty, "QMLP ROM logical name must be non-empty")
  require(moduleName.nonEmpty, "QMLP ROM module name must be non-empty")
  require(fileName.nonEmpty, "QMLP ROM file name must be non-empty")
  require(width > 0, s"QMLP ROM $logicalName width must be positive")
  require(values.nonEmpty, s"QMLP ROM $logicalName must contain at least one word")

  val depth: Int = values.size
  val mask: BigInt = (BigInt(1) << width) - 1
  val hexDigits: Int = (width + 3) / 4

  require(values.forall(value => value >= 0 && value <= mask),
    s"QMLP ROM $logicalName contains a value wider than $width bits")

  def hexWord(value: BigInt): String =
    (value & mask).toString(16).reverse.padTo(hexDigits, '0').reverse

  lazy val hexBody: String = values.map(hexWord).mkString("\n") + "\n"
  lazy val sha256: String = RadarQMLPReleaseData.sha256Hex(
    hexBody.getBytes(StandardCharsets.US_ASCII))
}

object RadarQMLPReleaseData {
  val releaseRelativePath =
    "releases/input_convergence_k3_rcs21_20260406/rcs_fix_k7_rcs21_20260414/" +
      "Radar_mlp_binary_k7_rcs21_rcsfixParams.scala"

  private def locate(path: String): String = {
    val candidates = Seq(
      path,
      s"../$path",
      s"../../$path")
    candidates.find(p => Files.exists(Paths.get(p))).getOrElse {
      throw new IllegalArgumentException(s"Unable to locate QMLP release file: $path")
    }
  }

  private val releasePath = locate(releaseRelativePath)
  private val releaseBytes = Files.readAllBytes(Paths.get(releasePath))

  private def readReleaseText(): String = {
    val src = Source.fromFile(releasePath)
    try src.mkString finally src.close()
  }

  private val text = readReleaseText()

  def sha256Hex(bytes: Array[Byte]): String =
    MessageDigest.getInstance("SHA-256").digest(bytes).iterator
      .map(byte => f"${byte & 0xff}%02x")
      .mkString

  val releaseSourceSha256: String = sha256Hex(releaseBytes)

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

  private[radar] def twos(value: Int, width: Int): BigInt = {
    val modulus = BigInt(1) << width
    if (value < 0) modulus + BigInt(value) else BigInt(value)
  }

  private[radar] def packWeightWords(
    weights: Seq[Int],
    rows: Int,
    cols: Int,
    lanes: Int): Seq[BigInt] = {
    require(weights.size == rows * cols,
      s"QMLP weight shape mismatch: ${weights.size} values for $rows x $cols")
    RadarQMLPArchitecture(lanes)
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

  private def emitHexFile(image: RadarQMLPRomImage): String = {
    val dir = Paths.get("generated-src", "radar_qmlp_mem")
    Files.createDirectories(dir)
    val path = dir.resolve(image.fileName)
    val bytes = image.hexBody.getBytes(StandardCharsets.US_ASCII)
    if (!Files.exists(path) || !java.util.Arrays.equals(Files.readAllBytes(path), bytes)) {
      Files.write(path, bytes)
    }
    path.toAbsolutePath.toString
  }

  private def weightHexName(layer: String, peLanes: Int): String = {
    val laneSuffix = if (peLanes == RadarQMLPArchitecture.defaultPELanes) "" else s"_x$peLanes"
    s"qmlp_k7_${layer}_weight_words$laneSuffix.hex"
  }

  private def weightImage(
    layer: String,
    moduleBase: String,
    weights: Seq[Int],
    rows: Int,
    cols: Int,
    peLanes: Int): RadarQMLPRomImage = {
    val architecture = RadarQMLPArchitecture(peLanes)
    val moduleName =
      if (peLanes == RadarQMLPArchitecture.defaultPELanes) moduleBase else s"${moduleBase}X$peLanes"
    RadarQMLPRomImage(
      logicalName = s"${layer}_weight",
      moduleName = moduleName,
      fileName = weightHexName(layer, peLanes),
      width = architecture.weightWordWidth,
      values = packWeightWords(weights, rows, cols, peLanes))
  }

  private def biasImage(layer: String, moduleName: String, biases: Seq[Int]): RadarQMLPRomImage =
    RadarQMLPRomImage(
      logicalName = s"${layer}_bias",
      moduleName = moduleName,
      fileName = s"qmlp_k7_${layer}_bias.hex",
      width = 32,
      values = biases.map(value => twos(value, 32)))

  def romImages(peLanes: Int): Seq[RadarQMLPRomImage] = Seq(
    weightImage("l1", "RadarQMLPL1WeightRom", data.l1Weight, data.l1Out, data.l1In, peLanes),
    weightImage("l2", "RadarQMLPL2WeightRom", data.l2Weight, data.l2Out, data.l2In, peLanes),
    weightImage("l3", "RadarQMLPL3WeightRom", data.l3Weight, data.l3Out, data.l3In, peLanes),
    biasImage("l1", "RadarQMLPL1BiasRom", data.l1Bias),
    biasImage("l2", "RadarQMLPL2BiasRom", data.l2Bias),
    biasImage("l3", "RadarQMLPL3BiasRom", data.l3Bias))

  def emitFpgaHex(image: RadarQMLPRomImage): String = emitHexFile(image)

  def romManifestJson(peLanes: Int, backend: RadarQMLPRomBackend): String = {
    val entries = romImages(peLanes).map { image =>
      s"""    {"logical_name":"${image.logicalName}","module":"${image.moduleName}","canonical_hex":"${image.fileName}","depth":${image.depth},"width":${image.width},"sha256":"${image.sha256}"}"""
    }.mkString(",\n")
    s"""{
       |  "schema": 1,
       |  "model": "qmlp_k7_rcs21",
       |  "release_source": "$releaseRelativePath",
       |  "release_sha256": "$releaseSourceSha256",
       |  "pe_lanes": $peLanes,
       |  "backend": "${backend.manifestName}",
       |  "roms": [
       |$entries
       |  ]
       |}
       |""".stripMargin
  }

  def emitRomManifest(peLanes: Int, backend: RadarQMLPRomBackend): String = {
    val dir = Paths.get("generated-src", "radar_qmlp_mem")
    Files.createDirectories(dir)
    val path = dir.resolve(s"qmlp_k7_rom_manifest_x${peLanes}_${backend.manifestName}.json")
    val bytes = romManifestJson(peLanes, backend).getBytes(StandardCharsets.US_ASCII)
    if (!Files.exists(path) || !java.util.Arrays.equals(Files.readAllBytes(path), bytes)) {
      Files.write(path, bytes)
    }
    path.toAbsolutePath.toString
  }

  // Compatibility entry points retained for scripts that explicitly request the FPGA images.
  def l1WeightHex(peLanes: Int): String = emitFpgaHex(romImages(peLanes)(0))
  def l2WeightHex(peLanes: Int): String = emitFpgaHex(romImages(peLanes)(1))
  def l3WeightHex(peLanes: Int): String = emitFpgaHex(romImages(peLanes)(2))
  lazy val l1BiasHex: String = emitFpgaHex(romImages(RadarQMLPArchitecture.defaultPELanes)(3))
  lazy val l2BiasHex: String = emitFpgaHex(romImages(RadarQMLPArchitecture.defaultPELanes)(4))
  lazy val l3BiasHex: String = emitFpgaHex(romImages(RadarQMLPArchitecture.defaultPELanes)(5))
}

class RadarQMLPRomIO(depth: Int, width: Int) extends Bundle {
  private val addrWidth = math.max(1, log2Ceil(depth))
  val addr = Input(UInt(addrWidth.W))
  val data = Output(UInt(width.W))
}

abstract class RadarQMLPRomBlackBox(depth: Int, width: Int) extends BlackBox {
  val io = IO(new RadarQMLPRomIO(depth, width))
}

object RadarQMLPAsyncRom {
  def verilogSource(moduleName: String, depth: Int, width: Int, initFile: String): String = {
    val addrWidth = math.max(1, log2Ceil(depth))
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
       |""".stripMargin
  }
}

class RadarQMLPAsyncRom(moduleName: String, depth: Int, width: Int, initFile: String)
    extends RadarQMLPRomBlackBox(depth, width) with HasBlackBoxInline {
  override def desiredName: String = moduleName
  setInline(s"$moduleName.sv", RadarQMLPAsyncRom.verilogSource(moduleName, depth, width, initFile))
}

object RadarQMLPEmbeddedConstantRom {
  def verilogSource(image: RadarQMLPRomImage): String = {
    val addrWidth = math.max(1, log2Ceil(image.depth))
    val cases = image.values.zipWithIndex.map { case (value, address) =>
      s"      ${addrWidth}'d$address: data = ${image.width}'h${image.hexWord(value)};"
    }.mkString("\n")
    s"""module ${image.moduleName}(
       |  input  [${addrWidth - 1}:0] addr,
       |  output reg [${image.width - 1}:0] data
       |);
       |
       |  always @* begin
       |    case (addr)
       |$cases
       |      default: data = ${image.width}'h0;
       |    endcase
       |  end
       |endmodule
       |""".stripMargin
  }
}

class RadarQMLPEmbeddedConstantRom(image: RadarQMLPRomImage)
    extends RadarQMLPRomBlackBox(image.depth, image.width) with HasBlackBoxInline {
  override def desiredName: String = image.moduleName
  setInline(s"${image.moduleName}.sv", RadarQMLPEmbeddedConstantRom.verilogSource(image))
}

class RadarAXISQMLP(
  peLanes: Int = RadarQMLPArchitecture.defaultPELanes,
  romBackend: RadarQMLPRomBackend = RadarQMLPRomBackend.FpgaReadmemh) extends Module {
  private val qmlp = RadarQMLPReleaseData.data
  // Keep the established shift-add requant path while allowing the int8 PE
  // array and packed weight ROMs to scale together.
  private val architecture = RadarQMLPArchitecture(peLanes)
  private val l1WeightWordsPerRow = architecture.weightWordsPerRow(qmlp.l1In)
  private val l2WeightWordsPerRow = architecture.weightWordsPerRow(qmlp.l2In)
  private val l3WeightWordsPerRow = architecture.weightWordsPerRow(qmlp.l3In)
  private val axisBytes = 8
  private val inputWordCount = 4
  private val l1ActWordCount = (qmlp.l1Out + axisBytes - 1) / axisBytes
  private val l2ActWordCount = (qmlp.l2Out + axisBytes - 1) / axisBytes

  require(qmlp.l1Weight.size == qmlp.l1Out * qmlp.l1In, "L1 weight shape mismatch")
  require(qmlp.l2Weight.size == qmlp.l2Out * qmlp.l2In, "L2 weight shape mismatch")
  require(qmlp.l3Weight.size == qmlp.l3Out * qmlp.l3In, "L3 weight shape mismatch")
  require(qmlp.l3Out == 2, "Radar QMLP output packer expects two logits")

  private val contextCount = architecture.contextCount
  private val Seq(cEmpty, cRecv, cRun, cLayerWait, cDone) = Enum(5)
  private val Seq(layerL1, layerL2, layerL3) = Enum(3)

  val io = IO(new Bundle {
    val ctrlEnable = Input(Bool())
    val abort = Input(Bool())
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
    val architecture = Output(UInt(32.W))
    val sleepSafe = Output(Bool())
  })

  private def romAddrWidth(depth: Int): Int = math.max(1, log2Ceil(depth))
  private val romImages = RadarQMLPReleaseData.romImages(peLanes)
  private val romManifestArtifact =
    s"qmlp-k7-rom-x${peLanes}-${romBackend.manifestName}.json"
  if (!ElaborationArtefacts.contains(romManifestArtifact)) {
    ElaborationArtefacts.add(
      romManifestArtifact,
      RadarQMLPReleaseData.romManifestJson(peLanes, romBackend))
  }
  RadarQMLPReleaseData.emitRomManifest(peLanes, romBackend)

  private def makeRom(image: RadarQMLPRomImage): RadarQMLPRomBlackBox = {
    romBackend match {
      case RadarQMLPRomBackend.FpgaReadmemh =>
        Module(new RadarQMLPAsyncRom(
          image.moduleName,
          image.depth,
          image.width,
          RadarQMLPReleaseData.emitFpgaHex(image)))
      case RadarQMLPRomBackend.EmbeddedConstant =>
        Module(new RadarQMLPEmbeddedConstantRom(image))
    }
  }

  private val l1WeightRom = makeRom(romImages(0))
  private val l2WeightRom = makeRom(romImages(1))
  private val l3WeightRom = makeRom(romImages(2))
  private val l1BiasRom = makeRom(romImages(3))
  private val l2BiasRom = makeRom(romImages(4))
  private val l3BiasRom = makeRom(romImages(5))

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

  private def contextWords(words: Vec[Vec[UInt]], context: UInt): Vec[UInt] =
    VecInit((0 until words(0).length).map(i => words(context)(i)))

  val ctxState = RegInit(VecInit(Seq.fill(contextCount)(cEmpty)))
  val ctxLayer = RegInit(VecInit(Seq.fill(contextCount)(layerL1)))
  val ctxOutIdx = RegInit(VecInit(Seq.fill(contextCount)(0.U(6.W))))
  val ctxInIdx = RegInit(VecInit(Seq.fill(contextCount)(0.U(7.W))))
  val ctxAcc = RegInit(VecInit(Seq.fill(contextCount)(0.S(32.W))))
  val ctxSampleLast = RegInit(VecInit(Seq.fill(contextCount)(false.B)))
  val ctxInputWords = RegInit(VecInit(Seq.fill(contextCount)(
    VecInit(Seq.fill(inputWordCount)(0.U(64.W))))))
  val ctxL1OutWords = RegInit(VecInit(Seq.fill(contextCount)(
    VecInit(Seq.fill(l1ActWordCount)(0.U(64.W))))))
  val ctxL2OutWords = RegInit(VecInit(Seq.fill(contextCount)(
    VecInit(Seq.fill(l2ActWordCount)(0.U(64.W))))))
  val ctxLogit0 = RegInit(VecInit(Seq.fill(contextCount)(0.S(32.W))))
  val ctxLogit1 = RegInit(VecInit(Seq.fill(contextCount)(0.S(32.W))))

  val allocPtr = RegInit(0.U(1.W))
  val emitPtr = RegInit(0.U(1.W))
  val recvBeatCount = RegInit(0.U(2.W))
  val dropPacketReg = RegInit(false.B)
  val protocolErrorReg = RegInit(false.B)

  // An owner holds the issue stage for one complete neuron.  At the neuron
  // boundary the oldest runnable context gets priority, so another frame can
  // cover the first frame's layer-tail requant/write latency.
  val issueOwnerValidReg = RegInit(false.B)
  val issueOwnerCtxReg = RegInit(0.U(1.W))

  // Issue descriptor -> operand prep -> MAC is a true three-stage pipeline.
  // The scheduler never drives the async ROM address and operand mux directly.
  val issueDescValidReg = RegInit(false.B)
  val issueDescCtxReg = RegInit(0.U(1.W))
  val issueDescLayerReg = RegInit(layerL1)
  val issueDescOutIdxReg = RegInit(0.U(6.W))
  val issueDescInIdxReg = RegInit(0.U(7.W))
  val issueDescFirstTileReg = RegInit(false.B)
  val issueDescLastTileReg = RegInit(false.B)

  // The async ROM and activation mux feed only these operand registers; MAC
  // consumes the previous cycle's registered values.
  val macValidReg = RegInit(false.B)
  val macCtxReg = RegInit(0.U(1.W))
  val macLayerReg = RegInit(layerL1)
  val macOutIdxReg = RegInit(0.U(6.W))
  val macFirstTileReg = RegInit(false.B)
  val macLastTileReg = RegInit(false.B)
  val macBiasReg = RegInit(0.S(32.W))
  val macDataRegs = RegInit(VecInit(Seq.fill(peLanes)(0.S(8.W))))
  val macWeightRegs = RegInit(VecInit(Seq.fill(peLanes)(0.S(8.W))))

  // Completed neurons leave the MAC immediately and flow through an
  // independent completion pipeline.  This is what removes Quant/Write
  // bubbles from the shared MAC issue stream.
  val complete0ValidReg = RegInit(false.B)
  val complete0CtxReg = RegInit(0.U(1.W))
  val complete0LayerReg = RegInit(layerL1)
  val complete0OutIdxReg = RegInit(0.U(6.W))
  val complete0AccReg = RegInit(0.S(32.W))

  val complete1ValidReg = RegInit(false.B)
  val complete1CtxReg = RegInit(0.U(1.W))
  val complete1LayerReg = RegInit(layerL1)
  val complete1OutIdxReg = RegInit(0.U(6.W))
  val complete1ValueReg = RegInit(0.S(64.W))

  val complete2ValidReg = RegInit(false.B)
  val complete2CtxReg = RegInit(0.U(1.W))
  val complete2LayerReg = RegInit(layerL1)
  val complete2OutIdxReg = RegInit(0.U(6.W))
  val complete2ValueReg = RegInit(0.S(64.W))

  val inBeatsReg = RegInit(0.U(32.W))
  val outBeatsReg = RegInit(0.U(32.W))
  val framesReg = RegInit(0.U(32.W))
  val lastKeepReg = RegInit(0.U(8.W))
  val runCyclesReg = RegInit(0.U(32.W))
  val lastLogit0Reg = RegInit(0.S(32.W))
  val lastLogit1Reg = RegInit(0.S(32.W))

  val nextCtxState = WireDefault(ctxState)
  val nextCtxLayer = WireDefault(ctxLayer)
  val nextCtxOutIdx = WireDefault(ctxOutIdx)
  val nextCtxInIdx = WireDefault(ctxInIdx)
  val nextCtxAcc = WireDefault(ctxAcc)
  val nextCtxSampleLast = WireDefault(ctxSampleLast)
  val nextCtxInputWords = WireDefault(ctxInputWords)
  val nextCtxL1OutWords = WireDefault(ctxL1OutWords)
  val nextCtxL2OutWords = WireDefault(ctxL2OutWords)
  val nextCtxLogit0 = WireDefault(ctxLogit0)
  val nextCtxLogit1 = WireDefault(ctxLogit1)

  val nextAllocPtr = WireDefault(allocPtr)
  val nextEmitPtr = WireDefault(emitPtr)
  val nextRecvBeatCount = WireDefault(recvBeatCount)
  val nextDropPacket = WireDefault(dropPacketReg)
  val nextProtocolError = WireDefault(protocolErrorReg)
  val nextIssueOwnerValid = WireDefault(issueOwnerValidReg)
  val nextIssueOwnerCtx = WireDefault(issueOwnerCtxReg)

  val nextIssueDescValid = WireDefault(false.B)
  val nextIssueDescCtx = WireDefault(issueDescCtxReg)
  val nextIssueDescLayer = WireDefault(issueDescLayerReg)
  val nextIssueDescOutIdx = WireDefault(issueDescOutIdxReg)
  val nextIssueDescInIdx = WireDefault(issueDescInIdxReg)
  val nextIssueDescFirstTile = WireDefault(issueDescFirstTileReg)
  val nextIssueDescLastTile = WireDefault(issueDescLastTileReg)

  val nextMacValid = WireDefault(false.B)
  val nextMacCtx = WireDefault(macCtxReg)
  val nextMacLayer = WireDefault(macLayerReg)
  val nextMacOutIdx = WireDefault(macOutIdxReg)
  val nextMacFirstTile = WireDefault(macFirstTileReg)
  val nextMacLastTile = WireDefault(macLastTileReg)
  val nextMacBias = WireDefault(macBiasReg)
  val nextMacData = WireDefault(macDataRegs)
  val nextMacWeight = WireDefault(macWeightRegs)

  val nextComplete0Valid = WireDefault(false.B)
  val nextComplete0Ctx = WireDefault(complete0CtxReg)
  val nextComplete0Layer = WireDefault(complete0LayerReg)
  val nextComplete0OutIdx = WireDefault(complete0OutIdxReg)
  val nextComplete0Acc = WireDefault(complete0AccReg)

  val nextComplete1Valid = WireDefault(complete0ValidReg)
  val nextComplete1Ctx = WireDefault(complete0CtxReg)
  val nextComplete1Layer = WireDefault(complete0LayerReg)
  val nextComplete1OutIdx = WireDefault(complete0OutIdxReg)
  val nextComplete1Value = WireDefault(complete1ValueReg)

  val nextComplete2Valid = WireDefault(complete1ValidReg)
  val nextComplete2Ctx = WireDefault(complete1CtxReg)
  val nextComplete2Layer = WireDefault(complete1LayerReg)
  val nextComplete2OutIdx = WireDefault(complete1OutIdxReg)
  val nextComplete2Value = WireDefault(complete2ValueReg)

  val nextInBeats = WireDefault(inBeatsReg)
  val nextOutBeats = WireDefault(outBeatsReg)
  val nextFrames = WireDefault(framesReg)
  val nextLastKeep = WireDefault(lastKeepReg)
  val nextRunCycles = WireDefault(runCyclesReg)
  val nextLastLogit0 = WireDefault(lastLogit0Reg)
  val nextLastLogit1 = WireDefault(lastLogit1Reg)

  private val otherEmitPtr = ~emitPtr
  private val headRunnable = ctxState(emitPtr) === cRun
  private val otherRunnable =
    ctxState(otherEmitPtr) === cRun &&
      ctxLayer(otherEmitPtr) =/= layerL3
  private val ownerRunnable =
    issueOwnerValidReg &&
      ctxState(issueOwnerCtxReg) === cRun &&
      !(ctxLayer(issueOwnerCtxReg) === layerL3 && issueOwnerCtxReg =/= emitPtr)

  val issueValid = WireDefault(false.B)
  val issueCtx = WireDefault(emitPtr)
  when (ownerRunnable) {
    issueValid := true.B
    issueCtx := issueOwnerCtxReg
  } .elsewhen (headRunnable) {
    issueValid := true.B
    issueCtx := emitPtr
  } .elsewhen (otherRunnable) {
    issueValid := true.B
    issueCtx := otherEmitPtr
  }

  val issueLayer = ctxLayer(issueCtx)
  val issueOutIdx = ctxOutIdx(issueCtx)
  val issueInIdx = ctxInIdx(issueCtx)
  val issueLayerIn = MuxLookup(issueLayer, qmlp.l1In.U(7.W))(Seq(
    layerL2 -> qmlp.l2In.U(7.W),
    layerL3 -> qmlp.l3In.U(7.W)))
  val issueLayerOut = MuxLookup(issueLayer, qmlp.l1Out.U(7.W))(Seq(
    layerL2 -> qmlp.l2Out.U(7.W),
    layerL3 -> qmlp.l3Out.U(7.W)))
  val issueTileDone = (issueInIdx + peLanes.U) >= issueLayerIn
  val issueNeuronDone = issueOutIdx === (issueLayerOut - 1.U)

  val prepWordIdx = issueDescInIdxReg >> log2Ceil(peLanes)
  val prepLayerIn = MuxLookup(issueDescLayerReg, qmlp.l1In.U(7.W))(Seq(
    layerL2 -> qmlp.l2In.U(7.W),
    layerL3 -> qmlp.l3In.U(7.W)))
  val l1WeightAddr =
    issueDescOutIdxReg * l1WeightWordsPerRow.U(romAddrWidth(qmlp.l1Out * l1WeightWordsPerRow).W) + prepWordIdx
  val l2WeightAddr =
    issueDescOutIdxReg(4, 0) * l2WeightWordsPerRow.U(romAddrWidth(qmlp.l2Out * l2WeightWordsPerRow).W) + prepWordIdx
  val l3WeightAddr =
    issueDescOutIdxReg(0) * l3WeightWordsPerRow.U(romAddrWidth(qmlp.l3Out * l3WeightWordsPerRow).W) + prepWordIdx

  l1WeightRom.io.addr := l1WeightAddr
  l2WeightRom.io.addr := l2WeightAddr
  l3WeightRom.io.addr := l3WeightAddr
  l1BiasRom.io.addr := issueDescOutIdxReg
  l2BiasRom.io.addr := issueDescOutIdxReg(4, 0)
  l3BiasRom.io.addr := issueDescOutIdxReg(0)

  val prepWeightWord = MuxLookup(issueDescLayerReg, l1WeightRom.io.data)(Seq(
    layerL2 -> l2WeightRom.io.data,
    layerL3 -> l3WeightRom.io.data))
  val prepBias = MuxLookup(issueDescLayerReg, l1BiasRom.io.data.asSInt)(Seq(
    layerL2 -> l2BiasRom.io.data.asSInt,
    layerL3 -> l3BiasRom.io.data.asSInt))
  val prepInputWords = contextWords(ctxInputWords, issueDescCtxReg)
  val prepL1Words = contextWords(ctxL1OutWords, issueDescCtxReg)
  val prepL2Words = contextWords(ctxL2OutWords, issueDescCtxReg)

  val prepData = Wire(Vec(peLanes, SInt(8.W)))
  val prepWeight = Wire(Vec(peLanes, SInt(8.W)))
  for (lane <- 0 until peLanes) {
    val laneIdx = issueDescInIdxReg + lane.U
    val laneValid = laneIdx < prepLayerIn
    val laneData = MuxLookup(
      issueDescLayerReg,
      readS8WordBank(prepInputWords, laneIdx))(Seq(
        layerL2 -> readS8WordBank(prepL1Words, laneIdx),
        layerL3 -> readS8WordBank(prepL2Words, laneIdx)))
    prepData(lane) := Mux(laneValid, laneData, 0.S)
    prepWeight(lane) := Mux(laneValid, weightLane(prepWeightWord, lane), 0.S)
  }

  when (issueValid) {
    nextIssueDescValid := true.B
    nextIssueDescCtx := issueCtx
    nextIssueDescLayer := issueLayer
    nextIssueDescOutIdx := issueOutIdx
    nextIssueDescInIdx := issueInIdx
    nextIssueDescFirstTile := issueInIdx === 0.U
    nextIssueDescLastTile := issueTileDone

    nextIssueOwnerValid := !issueTileDone
    nextIssueOwnerCtx := issueCtx
    when (issueTileDone) {
      nextCtxInIdx(issueCtx) := 0.U
      when (issueNeuronDone) {
        nextCtxState(issueCtx) := cLayerWait
      } .otherwise {
        nextCtxOutIdx(issueCtx) := issueOutIdx + 1.U
      }
    } .otherwise {
      nextCtxInIdx(issueCtx) := issueInIdx + peLanes.U
    }
  } .otherwise {
    nextIssueOwnerValid := false.B
  }

  when (issueDescValidReg) {
    nextMacValid := true.B
    nextMacCtx := issueDescCtxReg
    nextMacLayer := issueDescLayerReg
    nextMacOutIdx := issueDescOutIdxReg
    nextMacFirstTile := issueDescFirstTileReg
    nextMacLastTile := issueDescLastTileReg
    nextMacBias := prepBias
    nextMacData := prepData
    nextMacWeight := prepWeight
  }

  val macPartialSum = sumTree(Seq.tabulate(peLanes) { lane =>
    (macDataRegs(lane) * macWeightRegs(lane)).asSInt.pad(32)
  })
  val macBase = Mux(macFirstTileReg, macBiasReg, ctxAcc(macCtxReg))
  val macAcc = fitSInt((macBase +& macPartialSum).asSInt, 32)

  when (macValidReg) {
    when (macLastTileReg) {
      nextComplete0Valid := true.B
      nextComplete0Ctx := macCtxReg
      nextComplete0Layer := macLayerReg
      nextComplete0OutIdx := macOutIdxReg
      nextComplete0Acc := macAcc
    } .otherwise {
      nextCtxAcc(macCtxReg) := macAcc
    }
  }

  val complete1Product = MuxLookup(
    complete0LayerReg,
    constMultiplyShiftAdd(complete0AccReg, qmlp.l1Multiplier, 64))(Seq(
      layerL2 -> constMultiplyShiftAdd(complete0AccReg, qmlp.l2Multiplier, 64),
      layerL3 -> complete0AccReg.pad(64)))
  when (complete0ValidReg) {
    nextComplete1Value := complete1Product
  }

  val complete2Rounded = Mux(
    complete1LayerReg === layerL3,
    complete1ValueReg,
    bankRoundShift(complete1ValueReg, qmlp.requantShift))
  when (complete1ValidReg) {
    nextComplete2Value := complete2Rounded
  }

  when (complete2ValidReg) {
    when (complete2LayerReg === layerL1) {
      nextCtxL1OutWords(complete2CtxReg) :=
        writeS8WordBank(
          ctxL1OutWords(complete2CtxReg),
          complete2OutIdxReg(5, 0),
          reluClamp8(complete2ValueReg))
      when (complete2OutIdxReg === (qmlp.l1Out - 1).U) {
        nextCtxLayer(complete2CtxReg) := layerL2
        nextCtxOutIdx(complete2CtxReg) := 0.U
        nextCtxInIdx(complete2CtxReg) := 0.U
        nextCtxState(complete2CtxReg) := cRun
      }
    } .elsewhen (complete2LayerReg === layerL2) {
      nextCtxL2OutWords(complete2CtxReg) :=
        writeS8WordBank(
          ctxL2OutWords(complete2CtxReg),
          complete2OutIdxReg(4, 0),
          reluClamp8(complete2ValueReg))
      when (complete2OutIdxReg === (qmlp.l2Out - 1).U) {
        nextCtxLayer(complete2CtxReg) := layerL3
        nextCtxOutIdx(complete2CtxReg) := 0.U
        nextCtxInIdx(complete2CtxReg) := 0.U
        nextCtxState(complete2CtxReg) := cRun
      }
    } .otherwise {
      val completedLogit = fitSInt(complete2ValueReg, 32)
      when (complete2OutIdxReg === 0.U) {
        nextCtxLogit0(complete2CtxReg) := completedLogit
      } .otherwise {
        nextCtxLogit1(complete2CtxReg) := completedLogit
        nextCtxState(complete2CtxReg) := cDone
      }
    }
  }

  val recvIsActive = ctxState(allocPtr) === cRecv
  val recvSlotFree = ctxState(allocPtr) === cEmpty || recvIsActive
  val recvBeatBase = Mux(recvIsActive, recvBeatCount, 0.U)
  val recvBaseWords = Wire(Vec(inputWordCount, UInt(64.W)))
  for (word <- 0 until inputWordCount) {
    recvBaseWords(word) := Mux(
      recvIsActive,
      ctxInputWords(allocPtr)(word),
      0.U)
  }
  val recvWordsAfterBeat = inputAfterBeat(recvBaseWords, io.in.bits, recvBeatBase)

  io.in.ready := io.ctrlEnable && (dropPacketReg || recvSlotFree)
  when (io.in.fire) {
    nextInBeats := inBeatsReg + 1.U
    nextLastKeep := io.in.bits.keep

    when (dropPacketReg) {
      when (io.in.bits.last) {
        nextDropPacket := false.B
        nextFrames := framesReg + 1.U
      }
    } .otherwise {
      val keepError = io.in.bits.keep =/= "hff".U
      val earlyLast = io.in.bits.last && recvBeatBase =/= 3.U
      when (keepError || earlyLast) {
        nextProtocolError := true.B
        nextCtxState(allocPtr) := cEmpty
        nextRecvBeatCount := 0.U
        nextDropPacket := !io.in.bits.last
        when (io.in.bits.last) {
          nextFrames := framesReg + 1.U
        }
      } .otherwise {
        nextCtxState(allocPtr) := cRecv
        nextCtxInputWords(allocPtr) := recvWordsAfterBeat
        when (recvBeatBase === 3.U) {
          nextCtxState(allocPtr) := cRun
          nextCtxLayer(allocPtr) := layerL1
          nextCtxOutIdx(allocPtr) := 0.U
          nextCtxInIdx(allocPtr) := 0.U
          nextCtxAcc(allocPtr) := 0.S
          nextCtxSampleLast(allocPtr) := io.in.bits.last
          nextCtxL1OutWords(allocPtr) := zeroWords(l1ActWordCount)
          nextCtxL2OutWords(allocPtr) := zeroWords(l2ActWordCount)
          nextCtxLogit0(allocPtr) := 0.S
          nextCtxLogit1(allocPtr) := 0.S
          nextAllocPtr := ~allocPtr
          nextRecvBeatCount := 0.U
          when (io.in.bits.last) {
            nextFrames := framesReg + 1.U
          }
        } .otherwise {
          nextRecvBeatCount := recvBeatBase + 1.U
        }
      }
    }
  }

  io.out.valid := ctxState(emitPtr) === cDone
  io.out.bits.data := Cat(ctxLogit1(emitPtr).asUInt, ctxLogit0(emitPtr).asUInt)
  io.out.bits.keep := "hff".U
  io.out.bits.last := ctxSampleLast(emitPtr)

  when (io.out.fire) {
    nextLastLogit0 := ctxLogit0(emitPtr)
    nextLastLogit1 := ctxLogit1(emitPtr)
    nextOutBeats := outBeatsReg + 1.U
    nextCtxState(emitPtr) := cEmpty
    nextEmitPtr := ~emitPtr
  }

  val computeBusy =
    ctxState.map(state => state === cRun || state === cLayerWait).reduce(_ || _) ||
      issueDescValidReg || macValidReg ||
      complete0ValidReg || complete1ValidReg || complete2ValidReg
  when (computeBusy) {
    nextRunCycles := runCyclesReg + 1.U
  }

  // Disabling the block is the local recovery operation for a partial or
  // aborted packet.  It flushes datapath state but deliberately preserves
  // counters/error evidence until clearCounters is requested.
  when (!io.ctrlEnable || io.abort) {
    for (context <- 0 until contextCount) {
      nextCtxState(context) := cEmpty
      nextCtxLayer(context) := layerL1
      nextCtxOutIdx(context) := 0.U
      nextCtxInIdx(context) := 0.U
      nextCtxAcc(context) := 0.S
      nextCtxSampleLast(context) := false.B
      nextCtxInputWords(context) := zeroWords(inputWordCount)
      nextCtxL1OutWords(context) := zeroWords(l1ActWordCount)
      nextCtxL2OutWords(context) := zeroWords(l2ActWordCount)
      nextCtxLogit0(context) := 0.S
      nextCtxLogit1(context) := 0.S
    }
    nextAllocPtr := 0.U
    nextEmitPtr := 0.U
    nextRecvBeatCount := 0.U
    nextDropPacket := false.B
    nextIssueOwnerValid := false.B
    nextIssueDescValid := false.B
    nextMacValid := false.B
    nextComplete0Valid := false.B
    nextComplete1Valid := false.B
    nextComplete2Valid := false.B
  }

  // Counter/error clear has final priority over same-cycle datapath events.
  when (io.clearCounters) {
    nextInBeats := 0.U
    nextOutBeats := 0.U
    nextFrames := 0.U
    nextLastKeep := 0.U
    nextRunCycles := 0.U
    nextProtocolError := false.B
  }

  ctxState := nextCtxState
  ctxLayer := nextCtxLayer
  ctxOutIdx := nextCtxOutIdx
  ctxInIdx := nextCtxInIdx
  ctxAcc := nextCtxAcc
  ctxSampleLast := nextCtxSampleLast
  ctxInputWords := nextCtxInputWords
  ctxL1OutWords := nextCtxL1OutWords
  ctxL2OutWords := nextCtxL2OutWords
  ctxLogit0 := nextCtxLogit0
  ctxLogit1 := nextCtxLogit1

  allocPtr := nextAllocPtr
  emitPtr := nextEmitPtr
  recvBeatCount := nextRecvBeatCount
  dropPacketReg := nextDropPacket
  protocolErrorReg := nextProtocolError
  issueOwnerValidReg := nextIssueOwnerValid
  issueOwnerCtxReg := nextIssueOwnerCtx

  issueDescValidReg := nextIssueDescValid
  issueDescCtxReg := nextIssueDescCtx
  issueDescLayerReg := nextIssueDescLayer
  issueDescOutIdxReg := nextIssueDescOutIdx
  issueDescInIdxReg := nextIssueDescInIdx
  issueDescFirstTileReg := nextIssueDescFirstTile
  issueDescLastTileReg := nextIssueDescLastTile

  macValidReg := nextMacValid
  macCtxReg := nextMacCtx
  macLayerReg := nextMacLayer
  macOutIdxReg := nextMacOutIdx
  macFirstTileReg := nextMacFirstTile
  macLastTileReg := nextMacLastTile
  macBiasReg := nextMacBias
  macDataRegs := nextMacData
  macWeightRegs := nextMacWeight

  complete0ValidReg := nextComplete0Valid
  complete0CtxReg := nextComplete0Ctx
  complete0LayerReg := nextComplete0Layer
  complete0OutIdxReg := nextComplete0OutIdx
  complete0AccReg := nextComplete0Acc
  complete1ValidReg := nextComplete1Valid
  complete1CtxReg := nextComplete1Ctx
  complete1LayerReg := nextComplete1Layer
  complete1OutIdxReg := nextComplete1OutIdx
  complete1ValueReg := nextComplete1Value
  complete2ValidReg := nextComplete2Valid
  complete2CtxReg := nextComplete2Ctx
  complete2LayerReg := nextComplete2Layer
  complete2OutIdxReg := nextComplete2OutIdx
  complete2ValueReg := nextComplete2Value

  inBeatsReg := nextInBeats
  outBeatsReg := nextOutBeats
  framesReg := nextFrames
  lastKeepReg := nextLastKeep
  runCyclesReg := nextRunCycles
  lastLogit0Reg := nextLastLogit0
  lastLogit1Reg := nextLastLogit1

  val engineBusy =
    ctxState.map(_ =/= cEmpty).reduce(_ || _) ||
      dropPacketReg || issueDescValidReg || macValidReg ||
      complete0ValidReg || complete1ValidReg || complete2ValidReg
  io.sleepSafe :=
    !engineBusy && !io.clearCounters && !io.abort && (!io.ctrlEnable || !io.in.valid)
  val statusLow = Mux(engineBusy, 1.U(5.W), 0.U(5.W))
  io.inBeats := inBeatsReg
  io.outBeats := outBeatsReg
  io.frameCount := framesReg
  io.lastKeep := lastKeepReg
  io.runCycles := runCyclesReg
  io.lastLogit0 := lastLogit0Reg
  io.lastLogit1 := lastLogit1Reg
  io.status :=
    statusLow |
      (io.in.ready.asUInt << 5) |
      (io.out.valid.asUInt << 6) |
      (protocolErrorReg.asUInt << 8) |
      (dropPacketReg.asUInt << 9) |
      (issueDescValidReg.asUInt << 10) |
      (macValidReg.asUInt << 11) |
      (complete0ValidReg.asUInt << 12) |
      (complete1ValidReg.asUInt << 13) |
      (complete2ValidReg.asUInt << 14)
  io.capabilities := "h00002411".U
  io.architecture := architecture.archRegisterValue(qmlp).U(32.W)
}
