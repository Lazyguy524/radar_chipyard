// See LICENSE for license details.
package chipyard.fpga.nexysvideo

import gemmini._
import org.chipsalliance.cde.config._
import freechips.rocketchip.subsystem._
import freechips.rocketchip.devices.debug._
import freechips.rocketchip.devices.tilelink._
import org.chipsalliance.diplomacy.lazymodule._
import freechips.rocketchip.system._
import freechips.rocketchip.tile._

import sifive.blocks.devices.uart._
import sifive.fpgashells.shell.{DesignKey}

import testchipip.serdes.{SerialTLKey}

import chipyard.{BuildSystem}

// don't use FPGAShell's DesignKey
class WithNoDesignKey extends Config((site, here, up) => {
  case DesignKey => (p: Parameters) => new SimpleLazyRawModule()(p)
})

object RadarAXIMMIOAddressMap {
  val PreprocBase  = 0x60000000L
  val ClusterBase  = 0x60001000L
  val DetectBase   = 0x60002000L
  val ReservedBase = 0x60003000L
  val WindowSize   = 0x00010000L
}

object RadarDDRAddressMap {
  val CachedBase        = 0x80000000L
  val SizeBytes         = 0x20000000L
  val IncohAliasOffset  = 0x1000000000L
}

// DOC include start: WithNexysVideoTweaks and Rocket
class WithNexysVideoTweaks(freqMHz: Double = 50.0) extends Config(
  new WithNexysVideoUARTTSI ++
  new WithNexysVideoDDRTL ++
  new WithNoDesignKey ++
  new testchipip.tsi.WithUARTTSIClient ++
  new chipyard.harness.WithSerialTLTiedOff ++
  new chipyard.harness.WithHarnessBinderClockFreqMHz(freqMHz) ++
  new chipyard.config.WithMemoryBusFrequency(freqMHz) ++
  new chipyard.config.WithFrontBusFrequency(freqMHz) ++
  new chipyard.config.WithSystemBusFrequency(freqMHz) ++
  new chipyard.config.WithPeripheryBusFrequency(freqMHz) ++
  new chipyard.config.WithControlBusFrequency(freqMHz) ++
  new chipyard.harness.WithAllClocksFromHarnessClockInstantiator ++
  new chipyard.clocking.WithPassthroughClockGenerator ++
  new chipyard.config.WithNoDebug ++ // no jtag
  new chipyard.config.WithNoUART ++ // use UART for the UART-TSI thing instad
  new chipyard.config.WithTLBackingMemory ++ // FPGA-shells converts the AXI to TL for us
  new freechips.rocketchip.subsystem.WithExtMemSbusBypass(RadarDDRAddressMap.IncohAliasOffset) ++
  new freechips.rocketchip.subsystem.WithExtMemSize(BigInt(512) << 20) ++ // 512mb on Nexys Video
  new freechips.rocketchip.subsystem.WithoutTLMonitors)

class RocketNexysVideoConfig extends Config(
  new WithNexysVideoTweaks ++
  new chipyard.config.WithBroadcastManager ++ // no l2
  new chipyard.RocketConfig)
// DOC include end: WithNexysVideoTweaks and Rocket

// DOC include start: WithTinyNexysVideoTweaks and Rocket
class WithTinyNexysVideoTweaks(freqMHz: Double = 50.0) extends Config(
  new WithNexysVideoUARTTSI ++
  new WithNoDesignKey ++
  new sifive.fpgashells.shell.xilinx.WithNoNexysVideoShellDDR ++ // no DDR
  new testchipip.tsi.WithUARTTSIClient ++
  new chipyard.harness.WithSerialTLTiedOff ++
  new chipyard.harness.WithHarnessBinderClockFreqMHz(freqMHz) ++
  new chipyard.config.WithMemoryBusFrequency(freqMHz) ++
  new chipyard.config.WithFrontBusFrequency(freqMHz) ++
  new chipyard.config.WithSystemBusFrequency(freqMHz) ++
  new chipyard.config.WithPeripheryBusFrequency(freqMHz) ++
  new chipyard.config.WithControlBusFrequency(freqMHz) ++
  new chipyard.harness.WithAllClocksFromHarnessClockInstantiator ++
  new chipyard.clocking.WithPassthroughClockGenerator ++
  new chipyard.config.WithNoDebug ++ // no jtag
  new chipyard.config.WithNoUART ++ // use UART for the UART-TSI thing instad
  new freechips.rocketchip.subsystem.WithoutTLMonitors)

class TinyRocketNexysVideoConfig extends Config(
  new WithTinyNexysVideoTweaks ++
  new chipyard.config.WithBroadcastManager ++ // no l2
  new chipyard.TinyRocketConfig)
// DOC include end: WithTinyNexysVideoTweaks and Rocket

// DOC include start: WithNexysVideoTweaks and Rocket
class WithRadarNexysVideoTweaks(freqMHz: Double = 50) extends Config(
  new WithNexysVideoUARTTSI ++
  new WithNexysVideoDDRTL ++
  new WithNoDesignKey ++
  new testchipip.tsi.WithUARTTSIClient ++
  new chipyard.harness.WithSerialTLTiedOff ++
  new chipyard.harness.WithHarnessBinderClockFreqMHz(freqMHz) ++
  new chipyard.config.WithMemoryBusFrequency(freqMHz) ++
  new chipyard.config.WithFrontBusFrequency(freqMHz) ++
  new chipyard.config.WithSystemBusFrequency(freqMHz) ++
  new chipyard.config.WithPeripheryBusFrequency(freqMHz) ++
  new chipyard.config.WithControlBusFrequency(freqMHz) ++
  new chipyard.harness.WithAllClocksFromHarnessClockInstantiator ++
  new chipyard.clocking.WithPassthroughClockGenerator ++
  new chipyard.config.WithNoDebug ++ // no jtag
  new chipyard.config.WithNoUART ++ // use UART for the UART-TSI thing instad
  new chipyard.config.WithTLBackingMemory ++ // FPGA-shells converts the AXI to TL for us
  new freechips.rocketchip.subsystem.WithExtMemSbusBypass(RadarDDRAddressMap.IncohAliasOffset) ++
  new freechips.rocketchip.subsystem.WithExtMemSize(BigInt(512) << 20) ++ // 512mb on Nexys Video
  new freechips.rocketchip.subsystem.WithoutTLMonitors)

class WithRadarRocketCore extends Config((site, here, up) => {  
  case TilesLocated(InSubsystem) => up(TilesLocated(InSubsystem)) map {  
    case tp: RocketTileAttachParams => tp.copy(tileParams = tp.tileParams.copy(  
      core = tp.tileParams.core.copy(fpu = None)  // 移除 FPU  
    ))  
    case other => other  
  }  
}) 

class RadarNexysVideoConfig extends Config(
  new gemmini.LeanGemminiConfig ++
  new WithRadarNexysVideoTweaks ++
  new chipyard.config.WithBroadcastManager ++ // no l2
  //new WithRadarRocketCore ++ //remove FPU
  new chipyard.RocketConfig)
// DOC include end: WithNexysVideoTweaks and Rocket

class GenericRadarNexysVideoConfig extends Config(
  new WithNexysVideoTweaks ++
  new chipyard.radar.WithGenericRadarShell ++
  new chipyard.config.WithBroadcastManager ++ // no l2
  new freechips.rocketchip.rocket.WithoutFPU ++
  new freechips.rocketchip.rocket.WithNSmallCores(1) ++
  new chipyard.config.AbstractConfig)

class RadarAXIMMIONexysVideoFreqConfig(freqMHz: Double = 50.0) extends Config(
  new WithNexysVideoAXI4MMIO ++
  new freechips.rocketchip.subsystem.WithCustomMMIOPort(
    RadarAXIMMIOAddressMap.PreprocBase,
    RadarAXIMMIOAddressMap.WindowSize,
    64,
    4,
    8) ++
  new WithNexysVideoTweaks(freqMHz = freqMHz) ++
  new testchipip.soc.WithNoScratchpads ++
  new chipyard.config.WithBroadcastManager ++
  new freechips.rocketchip.rocket.WithoutFPU ++
  new freechips.rocketchip.rocket.WithNSmallCores(1) ++
  new chipyard.config.AbstractConfig)

class RadarAXIMMIONexysVideoConfig extends RadarAXIMMIONexysVideoFreqConfig(50.0)
class RadarAXIMMIONexysVideo51p282MHzConfig extends RadarAXIMMIONexysVideoFreqConfig(51.282051)
class RadarAXIMMIONexysVideo55MHzConfig extends RadarAXIMMIONexysVideoFreqConfig(55.0)
class RadarAXIMMIONexysVideo60MHzConfig extends RadarAXIMMIONexysVideoFreqConfig(60.0)
class RadarAXIMMIONexysVideo65MHzConfig extends RadarAXIMMIONexysVideoFreqConfig(65.0)
class RadarAXIMMIONexysVideo66p667MHzConfig extends RadarAXIMMIONexysVideoFreqConfig(66.666667)
class RadarAXIMMIONexysVideo75MHzConfig extends RadarAXIMMIONexysVideoFreqConfig(75.0)
class RadarAXIMMIOXradarRoCCNexysVideo75MHzConfig extends Config(
  new WithXradarRoCC(OpcodeSet.custom0) ++
  new RadarAXIMMIONexysVideoFreqConfig(75.0))

class RadarAXIMMIOSimConfig extends Config(
  new freechips.rocketchip.subsystem.WithCustomMMIOPort(
    RadarAXIMMIOAddressMap.PreprocBase,
    RadarAXIMMIOAddressMap.WindowSize,
    64,
    4,
    8) ++
  new freechips.rocketchip.subsystem.WithExtMemSize(BigInt(512) << 20) ++
  new testchipip.soc.WithNoScratchpads ++
  new chipyard.config.WithBroadcastManager ++
  new freechips.rocketchip.rocket.WithoutFPU ++
  new freechips.rocketchip.rocket.WithNSmallCores(1) ++
  new chipyard.config.AbstractConfig)
