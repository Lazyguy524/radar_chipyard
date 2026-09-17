package chipyard.radar

import chisel3._

class RadarAXISWord extends Bundle {
  val data = UInt(64.W)
  val keep = UInt(8.W)
  val last = Bool()
}
