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
            qmlpCtrlReg := nextCtrl & 1.U(32.W)
            qmlpClearCounters := nextCtrl(1)
          }
        }
      }

      switch (ctrlBridge.io.local.rdAddr) {
        is ("h00".U) { localReadData := preprocCtrlReg }
        is ("h04".U) { localReadData := preprocModeReg }
        is ("h08".U) { localReadData := preprocParam0Reg }
        is ("h0c".U) { localReadData := preprocParam1Reg }
        is ("h10".U) { localReadData := preproc.io.status }
        is ("h14".U) { localReadData := preproc.io.inBeats }
        is ("h18".U) { localReadData := preproc.io.outBeats }
        is ("h1c".U) { localReadData := preproc.io.frameCount }
        is ("h20".U) { localReadData := preproc.io.lastKeep }
        is ("h24".U) { localReadData := preproc.io.capabilities }
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

    preproc.io.in.valid := bb.io.m_axis_mm2s_tvalid && !qmlpEnabled
    preproc.io.in.bits.data := bb.io.m_axis_mm2s_tdata
    preproc.io.in.bits.keep := bb.io.m_axis_mm2s_tkeep
    preproc.io.in.bits.last := bb.io.m_axis_mm2s_tlast
    preproc.io.out.ready := bb.io.s_axis_s2mm_tready && !qmlpEnabled

    qmlp.io.in.valid := bb.io.m_axis_mm2s_tvalid && qmlpEnabled
    qmlp.io.in.bits.data := bb.io.m_axis_mm2s_tdata
    qmlp.io.in.bits.keep := bb.io.m_axis_mm2s_tkeep
    qmlp.io.in.bits.last := bb.io.m_axis_mm2s_tlast
    qmlp.io.out.ready := bb.io.s_axis_s2mm_tready && qmlpEnabled

    bb.io.m_axis_mm2s_tready := Mux(qmlpEnabled, qmlp.io.in.ready, preproc.io.in.ready)
    bb.io.s_axis_s2mm_tdata  := Mux(qmlpEnabled, qmlp.io.out.bits.data, preproc.io.out.bits.data)
    bb.io.s_axis_s2mm_tkeep  := Mux(qmlpEnabled, qmlp.io.out.bits.keep, preproc.io.out.bits.keep)
    bb.io.s_axis_s2mm_tvalid := Mux(qmlpEnabled, qmlp.io.out.valid, preproc.io.out.valid)
    bb.io.s_axis_s2mm_tlast  := Mux(qmlpEnabled, qmlp.io.out.bits.last, preproc.io.out.bits.last)

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
