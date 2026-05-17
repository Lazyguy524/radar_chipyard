// See LICENSE for license details.
package chipyard.fpga.nexysvideo

import chisel3._

import freechips.rocketchip.subsystem.{PeripheryBusKey}
import freechips.rocketchip.tilelink.{TLBundle}
import freechips.rocketchip.util.{HeterogeneousBag}
import freechips.rocketchip.diplomacy.{LazyRawModuleImp}
import org.chipsalliance.diplomacy.nodes.{HeterogeneousBag}

import sifive.blocks.devices.uart.{UARTParams}

import chipyard._
import chipyard.harness._
import chipyard.iobinders._

class WithNexysVideoUARTTSI(uartBaudRate: BigInt = 115200) extends HarnessBinder({
  case (th: HasHarnessInstantiators, port: UARTTSIPort, chipId: Int) => {
    val nexysvideoth = th.asInstanceOf[LazyRawModuleImp].wrapper.asInstanceOf[NexysVideoHarness]
    nexysvideoth.io_uart_bb.bundle <> port.io.uart
    nexysvideoth.other_leds(1) := nexysvideoth.ddrOverlay.map(_.mig.module.io.port.init_calib_complete).getOrElse(false.B)
    nexysvideoth.other_leds(2) := nexysvideoth.radarDMA.map(_.module.debug.mm2sStreamBeat16Seen).getOrElse(false.B)
    nexysvideoth.other_leds(3) := nexysvideoth.radarDMA.map(_.module.debug.mm2sStreamBeat32Seen).getOrElse(false.B)
    nexysvideoth.other_leds(4) := nexysvideoth.radarDMA.map(_.module.debug.s2mmWriteBeat16Seen).getOrElse(false.B)
    nexysvideoth.other_leds(5) := nexysvideoth.radarDMA.map(_.module.debug.s2mmWriteBeat32Seen).getOrElse(false.B)
  }
})

class WithNexysVideoDDRTL extends HarnessBinder({
  case (th: HasHarnessInstantiators, port: TLMemPort, chipId: Int) => {
    val nexysTh = th.asInstanceOf[LazyRawModuleImp].wrapper.asInstanceOf[NexysVideoHarness]
    val bundles = nexysTh.ddrClient.get.out.map(_._1)
    val ddrClientBundle = Wire(new HeterogeneousBag(bundles.map(_.cloneType)))
    bundles.zip(ddrClientBundle).foreach { case (bundle, io) => bundle <> io }
    ddrClientBundle <> port.io
  }
})

class WithNexysVideoAXI4MMIO extends HarnessBinder({
  case (th: HasHarnessInstantiators, port: AXI4MMIOPort, chipId: Int) => {
    val nexysTh = th.asInstanceOf[LazyRawModuleImp].wrapper.asInstanceOf[NexysVideoHarness]
    val dma = nexysTh.radarDMA.get
    dma.module.ctrlClock := port.io.clock
    dma.module.ctrlResetN := !th.harnessBinderReset.asBool
    dma.module.ctrl <> port.io.bits
  }
})

class WithNexysVideoFullChainAXI4MMIO extends HarnessBinder({
  case (th: HasHarnessInstantiators, port: AXI4MMIOPort, chipId: Int) => {
    val nexysTh = th.asInstanceOf[LazyRawModuleImp].wrapper.asInstanceOf[NexysVideoHarness]
    val dma = nexysTh.fullChainDMA.get
    dma.module.ctrlClock := port.io.clock
    dma.module.ctrlResetN := !th.harnessBinderReset.asBool
    dma.module.ctrl <> port.io.bits
  }
})
