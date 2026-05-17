if {$argc != 2} {
  puts "usage: check_fullchain_dma_ip.tcl <generated_dma_tcl> <ipdir>"
  exit 2
}

set generated_dma_tcl [lindex $argv 0]
set ipdir [lindex $argv 1]

file delete -force $ipdir
file mkdir $ipdir

create_project -in_memory -part xc7a200tsbg484-1
source $generated_dma_tcl

set ip [get_ips full_chain_axi_dma]
set mm2s_stream_width [get_property CONFIG.c_m_axis_mm2s_tdata_width $ip]
set s2mm_stream_width [get_property CONFIG.c_s_axis_s2mm_tdata_width $ip]
set mm2s_mem_width [get_property CONFIG.c_m_axi_mm2s_data_width $ip]
set s2mm_mem_width [get_property CONFIG.c_m_axi_s2mm_data_width $ip]

puts "IP_NAME=[get_property NAME $ip]"
puts "MM2S_STREAM_WIDTH=$mm2s_stream_width"
puts "S2MM_STREAM_WIDTH=$s2mm_stream_width"
puts "MM2S_MEM_WIDTH=$mm2s_mem_width"
puts "S2MM_MEM_WIDTH=$s2mm_mem_width"

if {$mm2s_stream_width != 32} {
  puts "ERROR: expected MM2S stream width 32"
  exit 1
}
if {$s2mm_stream_width != 64} {
  puts "ERROR: expected S2MM stream width 64"
  exit 1
}
if {$mm2s_mem_width != 64 || $s2mm_mem_width != 64} {
  puts "ERROR: expected 64-bit memory-mapped DMA widths"
  exit 1
}

puts "FULLCHAIN_DMA_IP_CHECK_OK"
exit 0
