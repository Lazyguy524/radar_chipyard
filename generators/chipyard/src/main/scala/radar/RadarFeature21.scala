package chipyard.radar

import chisel3._
import chisel3.util._

class RadarAXISFeature21Preprocessor extends Module {
  private val maxPoints = 511
  private val inputBeatsPerPoint = 1
  private val outputBeats = 4

  val io = IO(new Bundle {
    val ctrlEnable = Input(Bool())
    val abort = Input(Bool())

    val in = Flipped(Decoupled(new RadarAXISWord))
    val out = Decoupled(new RadarAXISWord)

    val clearCounters = Input(Bool())
    val inBeats       = Output(UInt(32.W))
    val outBeats      = Output(UInt(32.W))
    val frameCount    = Output(UInt(32.W))
    val lastKeep      = Output(UInt(8.W))
    val status        = Output(UInt(32.W))
    val capabilities  = Output(UInt(32.W))
    val sleepSafe      = Output(Bool())
  })

  private val (
    sIdle :: sAccum ::
    sMeanX :: sMeanY :: sMeanDoppler :: sMeanRcs ::
    sDensityArea :: sDensityNormalize :: sDensityMul ::
    sDensityShift :: sDensityQuantMul :: sDensityQuantRound ::
    sFeatureSelect :: sFeatureQuantMul :: sFeatureQuantRound ::
    sFeatureWrite :: sEmit :: sSkipPoints :: Nil) = Enum(18)

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
    // abs16 is unsigned because |-32768| needs all 16 magnitude bits.
    // Preserve the carry here: the approximation can reach 49152, which
    // needs a positive signed 17-bit result.
    (hi +& (lo >> 1)).asSInt
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
  val skipRemaining = RegInit(0.U(16.W))
  val protocolErrorReg = RegInit(false.B)
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
  val frameInputLastReg = RegInit(false.B)

  val inBeatsReg = RegInit(0.U(32.W))
  val outBeatsReg = RegInit(0.U(32.W))
  val framesReg = RegInit(0.U(32.W))
  val lastKeepReg = RegInit(0.U(8.W))

  // A signed-16 maximum minus minimum is in [0, 65535].  Extend both
  // operands before subtracting so cross-zero spans stay positive.
  private val spanX = (maxX.pad(17) - minX.pad(17)).asSInt
  private val spanY = (maxY.pad(17) - minY.pad(17)).asSInt
  private val spanDoppler = (maxDoppler.pad(17) - minDoppler.pad(17)).asSInt
  private val spanRcs = (maxRcs.pad(17) - minRcs.pad(17)).asSInt
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

  io.in.ready :=
    io.ctrlEnable &&
      (state === sIdle || state === sAccum || state === sSkipPoints)
  io.out.valid := outValidReg
  io.out.bits := outBitsReg

  switch (state) {
    is (sIdle) {
      when (!io.ctrlEnable) {
        outValidReg := false.B
      }

      when (io.in.fire) {
        val rawCount = io.in.bits.data(15, 0)
        val count = clampCount(rawCount)
        inBeatsReg := inBeatsReg + 1.U
        lastKeepReg := io.in.bits.keep
        when (io.in.bits.keep =/= "hff".U ||
              rawCount > maxPoints.U ||
              (io.in.bits.last && rawCount =/= 0.U)) {
          // The header is unusable.  When TLAST is absent, consume exactly
          // the declared point payload so the next beat is again a header.
          protocolErrorReg := true.B
          skipRemaining := rawCount
          state := Mux(io.in.bits.last || rawCount === 0.U, sIdle, sSkipPoints)
        } .otherwise {
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
          frameInputLastReg := io.in.bits.last
          state := Mux(count === 0.U, sMeanX, sAccum)
        }
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
        inBeatsReg := inBeatsReg + 1.U
        lastKeepReg := io.in.bits.keep
        when (io.in.bits.keep =/= "hff".U ||
              (io.in.bits.last && nextActual < expectedPoints)) {
          // Reject the whole sample.  A bad non-final point is skipped using
          // point_count, which preserves alignment for later batched samples.
          protocolErrorReg := true.B
          val remaining = expectedPoints - nextActual
          skipRemaining := remaining
          state := Mux(io.in.bits.last || remaining === 0.U, sIdle, sSkipPoints)
        } .otherwise {
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
          when (nextActual >= expectedPoints) {
            frameInputLastReg := io.in.bits.last
            state := sMeanX
          }
        }
      }
    }

    is (sSkipPoints) {
      when (io.in.fire) {
        inBeatsReg := inBeatsReg + 1.U
        lastKeepReg := io.in.bits.keep
        val lastDeclaredPoint = skipRemaining <= 1.U
        skipRemaining := Mux(lastDeclaredPoint, 0.U, skipRemaining - 1.U)
        when (io.in.bits.last || lastDeclaredPoint) {
          state := sIdle
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
          framesReg := framesReg + 1.U
          state := sIdle
        } .otherwise {
          val nextEmitIdx = emitIdx + 1.U
          emitIdx := nextEmitIdx
          outBitsReg.data := MuxLookup(nextEmitIdx, packedFeatureWords(0))(Seq(
            1.U -> packedFeatureWords(1),
            2.U -> packedFeatureWords(2),
            3.U -> packedFeatureWords(3)))
          outBitsReg.keep := "hff".U
          outBitsReg.last := frameInputLastReg && nextEmitIdx === (outputBeats - 1).U
        }
      }
    }

  }

  // Disabling is the local recovery operation for a truncated DMA packet.
  // Keep the sticky error/counters so software can diagnose the failure.
  when (!io.ctrlEnable || io.abort) {
    state := sIdle
    outValidReg := false.B
    skipRemaining := 0.U
  }

  // Counter/error clear wins over same-cycle stream events.
  when (io.clearCounters) {
    inBeatsReg := 0.U
    outBeatsReg := 0.U
    framesReg := 0.U
    lastKeepReg := 0.U
    protocolErrorReg := false.B
  }

  io.inBeats := inBeatsReg
  io.outBeats := outBeatsReg
  io.frameCount := framesReg
  io.lastKeep := lastKeepReg
  io.status :=
    state.asUInt |
      (io.ctrlEnable.asUInt << 5) |
      (io.in.valid.asUInt << 6) |
      (io.out.valid.asUInt << 7) |
      (io.out.ready.asUInt << 8) |
      (io.in.ready.asUInt << 9) |
      (outValidReg.asUInt << 10) |
      (protocolErrorReg.asUInt << 11) |
      ((state === sSkipPoints).asUInt << 12)
  io.sleepSafe :=
    state === sIdle &&
      !outValidReg &&
      !io.clearCounters &&
      !io.abort &&
      (!io.ctrlEnable || !io.in.valid)
  io.capabilities := "h00000020".U
}
