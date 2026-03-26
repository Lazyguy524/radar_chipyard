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

// DOC include start: WithNexysVideoTweaks and Rocket
class WithNexysVideoTweaks extends Config(
  new WithNexysVideoUARTTSI ++
  new WithNexysVideoDDRTL ++
  new WithNoDesignKey ++
  new testchipip.tsi.WithUARTTSIClient ++
  new chipyard.harness.WithSerialTLTiedOff ++
  new chipyard.harness.WithHarnessBinderClockFreqMHz(50) ++
  new chipyard.config.WithMemoryBusFrequency(50.0) ++
  new chipyard.config.WithFrontBusFrequency(50.0) ++
  new chipyard.config.WithSystemBusFrequency(50.0) ++
  new chipyard.config.WithPeripheryBusFrequency(50.0) ++
  new chipyard.config.WithControlBusFrequency(50.0) ++
  new chipyard.harness.WithAllClocksFromHarnessClockInstantiator ++
  new chipyard.clocking.WithPassthroughClockGenerator ++
  new chipyard.config.WithNoDebug ++ // no jtag
  new chipyard.config.WithNoUART ++ // use UART for the UART-TSI thing instad
  new chipyard.config.WithTLBackingMemory ++ // FPGA-shells converts the AXI to TL for us
  new freechips.rocketchip.subsystem.WithExtMemSize(BigInt(512) << 20) ++ // 512mb on Nexys Video
  new freechips.rocketchip.subsystem.WithoutTLMonitors)

class RocketNexysVideoConfig extends Config(
  new WithNexysVideoTweaks ++
  new chipyard.config.WithBroadcastManager ++ // no l2
  new chipyard.RocketConfig)
// DOC include end: WithNexysVideoTweaks and Rocket

// DOC include start: WithTinyNexysVideoTweaks and Rocket
class WithTinyNexysVideoTweaks extends Config(
  new WithNexysVideoUARTTSI ++
  new WithNoDesignKey ++
  new sifive.fpgashells.shell.xilinx.WithNoNexysVideoShellDDR ++ // no DDR
  new testchipip.tsi.WithUARTTSIClient ++
  new chipyard.harness.WithSerialTLTiedOff ++
  new chipyard.harness.WithHarnessBinderClockFreqMHz(50) ++
  new chipyard.config.WithMemoryBusFrequency(50.0) ++
  new chipyard.config.WithFrontBusFrequency(50.0) ++
  new chipyard.config.WithSystemBusFrequency(50.0) ++
  new chipyard.config.WithPeripheryBusFrequency(50.0) ++
  new chipyard.config.WithControlBusFrequency(50.0) ++
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
  new chipyard.harness.WithHarnessBinderClockFreqMHz(50) ++
  new chipyard.config.WithMemoryBusFrequency(50.0) ++
  new chipyard.config.WithFrontBusFrequency(50.0) ++
  new chipyard.config.WithSystemBusFrequency(50.0) ++
  new chipyard.config.WithPeripheryBusFrequency(50.0) ++
  new chipyard.config.WithControlBusFrequency(50.0) ++
  new chipyard.harness.WithAllClocksFromHarnessClockInstantiator ++
  new chipyard.clocking.WithPassthroughClockGenerator ++
  new chipyard.config.WithNoDebug ++ // no jtag
  new chipyard.config.WithNoUART ++ // use UART for the UART-TSI thing instad
  new chipyard.config.WithTLBackingMemory ++ // FPGA-shells converts the AXI to TL for us
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

class RadarAXIMMIONexysVideoConfig extends Config(
  new WithNexysVideoAXI4MMIO ++
  new freechips.rocketchip.subsystem.WithCustomMMIOPort(
    RadarAXIMMIOAddressMap.PreprocBase,
    RadarAXIMMIOAddressMap.WindowSize,
    64,
    4,
    8) ++
  new WithNexysVideoTweaks ++
  new testchipip.soc.WithNoScratchpads ++
  new chipyard.config.WithBroadcastManager ++
  new freechips.rocketchip.rocket.WithoutFPU ++
  new freechips.rocketchip.rocket.WithNSmallCores(1) ++
  new chipyard.config.AbstractConfig)

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
