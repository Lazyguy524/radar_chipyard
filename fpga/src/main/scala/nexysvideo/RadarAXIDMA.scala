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

class RadarAXI4ToAXI4LiteBridge(params: RadarAXIDMAControlParams, liteAddrBits: Int = 10) extends Module {
  private val full = AXI4BundleParameters(
    addrBits = params.addrBits,
    dataBits = params.dataBits,
    idBits   = params.idBits)

  val io = IO(new Bundle {
    val in   = Flipped(new AXI4Bundle(full))
    val lite = new RadarAXI4LiteMasterIO(liteAddrBits)
  })

  val awHeld    = RegInit(false.B)
  val wHeld     = RegInit(false.B)
  val awSent    = RegInit(false.B)
  val wSent     = RegInit(false.B)
  val bPending  = RegInit(false.B)
  val awAddrReg = Reg(UInt(params.addrBits.W))
  val awIdReg   = Reg(UInt(params.idBits.W))
  val wDataReg  = Reg(UInt(params.dataBits.W))
  val wStrbReg  = Reg(UInt((params.dataBits / 8).W))

  val arHeld    = RegInit(false.B)
  val arSent    = RegInit(false.B)
  val rPending  = RegInit(false.B)
  val arAddrReg = Reg(UInt(params.addrBits.W))
  val arIdReg   = Reg(UInt(params.idBits.W))
  val rDataReg  = Reg(UInt(32.W))
  val rRespReg  = Reg(UInt(2.W))

  val writeBusy = awHeld || wHeld || awSent || wSent || bPending
  val readBusy  = arHeld || arSent || rPending

  io.in.aw.ready := !awHeld && !awSent && !bPending
  io.in.w.ready  := !wHeld && !wSent && !bPending
  io.in.ar.ready := !arHeld && !arSent && !rPending

  when (io.in.aw.fire) {
    awHeld    := true.B
    awAddrReg := io.in.aw.bits.addr
    awIdReg   := io.in.aw.bits.id
  }

  when (io.in.w.fire) {
    wHeld    := true.B
    wDataReg := io.in.w.bits.data
    wStrbReg := io.in.w.bits.strb
  }

  val writeUpperWord = awAddrReg(2)
  val liteWriteData  = Mux(writeUpperWord, wDataReg(63, 32), wDataReg(31, 0))
  val liteWriteStrb  = Mux(writeUpperWord, wStrbReg(7, 4), wStrbReg(3, 0))

  io.lite.awvalid := awHeld && !awSent
  io.lite.awaddr  := awAddrReg(liteAddrBits - 1, 0)
  io.lite.wvalid  := wHeld && !wSent
  io.lite.wdata   := liteWriteData
  io.lite.wstrb   := liteWriteStrb
  io.lite.bready  := !bPending

  when (io.lite.awvalid && io.lite.awready) {
    awSent := true.B
    awHeld := false.B
  }

  when (io.lite.wvalid && io.lite.wready) {
    wSent := true.B
    wHeld := false.B
  }

  when (!bPending && awSent && wSent) {
    bPending := true.B
  }

  io.in.b.valid := bPending && io.lite.bvalid
  io.in.b.bits.id := awIdReg
  io.in.b.bits.resp := io.lite.bresp
  io.in.b.bits.user := DontCare

  when (io.in.b.fire) {
    awSent   := false.B
    wSent    := false.B
    bPending := false.B
  }

  io.lite.arvalid := arHeld && !arSent
  io.lite.araddr  := arAddrReg(liteAddrBits - 1, 0)
  io.lite.rready  := !rPending

  when (io.in.ar.fire) {
    arHeld    := true.B
    arSent    := false.B
    arAddrReg := io.in.ar.bits.addr
    arIdReg   := io.in.ar.bits.id
  }

  when (io.lite.arvalid && io.lite.arready) {
    arSent := true.B
    arHeld := false.B
  }

  when (!rPending && arSent && io.lite.rvalid) {
    rPending := true.B
    rDataReg := io.lite.rdata
    rRespReg := io.lite.rresp
  }

  val replicatedReadData = Cat(rDataReg, rDataReg)
  io.in.r.valid := rPending
  io.in.r.bits.id := arIdReg
  io.in.r.bits.data := replicatedReadData
  io.in.r.bits.resp := rRespReg
  io.in.r.bits.last := true.B
  io.in.r.bits.user := DontCare

  when (io.in.r.fire) {
    arSent   := false.B
    rPending := false.B
  }
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
    ctrlBridge.io.in <> ctrl

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

    bb.io.m_axis_mm2s_tready := bb.io.s_axis_s2mm_tready
    bb.io.s_axis_s2mm_tdata  := bb.io.m_axis_mm2s_tdata
    bb.io.s_axis_s2mm_tkeep  := bb.io.m_axis_mm2s_tkeep
    bb.io.s_axis_s2mm_tvalid := bb.io.m_axis_mm2s_tvalid
    bb.io.s_axis_s2mm_tlast  := bb.io.m_axis_mm2s_tlast

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
