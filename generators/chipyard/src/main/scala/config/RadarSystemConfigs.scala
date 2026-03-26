package chipyard

import org.chipsalliance.cde.config.Config

object RadarSystemAddressMap {
  val ExtMemSize  = 0x20000000L
  val ExtMMIOBase = 0x60000000L
  val ExtMMIOSize = 0x00010000L
}

class WithRadarExternalAXI4Ports extends Config(
  new freechips.rocketchip.subsystem.WithCustomMMIOPort(
    RadarSystemAddressMap.ExtMMIOBase,
    RadarSystemAddressMap.ExtMMIOSize,
    64,
    4,
    8) ++
  new freechips.rocketchip.subsystem.WithExtMemSize(
    RadarSystemAddressMap.ExtMemSize))

class RadarSystemSimConfig extends Config(
  new chipyard.harness.WithSerialTLTiedOff ++
  new chipyard.harness.WithSimTSIToUARTTSI ++
  new chipyard.config.WithNoUART ++
  new testchipip.tsi.WithUARTTSIClient ++
  new WithRadarExternalAXI4Ports ++
  new chipyard.config.WithBroadcastManager ++
  new freechips.rocketchip.rocket.WithNBigCores(1) ++
  new chipyard.config.AbstractConfig)
