package chipyard.fpga.nexysvideo

import chisel3._
import chisel3.util._
import freechips.rocketchip.amba.axi4._
import freechips.rocketchip.diplomacy._
import freechips.rocketchip.util.ElaborationArtefacts
import org.chipsalliance.cde.config.Parameters

case class RadarAXIDMAControlParams(addrBits: Int = 31, dataBits: Int = 64, idBits: Int = 4) {
  require(dataBits == 64, "Radar AXI DMA control bridge assumes a 64-bit AXI4 MMIO bus")
}

class RadarAXI4LiteMasterIO(addrBits: Int) extends Bundle {
  val awvalid = Output(Bool())
  val awready = Input(Bool())
  val awaddr  = Output(UInt(addrBits.W))

  val wvalid = Output(Bool())
  val wready = Input(Bool())
  val wdata  = Output(UInt(32.W))
  val wstrb  = Output(UInt(4.W))

  val bvalid = Input(Bool())
  val bready = Output(Bool())
  val bresp  = Input(UInt(2.W))

  val arvalid = Output(Bool())
  val arready = Input(Bool())
  val araddr  = Output(UInt(addrBits.W))

  val rvalid = Input(Bool())
  val rready = Output(Bool())
  val rdata  = Input(UInt(32.W))
  val rresp  = Input(UInt(2.W))
}

class RadarLocalCSRPort(addrBits: Int) extends Bundle {
  val wrEn   = Output(Bool())
  val wrAddr = Output(UInt(addrBits.W))
  val wrData = Output(UInt(32.W))
  val wrStrb = Output(UInt(4.W))
  val wrResp = Input(UInt(2.W))

  val rdEn   = Output(Bool())
  val rdAddr = Output(UInt(addrBits.W))
  val rdData = Input(UInt(32.W))
  val rdResp = Input(UInt(2.W))
}

class RadarAXI4ToAXI4LiteBridge(params: RadarAXIDMAControlParams, liteAddrBits: Int = 10, localAddrBits: Int = 8) extends Module {
  private val full = AXI4BundleParameters(
    addrBits = params.addrBits,
    dataBits = params.dataBits,
    idBits   = params.idBits)
  private val wordSize = log2Ceil(4).U

  val io = IO(new Bundle {
    val in   = Flipped(new AXI4Bundle(full))
    val lite = new RadarAXI4LiteMasterIO(liteAddrBits)
    val local = new RadarLocalCSRPort(localAddrBits)
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
  val writeToLocal = awAddrReg(liteAddrBits - 1, localAddrBits) === 2.U
  val writeLiteForward = writeForward && !writeToLocal
  val writeLocalForward = writeForward && writeToLocal

  val readForward = arLenReg === 0.U &&
    arSizeReg === wordSize &&
    arAddrReg(1, 0) === 0.U
  val steeredReadData = Mux(arAddrReg(2), Cat(io.lite.rdata, 0.U(32.W)), Cat(0.U(32.W), io.lite.rdata))
  val readToLocal = arAddrReg(liteAddrBits - 1, localAddrBits) === 2.U
  val readLiteForward = readForward && !readToLocal
  val readLocalForward = readForward && readToLocal
  val steeredLocalReadData = Mux(arAddrReg(2), Cat(io.local.rdData, 0.U(32.W)), Cat(0.U(32.W), io.local.rdData))

  io.in.aw.ready := false.B
  io.in.w.ready  := false.B
  io.in.ar.ready := false.B

  io.local.wrEn := false.B
  io.local.wrAddr := awAddrReg(localAddrBits - 1, 0)
  io.local.wrData := liteWriteData
  io.local.wrStrb := liteWriteStrb
  io.local.rdEn := false.B
  io.local.rdAddr := arAddrReg(localAddrBits - 1, 0)

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

  io.lite.awvalid := state === sWriteIssue && writeLiteForward && awCaptured && !awIssued
  io.lite.awaddr  := awAddrReg(liteAddrBits - 1, 0)
  io.lite.wvalid  := state === sWriteIssue && writeLiteForward && wCaptured && !wIssued
  io.lite.wdata   := liteWriteData
  io.lite.wstrb   := liteWriteStrb
  io.lite.bready  := state === sWriteIssue && writeLiteForward && !bRespValid

  io.lite.arvalid := state === sReadIssue && readLiteForward && !arIssued
  io.lite.araddr  := arAddrReg(liteAddrBits - 1, 0)
  io.lite.rready  := state === sReadIssue && readLiteForward && !rRespValid

  switch (state) {
    is (sIdle) {
      when (io.in.aw.valid || io.in.w.valid) {
        io.in.aw.ready := true.B
        io.in.w.ready := true.B

        val gotAw = io.in.aw.valid
        val gotW = io.in.w.valid

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

        state := Mux(gotAw && gotW, sWriteIssue, sWriteCollect)
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
      val awHandshake = io.lite.awvalid && io.lite.awready
      val wHandshake = io.lite.wvalid && io.lite.wready
      val nextAwIssued = awIssued || awHandshake
      val nextWIssued = wIssued || wHandshake
      val canCaptureB = !bRespValid && writeLiteForward && nextAwIssued && nextWIssued && io.lite.bvalid

      when (awHandshake) { awIssued := true.B }
      when (wHandshake) { wIssued := true.B }

      when (!writeForward && !bRespValid) {
        bRespReg := AXI4Parameters.RESP_SLVERR
        bRespValid := true.B
        state := sWriteResp
      } .elsewhen (writeLocalForward && !bRespValid) {
        io.local.wrEn := true.B
        bRespReg := io.local.wrResp
        bRespValid := true.B
        state := sWriteResp
      } .elsewhen (canCaptureB) {
        bRespReg := io.lite.bresp
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
      val arHandshake = io.lite.arvalid && io.lite.arready
      val nextArIssued = arIssued || arHandshake
      val canCaptureR = !rRespValid && readLiteForward && nextArIssued && io.lite.rvalid

      when (arHandshake) { arIssued := true.B }

      when (!readForward && !rRespValid) {
        rDataReg := 0.U
        rRespReg := AXI4Parameters.RESP_SLVERR
        rRespValid := true.B
        state := sReadResp
      } .elsewhen (readLocalForward && !rRespValid) {
        io.local.rdEn := true.B
        rDataReg := steeredLocalReadData
        rRespReg := io.local.rdResp
        rRespValid := true.B
        state := sReadResp
      } .elsewhen (canCaptureR) {
        rDataReg := steeredReadData
        rRespReg := io.lite.rresp
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

object RadarAXISPreprocMode {
  val bypass   = 0.U(3.W)
  val add32    = 1.U(3.W)
  val shift16  = 2.U(3.W)
  val relu16   = 3.U(3.W)
  val swap32   = 4.U(3.W)
  val feature21 = 5.U(3.W)
}

class RadarAXISWord extends Bundle {
  val data = UInt(64.W)
  val keep = UInt(8.W)
  val last = Bool()
}

class RadarAXISPreprocessor extends Module {
  val io = IO(new Bundle {
    val ctrlEnable = Input(Bool())
    val mode       = Input(UInt(3.W))
    val param0     = Input(UInt(32.W))
    val param1     = Input(UInt(32.W))

    val in = Flipped(Decoupled(new RadarAXISWord))
    val out = Decoupled(new RadarAXISWord)

    val clearCounters = Input(Bool())
    val inBeats       = Output(UInt(32.W))
    val outBeats      = Output(UInt(32.W))
    val frameCount    = Output(UInt(32.W))
    val lastKeep      = Output(UInt(8.W))
    val status        = Output(UInt(32.W))
    val capabilities  = Output(UInt(32.W))
  })

  private def reverseHalfwords(word: UInt): UInt =
    Cat(word(15, 0), word(31, 16))

  private def add32(word: UInt, loAdd: UInt, hiAdd: UInt): UInt = {
    val lo = word(31, 0) + loAdd
    val hi = word(63, 32) + hiAdd
    Cat(hi(31, 0), lo(31, 0))
  }

  private def shift16Ar(word: UInt, shamt: UInt): UInt = {
    val lanes = Seq.tabulate(4) { i =>
      val shifted = (word(16 * i + 15, 16 * i).asSInt >> shamt).asUInt
      shifted(15, 0)
    }
    Cat(lanes.reverse)
  }

  private def relu16(word: UInt, clip: UInt): UInt = {
    val limit = clip(15, 0)
    val lanes = Seq.tabulate(4) { i =>
      val lane = word(16 * i + 15, 16 * i).asSInt
      val laneUInt = lane.asUInt
      val zeroed = Mux(lane < 0.S, 0.U(16.W), laneUInt(15, 0))
      Mux(limit =/= 0.U && zeroed > limit, limit, zeroed)
    }
    Cat(lanes.reverse)
  }

  private def swap32(word: UInt, param: UInt): UInt = {
    val lo = Mux(param(0), reverseHalfwords(word(31, 0)), word(31, 0))
    val hi = Mux(param(1), reverseHalfwords(word(63, 32)), word(63, 32))
    Mux(param(8), Cat(lo, hi), Cat(hi, lo))
  }

  private def transform(word: UInt): UInt = {
    val activeMode = Mux(io.ctrlEnable, io.mode, RadarAXISPreprocMode.bypass)
    MuxLookup(activeMode, word)(Seq(
      RadarAXISPreprocMode.bypass -> word,
      RadarAXISPreprocMode.add32  -> add32(word, io.param0, io.param1),
      RadarAXISPreprocMode.shift16 -> shift16Ar(word, io.param0(3, 0)),
      RadarAXISPreprocMode.relu16 -> relu16(word, io.param0),
      RadarAXISPreprocMode.swap32 -> swap32(word, io.param0)))
  }

  val outValidReg = RegInit(false.B)
  val outBitsReg  = Reg(new RadarAXISWord)
  val inBeatsReg  = RegInit(0.U(32.W))
  val outBeatsReg = RegInit(0.U(32.W))
  val framesReg   = RegInit(0.U(32.W))
  val lastKeepReg = RegInit(0.U(8.W))

  when (io.clearCounters) {
    inBeatsReg := 0.U
    outBeatsReg := 0.U
    framesReg := 0.U
    lastKeepReg := 0.U
  }

  io.in.ready := !outValidReg || io.out.ready
  io.out.valid := outValidReg
  io.out.bits := outBitsReg

  when (io.in.fire) {
    outBitsReg.data := transform(io.in.bits.data)
    outBitsReg.keep := io.in.bits.keep
    outBitsReg.last := io.in.bits.last
    outValidReg := true.B
    inBeatsReg := inBeatsReg + 1.U
    lastKeepReg := io.in.bits.keep
    when (io.in.bits.last) {
      framesReg := framesReg + 1.U
    }
  } .elsewhen (io.out.fire) {
    outValidReg := false.B
  }

  when (io.out.fire) {
    outBeatsReg := outBeatsReg + 1.U
  }

  io.inBeats := inBeatsReg
  io.outBeats := outBeatsReg
  io.frameCount := framesReg
  io.lastKeep := lastKeepReg
  io.status := Cat(
    0.U(24.W),
    outValidReg,
    io.in.ready,
    io.out.ready,
    io.out.valid,
    io.in.valid,
    io.ctrlEnable,
    io.mode)
  io.capabilities := "h0000001f".U
}

class RadarAXISFeature21Preprocessor extends Module {
  private val maxPoints = 511
  private val inputBeatsPerPoint = 1
  private val outputBeats = 4

  val io = IO(new Bundle {
    val ctrlEnable = Input(Bool())

    val in = Flipped(Decoupled(new RadarAXISWord))
    val out = Decoupled(new RadarAXISWord)

    val clearCounters = Input(Bool())
    val inBeats       = Output(UInt(32.W))
    val outBeats      = Output(UInt(32.W))
    val frameCount    = Output(UInt(32.W))
    val lastKeep      = Output(UInt(8.W))
    val status        = Output(UInt(32.W))
    val capabilities  = Output(UInt(32.W))
  })

  private val (
    sIdle :: sAccum ::
    sMeanX :: sMeanY :: sMeanDoppler :: sMeanRcs ::
    sDensityArea :: sDensityNormalize :: sDensityMul ::
    sDensityShift :: sDensityQuantMul :: sDensityQuantRound ::
    sFeatureSelect :: sFeatureQuantMul :: sFeatureQuantRound ::
    sFeatureWrite :: sEmit :: Nil) = Enum(17)

  private def clampCount(raw: UInt): UInt =
    Mux(raw > maxPoints.U, maxPoints.U, raw)(9, 0)

  private def unpackLane(word: UInt, lane: Int): SInt =
    word(16 * lane + 15, 16 * lane).asSInt

  private def abs16(value: SInt): UInt =
    Mux(value < 0.S, (-value).asUInt, value.asUInt)(15, 0)

  private def rangeApproxQ8p8(x: SInt, y: SInt): SInt = {
    val ax = abs16(x)
    val ay = abs16(y)
    val hi = Mux(ax > ay, ax, ay)
    val lo = Mux(ax > ay, ay, ax)
    (hi + (lo >> 1)).asSInt
  }

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

  private def clampS8(value: SInt): UInt = {
    val clipped = Mux(value > 127.S, 127.S, Mux(value < -127.S, -127.S, value))
    clipped.asUInt(7, 0)
  }

  private def clampU7(value: SInt): UInt =
    Mux(value > 127.S, 127.U(8.W), Mux(value < 0.S, 0.U(8.W), value.asUInt(7, 0)))

  private def bankRoundShiftUIntConst(value: UInt, shift: Int): UInt = {
    val width = value.getWidth
    if (shift == 0) {
      value
    } else {
      val q = value >> shift
      val remMask = ((BigInt(1) << shift) - 1).U(width.W)
      val rem = value & remMask
      val half = (BigInt(1) << (shift - 1)).U(width.W)
      val roundUp = (rem > half) || ((rem === half) && q(0))
      (q +& roundUp.asUInt).asUInt.pad(width)
    }
  }

  private def bankRoundShiftUInt(value: UInt, shift: UInt, maxShift: Int): UInt =
    MuxLookup(shift, value)(Seq.tabulate(maxShift + 1) { i =>
      i.U -> bankRoundShiftUIntConst(value, i)
    })

  private def multiplyByQ8p8QuantConstant(value: SInt): SInt =
    Seq(5, 3, 0).foldLeft((value << 6).asSInt.pad(56)) { (acc, shift) =>
      (acc +& (value << shift).asSInt.pad(56)).asSInt.pad(56)
    }

  private def quantQ8p8(value: SInt): UInt =
    clampS8(bankRoundShift(multiplyByQ8p8QuantConstant(value), 16))

  private def quantRaw(value: UInt): UInt =
    quantQ8p8((value.zext.asSInt << 8).asSInt)

  private def roundNearestEvenDiv(numer: BigInt, denom: Int): BigInt = {
    val q = numer / denom
    val rem = numer % denom
    val twiceRem = rem << 1
    q + (if (twiceRem > denom || (twiceRem == denom && (q & 1) == 1)) BigInt(1) else BigInt(0))
  }

  private val densityRecipLut = VecInit(Seq.tabulate(128) { i =>
    roundNearestEvenDiv(BigInt(1) << 23, i + 128).U(17.W)
  })

  private def floorLog2NonZero(value: UInt): UInt = {
    val out = WireDefault(0.U(5.W))
    for (i <- 0 until 32) {
      when (value(i)) { out := i.U }
    }
    out
  }

  private def meanApproxQ8p8(sum: SInt, count: UInt): SInt = {
    val shift = Wire(UInt(4.W))
    shift := MuxLookup(count, 0.U)(Seq(
      0.U -> 0.U,
      1.U -> 0.U,
      2.U -> 1.U,
      3.U -> 2.U,
      4.U -> 2.U,
      5.U -> 3.U,
      6.U -> 3.U,
      7.U -> 3.U,
      8.U -> 3.U))
    when (count > 8.U && count <= 16.U) { shift := 4.U }
    when (count > 16.U && count <= 32.U) { shift := 5.U }
    when (count > 32.U && count <= 64.U) { shift := 6.U }
    when (count > 64.U && count <= 128.U) { shift := 7.U }
    when (count > 128.U && count <= 256.U) { shift := 8.U }
    when (count > 256.U) { shift := 9.U }
    (sum >> shift).asSInt
  }

  private def packFeatureWord(bytes: Vec[UInt], beat: Int): UInt =
    Cat((0 until 8).reverse.map(i => bytes(beat * 8 + i)))

  val state = RegInit(sIdle)
  val expectedPoints = RegInit(0.U(10.W))
  val actualPoints = RegInit(0.U(10.W))
  val emitIdx = RegInit(0.U(2.W))
  val featureIdx = RegInit(0.U(5.W))
  val featureDensityReg = RegInit(false.B)
  val featureQ8p8Reg = RegInit(0.S(40.W))
  val featureQuantProductReg = RegInit(0.S(56.W))
  val featureByteReg = RegInit(0.U(8.W))

  val sumX = RegInit(0.S(40.W))
  val sumY = RegInit(0.S(40.W))
  val sumDoppler = RegInit(0.S(40.W))
  val sumRcs = RegInit(0.S(40.W))

  val minX = RegInit(0.S(16.W))
  val maxX = RegInit(0.S(16.W))
  val minY = RegInit(0.S(16.W))
  val maxY = RegInit(0.S(16.W))
  val minDoppler = RegInit(0.S(16.W))
  val maxDoppler = RegInit(0.S(16.W))
  val minRcs = RegInit(0.S(16.W))
  val maxRcs = RegInit(0.S(16.W))
  val minRange = RegInit(0.S(17.W))
  val maxRange = RegInit(0.S(17.W))
  val meanXReg = RegInit(0.S(40.W))
  val meanYReg = RegInit(0.S(40.W))
  val meanDopplerReg = RegInit(0.S(40.W))
  val meanRcsReg = RegInit(0.S(40.W))
  val densityAreaReg = RegInit(0.U(32.W))
  val densityExponentReg = RegInit(0.U(5.W))
  val densityMantReg = RegInit(128.U(8.W))
  val densityRecipReg = RegInit(0.U(17.W))
  val densityProdReg = RegInit(0.U(32.W))
  val densityQ8p8Reg = RegInit(0.U(40.W))
  val densityQuantProductReg = RegInit(0.S(56.W))
  val densityFeatureReg = RegInit(0.U(8.W))

  val featureByteRegs = RegInit(VecInit(Seq.fill(32)(0.U(8.W))))
  val outValidReg = RegInit(false.B)
  val outBitsReg = RegInit(0.U.asTypeOf(new RadarAXISWord))

  val inBeatsReg = RegInit(0.U(32.W))
  val outBeatsReg = RegInit(0.U(32.W))
  val framesReg = RegInit(0.U(32.W))
  val lastKeepReg = RegInit(0.U(8.W))

  private val spanX = (maxX - minX).asSInt
  private val spanY = (maxY - minY).asSInt
  private val spanDoppler = (maxDoppler - minDoppler).asSInt
  private val spanRcs = (maxRcs - minRcs).asSInt
  private val stdXApprox = (spanX >> 2).asSInt
  private val stdYApprox = (spanY >> 2).asSInt
  private val stdDopplerApprox = (spanDoppler >> 2).asSInt
  private val stdRcsApprox = (spanRcs >> 2).asSInt
  private val centroidRange = rangeApproxQ8p8(meanXReg, meanYReg)
  private val eigMajorApprox = Mux(stdXApprox > stdYApprox, stdXApprox, stdYApprox)
  private val eigMinorApprox = Mux(stdXApprox > stdYApprox, stdYApprox, stdXApprox)

  private val selectedFeatureDensity = WireDefault(false.B)
  private val selectedFeatureQ8p8 = WireDefault(0.S(40.W))
  switch (featureIdx) {
    is (0.U)  { selectedFeatureQ8p8 := (actualPoints.zext << 8).asSInt }
    is (1.U)  { selectedFeatureQ8p8 := meanXReg }
    is (2.U)  { selectedFeatureQ8p8 := meanYReg }
    is (3.U)  { selectedFeatureQ8p8 := stdXApprox }
    is (4.U)  { selectedFeatureQ8p8 := stdYApprox }
    is (5.U)  { selectedFeatureQ8p8 := spanX }
    is (6.U)  { selectedFeatureQ8p8 := spanY }
    is (7.U)  { selectedFeatureQ8p8 := minRange }
    is (8.U)  { selectedFeatureQ8p8 := maxRange }
    is (9.U)  { selectedFeatureQ8p8 := centroidRange }
    is (10.U) { selectedFeatureQ8p8 := spanY }
    is (11.U) { selectedFeatureQ8p8 := eigMajorApprox }
    is (12.U) { selectedFeatureQ8p8 := eigMinorApprox }
    is (13.U) { selectedFeatureDensity := true.B }
    is (14.U) { selectedFeatureQ8p8 := meanDopplerReg }
    is (15.U) { selectedFeatureQ8p8 := stdDopplerApprox }
    is (16.U) { selectedFeatureQ8p8 := minDoppler }
    is (17.U) { selectedFeatureQ8p8 := maxDoppler }
    is (18.U) { selectedFeatureQ8p8 := meanRcsReg }
    is (19.U) { selectedFeatureQ8p8 := stdRcsApprox }
    is (20.U) { selectedFeatureQ8p8 := maxRcs }
  }
  private val packedFeatureWords = VecInit((0 until outputBeats).map { beat =>
    packFeatureWord(featureByteRegs, beat)
  })

  io.in.ready := io.ctrlEnable && (state === sIdle || state === sAccum)
  io.out.valid := outValidReg
  io.out.bits := outBitsReg

  when (io.clearCounters) {
    inBeatsReg := 0.U
    outBeatsReg := 0.U
    framesReg := 0.U
    lastKeepReg := 0.U
  }

  switch (state) {
    is (sIdle) {
      when (!io.ctrlEnable) {
        outValidReg := false.B
      }

      when (io.in.fire) {
        val count = clampCount(io.in.bits.data(15, 0))
        expectedPoints := count
        actualPoints := 0.U
        sumX := 0.S
        sumY := 0.S
        sumDoppler := 0.S
        sumRcs := 0.S
        minX := 0.S
        maxX := 0.S
        minY := 0.S
        maxY := 0.S
        minDoppler := 0.S
        maxDoppler := 0.S
        minRcs := 0.S
        maxRcs := 0.S
        minRange := 0.S
        maxRange := 0.S
        meanXReg := 0.S
        meanYReg := 0.S
        meanDopplerReg := 0.S
        meanRcsReg := 0.S
        densityAreaReg := 0.U
        densityExponentReg := 0.U
        densityMantReg := 128.U
        densityRecipReg := 0.U
        densityProdReg := 0.U
        densityQ8p8Reg := 0.U
        densityQuantProductReg := 0.S
        densityFeatureReg := 0.U
        featureDensityReg := false.B
        featureQ8p8Reg := 0.S
        featureQuantProductReg := 0.S
        featureByteReg := 0.U
        featureByteRegs.foreach(_ := 0.U)
        inBeatsReg := inBeatsReg + 1.U
        lastKeepReg := io.in.bits.keep
        when (io.in.bits.last) {
          framesReg := framesReg + 1.U
        }
        state := Mux(count === 0.U || io.in.bits.last, sMeanX, sAccum)
      }
    }

    is (sAccum) {
      when (io.in.fire) {
        val x = unpackLane(io.in.bits.data, 0)
        val y = unpackLane(io.in.bits.data, 1)
        val doppler = unpackLane(io.in.bits.data, 2)
        val rcs = unpackLane(io.in.bits.data, 3)
        val rangeApprox = rangeApproxQ8p8(x, y).pad(17)
        val firstPoint = actualPoints === 0.U
        val nextActual = actualPoints + inputBeatsPerPoint.U

        sumX := sumX + x.pad(40)
        sumY := sumY + y.pad(40)
        sumDoppler := sumDoppler + doppler.pad(40)
        sumRcs := sumRcs + rcs.pad(40)

        minX := Mux(firstPoint || x < minX, x, minX)
        maxX := Mux(firstPoint || x > maxX, x, maxX)
        minY := Mux(firstPoint || y < minY, y, minY)
        maxY := Mux(firstPoint || y > maxY, y, maxY)
        minDoppler := Mux(firstPoint || doppler < minDoppler, doppler, minDoppler)
        maxDoppler := Mux(firstPoint || doppler > maxDoppler, doppler, maxDoppler)
        minRcs := Mux(firstPoint || rcs < minRcs, rcs, minRcs)
        maxRcs := Mux(firstPoint || rcs > maxRcs, rcs, maxRcs)
        minRange := Mux(firstPoint || rangeApprox < minRange, rangeApprox, minRange)
        maxRange := Mux(firstPoint || rangeApprox > maxRange, rangeApprox, maxRange)

        actualPoints := nextActual
        inBeatsReg := inBeatsReg + 1.U
        lastKeepReg := io.in.bits.keep
        when (io.in.bits.last) {
          framesReg := framesReg + 1.U
        }
        when (nextActual >= expectedPoints || io.in.bits.last) {
          state := sMeanX
        }
      }
    }

    is (sMeanX) {
      meanXReg := meanApproxQ8p8(sumX, actualPoints)
      state := sMeanY
    }

    is (sMeanY) {
      meanYReg := meanApproxQ8p8(sumY, actualPoints)
      state := sMeanDoppler
    }

    is (sMeanDoppler) {
      meanDopplerReg := meanApproxQ8p8(sumDoppler, actualPoints)
      state := sMeanRcs
    }

    is (sMeanRcs) {
      meanRcsReg := meanApproxQ8p8(sumRcs, actualPoints)
      state := sDensityArea
    }

    is (sDensityArea) {
      val spanXU = Mux(spanX < 0.S, 0.U(16.W), spanX.asUInt(15, 0))
      val spanYU = Mux(spanY < 0.S, 0.U(16.W), spanY.asUInt(15, 0))
      densityAreaReg := spanXU * spanYU
      state := sDensityNormalize
    }

    is (sDensityNormalize) {
      val exponent = floorLog2NonZero(densityAreaReg)
      val normRightShift = Mux(exponent >= 7.U, exponent - 7.U, 0.U)
      val normLeftShift = Mux(exponent < 7.U, 7.U - exponent, 0.U)
      val mantWide = Wire(UInt(32.W))
      mantWide := Mux(exponent >= 7.U, densityAreaReg >> normRightShift, densityAreaReg << normLeftShift)
      val mantClamped = Mux(mantWide < 128.U, 128.U(8.W), Mux(mantWide > 255.U, 255.U(8.W), mantWide(7, 0)))
      densityExponentReg := exponent
      densityMantReg := mantClamped
      densityRecipReg := densityRecipLut((mantClamped - 128.U)(6, 0))
      state := sDensityMul
    }

    is (sDensityMul) {
      densityProdReg := actualPoints(8, 0) * densityRecipReg
      state := sDensityShift
    }

    is (sDensityShift) {
      val densityRightShift = Mux(densityExponentReg >= 8.U, densityExponentReg - 8.U, 0.U)
      val densityLeftShift = Mux(densityExponentReg < 8.U, 8.U - densityExponentReg, 0.U)
      val shiftedRight = bankRoundShiftUInt(densityProdReg, densityRightShift, 23)
      val shiftedLeft = (densityProdReg << densityLeftShift)(39, 0)
      densityQ8p8Reg := Mux(densityExponentReg >= 8.U, shiftedRight.pad(40), shiftedLeft)
      state := sDensityQuantMul
    }

    is (sDensityQuantMul) {
      densityQuantProductReg := multiplyByQ8p8QuantConstant(densityQ8p8Reg.zext.asSInt)
      state := sDensityQuantRound
    }

    is (sDensityQuantRound) {
      val densityRounded = bankRoundShift(densityQuantProductReg, 16)
      densityFeatureReg := Mux(actualPoints === 0.U, 0.U(8.W), Mux(densityAreaReg === 0.U, 127.U(8.W), clampU7(densityRounded)))
      featureIdx := 0.U
      state := sFeatureSelect
    }

    is (sFeatureSelect) {
      // Split feature selection from quantization. This keeps the large
      // feature mux out of the quantize/round/clamp path.
      featureDensityReg := selectedFeatureDensity
      featureQ8p8Reg := selectedFeatureQ8p8
      state := sFeatureQuantMul
    }

    is (sFeatureQuantMul) {
      featureQuantProductReg := multiplyByQ8p8QuantConstant(featureQ8p8Reg)
      state := sFeatureQuantRound
    }

    is (sFeatureQuantRound) {
      val featureRounded = bankRoundShift(featureQuantProductReg, 16)
      featureByteReg := Mux(featureDensityReg, densityFeatureReg, clampS8(featureRounded))
      state := sFeatureWrite
    }

    is (sFeatureWrite) {
      featureByteRegs(featureIdx) := featureByteReg
      when (featureIdx === 20.U) {
        emitIdx := 0.U
        outBitsReg.data := packedFeatureWords(0)
        outBitsReg.keep := "hff".U
        outBitsReg.last := false.B
        outValidReg := true.B
        state := sEmit
      } .otherwise {
        featureIdx := featureIdx + 1.U
        state := sFeatureSelect
      }
    }

    is (sEmit) {
      when (io.out.fire) {
        outBeatsReg := outBeatsReg + 1.U
        when (emitIdx === (outputBeats - 1).U) {
          outValidReg := false.B
          state := sIdle
        } .otherwise {
          val nextEmitIdx = emitIdx + 1.U
          emitIdx := nextEmitIdx
          outBitsReg.data := MuxLookup(nextEmitIdx, packedFeatureWords(0))(Seq(
            1.U -> packedFeatureWords(1),
            2.U -> packedFeatureWords(2),
            3.U -> packedFeatureWords(3)))
          outBitsReg.keep := "hff".U
          outBitsReg.last := nextEmitIdx === (outputBeats - 1).U
        }
      }
    }

  }

  io.inBeats := inBeatsReg
  io.outBeats := outBeatsReg
  io.frameCount := framesReg
  io.lastKeep := lastKeepReg
  io.status := Cat(
    0.U(22.W),
    outValidReg,
    io.in.ready,
    io.out.ready,
    io.out.valid,
    io.in.valid,
    io.ctrlEnable,
    state)
  io.capabilities := "h00000020".U
}

class RadarAXIDMABlackBox extends BlackBox {
  override def desiredName: String = "radar_axi_dma"

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
    val m_axis_mm2s_tdata      = Output(UInt(64.W))
    val m_axis_mm2s_tkeep      = Output(UInt(8.W))
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
       |  CONFIG.c_m_axis_mm2s_tdata_width {64} \\
       |  CONFIG.c_s_axis_s2mm_tdata_width {64} \\
       |  CONFIG.c_m_axi_s2mm_data_width {64} \\
       |  CONFIG.c_addr_width {32} \\
       |  CONFIG.c_mm2s_burst_size {8} \\
       |  CONFIG.c_s2mm_burst_size {8} \\
       |] [get_ips ${desiredName}]
       |""".stripMargin)
}

class RadarAXIDMA(implicit p: Parameters) extends LazyModule {
  val controlParams = RadarAXIDMAControlParams()

  val mm2sNode = AXI4MasterNode(Seq(AXI4MasterPortParameters(
    masters = Seq(AXI4MasterParameters(
      name = "radar-dma-mm2s",
      id   = IdRange(0, 1),
      aligned = false)))))

  val s2mmNode = AXI4MasterNode(Seq(AXI4MasterPortParameters(
    masters = Seq(AXI4MasterParameters(
      name = "radar-dma-s2mm",
      id   = IdRange(0, 1),
      aligned = false)))))

  lazy val module = new Impl

  class Impl extends LazyRawModuleImp(this) {
    val debug = IO(Output(new Bundle {
      val mm2sArFireSeen       = Bool()
      val mm2sRValidSeen       = Bool()
      val mm2sRReadySeen       = Bool()
      val mm2sRFireSeen        = Bool()
      val mm2sReadBeat16Seen   = Bool()
      val mm2sReadBeat32Seen   = Bool()
      val mm2sStreamBeat16Seen = Bool()
      val mm2sStreamBeat32Seen = Bool()
      val mm2sTLASTSeen        = Bool()
      val s2mmWriteBeat16Seen  = Bool()
      val s2mmWriteBeat32Seen  = Bool()
      val s2mmWLASTSeen        = Bool()
      val mm2sPacketEOFSeen    = Bool()
      val s2mmPacketEOFSeen    = Bool()
      val mm2sIOCSeen          = Bool()
      val s2mmIOCSeen          = Bool()
    }))
    val ctrlClock = IO(Input(Clock()))
    val ctrlResetN = IO(Input(Bool()))
    val ctrl = IO(Flipped(new AXI4Bundle(AXI4BundleParameters(
      addrBits = controlParams.addrBits,
      dataBits = controlParams.dataBits,
      idBits   = controlParams.idBits))))

    val bb = Module(new RadarAXIDMABlackBox)
    val (mm2s, _) = mm2sNode.out(0)
    val (s2mm, _) = s2mmNode.out(0)

    bb.io.s_axi_lite_aclk := ctrlClock
    bb.io.m_axi_mm2s_aclk := ctrlClock
    bb.io.m_axi_s2mm_aclk := ctrlClock
    bb.io.axi_resetn      := ctrlResetN

    val ctrlBridge = withClockAndReset(ctrlClock, (!ctrlResetN).asAsyncReset) {
      Module(new RadarAXI4ToAXI4LiteBridge(controlParams))
    }
    val preproc = withClockAndReset(ctrlClock, (!ctrlResetN).asAsyncReset) {
      Module(new RadarAXISPreprocessor)
    }
    val feature21 = withClockAndReset(ctrlClock, (!ctrlResetN).asAsyncReset) {
      Module(new RadarAXISFeature21Preprocessor)
    }
    val qmlp = withClockAndReset(ctrlClock, (!ctrlResetN).asAsyncReset) {
      Module(new RadarAXISQMLP)
    }
    ctrlBridge.io.in <> ctrl

    def applyWriteStrobe(prev: UInt, data: UInt, strb: UInt): UInt = {
      Cat((3 to 0 by -1).map { i =>
        Mux(strb(i), data(8 * i + 7, 8 * i), prev(8 * i + 7, 8 * i))
      })
    }

    ctrlBridge.io.local.wrResp := AXI4Parameters.RESP_OKAY
    ctrlBridge.io.local.rdResp := AXI4Parameters.RESP_OKAY

    val (preprocCtrlReg,
         preprocModeReg,
         preprocParam0Reg,
         preprocParam1Reg,
         preprocClearCounters,
         qmlpCtrlReg,
         qmlpClearCounters,
         localReadData) = withClockAndReset(ctrlClock, (!ctrlResetN).asAsyncReset) {
      val preprocCtrlReg  = RegInit(0.U(32.W))
      val preprocModeReg  = RegInit(0.U(32.W))
      val preprocParam0Reg = RegInit(0.U(32.W))
      val preprocParam1Reg = RegInit(0.U(32.W))
      val preprocClearCounters = WireDefault(false.B)
      val qmlpCtrlReg = RegInit(0.U(32.W))
      val qmlpClearCounters = WireDefault(false.B)
      val localReadData = WireDefault(0.U(32.W))

      when (ctrlBridge.io.local.wrEn) {
        switch (ctrlBridge.io.local.wrAddr) {
          is ("h00".U) {
            val nextCtrl = applyWriteStrobe(preprocCtrlReg, ctrlBridge.io.local.wrData, ctrlBridge.io.local.wrStrb)
            preprocCtrlReg := nextCtrl & 1.U(32.W)
            preprocClearCounters := nextCtrl(1)
          }
          is ("h04".U) {
            preprocModeReg := applyWriteStrobe(preprocModeReg, ctrlBridge.io.local.wrData, ctrlBridge.io.local.wrStrb)
          }
          is ("h08".U) {
            preprocParam0Reg := applyWriteStrobe(preprocParam0Reg, ctrlBridge.io.local.wrData, ctrlBridge.io.local.wrStrb)
          }
          is ("h0c".U) {
            preprocParam1Reg := applyWriteStrobe(preprocParam1Reg, ctrlBridge.io.local.wrData, ctrlBridge.io.local.wrStrb)
          }
          is ("h40".U) {
            val nextCtrl = applyWriteStrobe(qmlpCtrlReg, ctrlBridge.io.local.wrData, ctrlBridge.io.local.wrStrb)
            // bit0: direct QMLP enable, bit2: route DMA stream through preproc before QMLP.
            qmlpCtrlReg := nextCtrl & "h00000005".U(32.W)
            qmlpClearCounters := nextCtrl(1)
          }
        }
      }

      switch (ctrlBridge.io.local.rdAddr) {
        is ("h00".U) { localReadData := preprocCtrlReg }
        is ("h04".U) { localReadData := preprocModeReg }
        is ("h08".U) { localReadData := preprocParam0Reg }
        is ("h0c".U) { localReadData := preprocParam1Reg }
        is ("h10".U) { localReadData := Mux(preprocModeReg(2, 0) === RadarAXISPreprocMode.feature21, feature21.io.status, preproc.io.status) }
        is ("h14".U) { localReadData := Mux(preprocModeReg(2, 0) === RadarAXISPreprocMode.feature21, feature21.io.inBeats, preproc.io.inBeats) }
        is ("h18".U) { localReadData := Mux(preprocModeReg(2, 0) === RadarAXISPreprocMode.feature21, feature21.io.outBeats, preproc.io.outBeats) }
        is ("h1c".U) { localReadData := Mux(preprocModeReg(2, 0) === RadarAXISPreprocMode.feature21, feature21.io.frameCount, preproc.io.frameCount) }
        is ("h20".U) { localReadData := Mux(preprocModeReg(2, 0) === RadarAXISPreprocMode.feature21, feature21.io.lastKeep, preproc.io.lastKeep) }
        is ("h24".U) { localReadData := preproc.io.capabilities | feature21.io.capabilities }
        is ("h40".U) { localReadData := qmlpCtrlReg }
        is ("h44".U) { localReadData := qmlp.io.status }
        is ("h48".U) { localReadData := qmlp.io.inBeats }
        is ("h4c".U) { localReadData := qmlp.io.outBeats }
        is ("h50".U) { localReadData := qmlp.io.frameCount }
        is ("h54".U) { localReadData := qmlp.io.lastKeep }
        is ("h58".U) { localReadData := qmlp.io.lastLogit0.asUInt }
        is ("h5c".U) { localReadData := qmlp.io.lastLogit1.asUInt }
        is ("h60".U) { localReadData := qmlp.io.runCycles }
        is ("h64".U) { localReadData := qmlp.io.capabilities }
        is ("h68".U) { localReadData := 32.U }
        is ("h6c".U) { localReadData := 8.U }
      }

      (preprocCtrlReg,
       preprocModeReg,
       preprocParam0Reg,
       preprocParam1Reg,
       preprocClearCounters,
       qmlpCtrlReg,
       qmlpClearCounters,
       localReadData)
    }
    ctrlBridge.io.local.rdData := localReadData

    preproc.io.ctrlEnable := preprocCtrlReg(0)
    preproc.io.mode := preprocModeReg(2, 0)
    preproc.io.param0 := preprocParam0Reg
    preproc.io.param1 := preprocParam1Reg
    preproc.io.clearCounters := preprocClearCounters

    feature21.io.ctrlEnable := preprocCtrlReg(0)
    feature21.io.clearCounters := preprocClearCounters

    qmlp.io.ctrlEnable := qmlpCtrlReg(0)
    qmlp.io.clearCounters := qmlpClearCounters

    bb.io.s_axi_lite_awvalid := ctrlBridge.io.lite.awvalid
    ctrlBridge.io.lite.awready := bb.io.s_axi_lite_awready
    bb.io.s_axi_lite_awaddr  := ctrlBridge.io.lite.awaddr

    bb.io.s_axi_lite_wvalid := ctrlBridge.io.lite.wvalid
    ctrlBridge.io.lite.wready := bb.io.s_axi_lite_wready
    bb.io.s_axi_lite_wdata  := ctrlBridge.io.lite.wdata

    ctrlBridge.io.lite.bvalid := bb.io.s_axi_lite_bvalid
    bb.io.s_axi_lite_bready := ctrlBridge.io.lite.bready
    ctrlBridge.io.lite.bresp := bb.io.s_axi_lite_bresp

    bb.io.s_axi_lite_arvalid := ctrlBridge.io.lite.arvalid
    ctrlBridge.io.lite.arready := bb.io.s_axi_lite_arready
    bb.io.s_axi_lite_araddr  := ctrlBridge.io.lite.araddr

    ctrlBridge.io.lite.rvalid := bb.io.s_axi_lite_rvalid
    bb.io.s_axi_lite_rready := ctrlBridge.io.lite.rready
    ctrlBridge.io.lite.rdata := bb.io.s_axi_lite_rdata
    ctrlBridge.io.lite.rresp := bb.io.s_axi_lite_rresp

    val (mm2sArFireSeen,
         mm2sRValidSeen,
         mm2sRReadySeen,
         mm2sRFireSeen,
         mm2sReadBeat16Seen,
         mm2sReadBeat32Seen,
         mm2sStreamBeat16Seen,
         mm2sStreamBeat32Seen,
         mm2sTLASTSeen,
         s2mmWriteBeat16Seen,
         s2mmWriteBeat32Seen,
         s2mmWLASTSeen,
         mm2sPacketEOFSeen,
         s2mmPacketEOFSeen,
         mm2sIOCSeen,
         s2mmIOCSeen) = withClockAndReset(ctrlClock, (!ctrlResetN).asAsyncReset) {
      val mm2sArFireSeen = RegInit(false.B)
      val mm2sRValidSeen = RegInit(false.B)
      val mm2sRReadySeen = RegInit(false.B)
      val mm2sRFireSeen  = RegInit(false.B)
      val mm2sReadBeat16Seen   = RegInit(false.B)
      val mm2sReadBeat32Seen   = RegInit(false.B)
      val mm2sStreamBeat16Seen = RegInit(false.B)
      val mm2sStreamBeat32Seen = RegInit(false.B)
      val mm2sTLASTSeen        = RegInit(false.B)
      val s2mmWriteBeat16Seen  = RegInit(false.B)
      val s2mmWriteBeat32Seen  = RegInit(false.B)
      val s2mmWLASTSeen        = RegInit(false.B)
      val mm2sPacketEOFSeen    = RegInit(false.B)
      val s2mmPacketEOFSeen    = RegInit(false.B)
      val mm2sIOCSeen          = RegInit(false.B)
      val s2mmIOCSeen          = RegInit(false.B)
      val mm2sReadBeatCount    = RegInit(0.U(6.W))
      val mm2sStreamBeatCount  = RegInit(0.U(6.W))
      val s2mmWriteBeatCount   = RegInit(0.U(6.W))

      val mm2sStreamFire = bb.io.m_axis_mm2s_tvalid && bb.io.m_axis_mm2s_tready

      when (mm2s.ar.fire) { mm2sArFireSeen := true.B }
      when (mm2s.r.valid) { mm2sRValidSeen := true.B }
      when (mm2s.r.ready) { mm2sRReadySeen := true.B }
      when (mm2s.r.fire) {
        mm2sRFireSeen := true.B
        val nextCount = Mux(mm2sReadBeatCount === 63.U, 63.U, mm2sReadBeatCount + 1.U)
        mm2sReadBeatCount := nextCount
        when (nextCount >= 16.U) { mm2sReadBeat16Seen := true.B }
        when (nextCount >= 32.U) { mm2sReadBeat32Seen := true.B }
      }
      when (mm2sStreamFire) {
        val nextCount = Mux(mm2sStreamBeatCount === 63.U, 63.U, mm2sStreamBeatCount + 1.U)
        mm2sStreamBeatCount := nextCount
        when (nextCount >= 16.U) { mm2sStreamBeat16Seen := true.B }
        when (nextCount >= 32.U) { mm2sStreamBeat32Seen := true.B }
      }
      when (mm2sStreamFire && bb.io.m_axis_mm2s_tlast) { mm2sTLASTSeen := true.B }
      when (s2mm.w.fire) {
        val nextCount = Mux(s2mmWriteBeatCount === 63.U, 63.U, s2mmWriteBeatCount + 1.U)
        s2mmWriteBeatCount := nextCount
        when (nextCount >= 16.U) { s2mmWriteBeat16Seen := true.B }
        when (nextCount >= 32.U) { s2mmWriteBeat32Seen := true.B }
      }
      when (s2mm.w.fire && s2mm.w.bits.last) { s2mmWLASTSeen := true.B }
      when (bb.io.axi_dma_tstvec(1)) { mm2sPacketEOFSeen := true.B }
      when (bb.io.axi_dma_tstvec(3)) { s2mmPacketEOFSeen := true.B }
      when (bb.io.axi_dma_tstvec(4)) { mm2sIOCSeen := true.B }
      when (bb.io.axi_dma_tstvec(5)) { s2mmIOCSeen := true.B }

      (mm2sArFireSeen,
       mm2sRValidSeen,
       mm2sRReadySeen,
       mm2sRFireSeen,
       mm2sReadBeat16Seen,
       mm2sReadBeat32Seen,
       mm2sStreamBeat16Seen,
       mm2sStreamBeat32Seen,
       mm2sTLASTSeen,
       s2mmWriteBeat16Seen,
       s2mmWriteBeat32Seen,
       s2mmWLASTSeen,
       mm2sPacketEOFSeen,
       s2mmPacketEOFSeen,
       mm2sIOCSeen,
       s2mmIOCSeen)
    }

    debug.mm2sArFireSeen       := mm2sArFireSeen
    debug.mm2sRValidSeen       := mm2sRValidSeen
    debug.mm2sRReadySeen       := mm2sRReadySeen
    debug.mm2sRFireSeen        := mm2sRFireSeen
    debug.mm2sReadBeat16Seen   := mm2sReadBeat16Seen
    debug.mm2sReadBeat32Seen   := mm2sReadBeat32Seen
    debug.mm2sStreamBeat16Seen := mm2sStreamBeat16Seen
    debug.mm2sStreamBeat32Seen := mm2sStreamBeat32Seen
    debug.mm2sTLASTSeen        := mm2sTLASTSeen
    debug.s2mmWriteBeat16Seen  := s2mmWriteBeat16Seen
    debug.s2mmWriteBeat32Seen  := s2mmWriteBeat32Seen
    debug.s2mmWLASTSeen        := s2mmWLASTSeen
    debug.mm2sPacketEOFSeen    := mm2sPacketEOFSeen
    debug.s2mmPacketEOFSeen    := s2mmPacketEOFSeen
    debug.mm2sIOCSeen          := mm2sIOCSeen
    debug.s2mmIOCSeen          := s2mmIOCSeen

    val qmlpEnabled = qmlpCtrlReg(0)
    val qmlpChainPreproc = qmlpCtrlReg(2)
    val feature21Selected = preprocModeReg(2, 0) === RadarAXISPreprocMode.feature21

    preproc.io.in.valid := false.B
    preproc.io.in.bits.data := bb.io.m_axis_mm2s_tdata
    preproc.io.in.bits.keep := bb.io.m_axis_mm2s_tkeep
    preproc.io.in.bits.last := bb.io.m_axis_mm2s_tlast
    preproc.io.out.ready := false.B

    feature21.io.in.valid := false.B
    feature21.io.in.bits.data := bb.io.m_axis_mm2s_tdata
    feature21.io.in.bits.keep := bb.io.m_axis_mm2s_tkeep
    feature21.io.in.bits.last := bb.io.m_axis_mm2s_tlast
    feature21.io.out.ready := false.B

    qmlp.io.in.valid := false.B
    qmlp.io.in.bits.data := bb.io.m_axis_mm2s_tdata
    qmlp.io.in.bits.keep := bb.io.m_axis_mm2s_tkeep
    qmlp.io.in.bits.last := bb.io.m_axis_mm2s_tlast
    qmlp.io.out.ready := false.B

    bb.io.m_axis_mm2s_tready := preproc.io.in.ready
    bb.io.s_axis_s2mm_tdata  := preproc.io.out.bits.data
    bb.io.s_axis_s2mm_tkeep  := preproc.io.out.bits.keep
    bb.io.s_axis_s2mm_tvalid := preproc.io.out.valid
    bb.io.s_axis_s2mm_tlast  := preproc.io.out.bits.last

    when (qmlpEnabled && qmlpChainPreproc) {
      when (feature21Selected) {
        feature21.io.in.valid := bb.io.m_axis_mm2s_tvalid
        feature21.io.out.ready := qmlp.io.in.ready

        qmlp.io.in.valid := feature21.io.out.valid
        qmlp.io.in.bits := feature21.io.out.bits

        bb.io.m_axis_mm2s_tready := feature21.io.in.ready
      } .otherwise {
        preproc.io.in.valid := bb.io.m_axis_mm2s_tvalid
        preproc.io.out.ready := qmlp.io.in.ready

        qmlp.io.in.valid := preproc.io.out.valid
        qmlp.io.in.bits := preproc.io.out.bits

        bb.io.m_axis_mm2s_tready := preproc.io.in.ready
      }
      qmlp.io.out.ready := bb.io.s_axis_s2mm_tready

      bb.io.s_axis_s2mm_tdata  := qmlp.io.out.bits.data
      bb.io.s_axis_s2mm_tkeep  := qmlp.io.out.bits.keep
      bb.io.s_axis_s2mm_tvalid := qmlp.io.out.valid
      bb.io.s_axis_s2mm_tlast  := qmlp.io.out.bits.last
    } .elsewhen (qmlpEnabled) {
      qmlp.io.in.valid := bb.io.m_axis_mm2s_tvalid
      qmlp.io.out.ready := bb.io.s_axis_s2mm_tready

      bb.io.m_axis_mm2s_tready := qmlp.io.in.ready
      bb.io.s_axis_s2mm_tdata  := qmlp.io.out.bits.data
      bb.io.s_axis_s2mm_tkeep  := qmlp.io.out.bits.keep
      bb.io.s_axis_s2mm_tvalid := qmlp.io.out.valid
      bb.io.s_axis_s2mm_tlast  := qmlp.io.out.bits.last
    } .otherwise {
      when (feature21Selected) {
        feature21.io.in.valid := bb.io.m_axis_mm2s_tvalid
        feature21.io.out.ready := bb.io.s_axis_s2mm_tready

        bb.io.m_axis_mm2s_tready := feature21.io.in.ready
        bb.io.s_axis_s2mm_tdata  := feature21.io.out.bits.data
        bb.io.s_axis_s2mm_tkeep  := feature21.io.out.bits.keep
        bb.io.s_axis_s2mm_tvalid := feature21.io.out.valid
        bb.io.s_axis_s2mm_tlast  := feature21.io.out.bits.last
      } .otherwise {
        preproc.io.in.valid := bb.io.m_axis_mm2s_tvalid
        preproc.io.out.ready := bb.io.s_axis_s2mm_tready
      }
    }

    mm2s.aw.valid := false.B
    mm2s.aw.bits  := DontCare
    mm2s.w.valid  := false.B
    mm2s.w.bits   := DontCare
    mm2s.b.ready  := false.B

    mm2s.ar.valid      := bb.io.m_axi_mm2s_arvalid
    mm2s.ar.bits.id    := 0.U
    mm2s.ar.bits.addr  := bb.io.m_axi_mm2s_araddr
    mm2s.ar.bits.len   := bb.io.m_axi_mm2s_arlen
    mm2s.ar.bits.size  := bb.io.m_axi_mm2s_arsize
    mm2s.ar.bits.burst := bb.io.m_axi_mm2s_arburst
    mm2s.ar.bits.lock  := 0.U
    mm2s.ar.bits.cache := bb.io.m_axi_mm2s_arcache
    mm2s.ar.bits.prot  := bb.io.m_axi_mm2s_arprot
    mm2s.ar.bits.qos   := 0.U
    bb.io.m_axi_mm2s_arready := mm2s.ar.ready

    bb.io.m_axi_mm2s_rdata  := mm2s.r.bits.data
    bb.io.m_axi_mm2s_rresp  := mm2s.r.bits.resp
    bb.io.m_axi_mm2s_rlast  := mm2s.r.bits.last
    bb.io.m_axi_mm2s_rvalid := mm2s.r.valid
    mm2s.r.ready            := bb.io.m_axi_mm2s_rready

    s2mm.ar.valid := false.B
    s2mm.ar.bits  := DontCare
    s2mm.r.ready  := false.B

    s2mm.aw.valid      := bb.io.m_axi_s2mm_awvalid
    s2mm.aw.bits.id    := 0.U
    s2mm.aw.bits.addr  := bb.io.m_axi_s2mm_awaddr
    s2mm.aw.bits.len   := bb.io.m_axi_s2mm_awlen
    s2mm.aw.bits.size  := bb.io.m_axi_s2mm_awsize
    s2mm.aw.bits.burst := bb.io.m_axi_s2mm_awburst
    s2mm.aw.bits.lock  := 0.U
    s2mm.aw.bits.cache := bb.io.m_axi_s2mm_awcache
    s2mm.aw.bits.prot  := bb.io.m_axi_s2mm_awprot
    s2mm.aw.bits.qos   := 0.U
    bb.io.m_axi_s2mm_awready := s2mm.aw.ready

    s2mm.w.valid     := bb.io.m_axi_s2mm_wvalid
    s2mm.w.bits.data := bb.io.m_axi_s2mm_wdata
    s2mm.w.bits.strb := bb.io.m_axi_s2mm_wstrb
    s2mm.w.bits.last := bb.io.m_axi_s2mm_wlast
    bb.io.m_axi_s2mm_wready := s2mm.w.ready

    bb.io.m_axi_s2mm_bresp  := s2mm.b.bits.resp
    bb.io.m_axi_s2mm_bvalid := s2mm.b.valid
    s2mm.b.ready            := bb.io.m_axi_s2mm_bready
  }
}
