open_hw_manager
connect_hw_server

set bit_file {/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/NexysVideoHarness-xradar-rocc-pipelined-75mhz-timingclean-2026-06-09.bit}

set targets [get_hw_targets]
puts "HW_TARGETS: $targets"

set ordered_targets {}
foreach target $targets {
  if {[string match {*210276689939B*} $target]} {
    set ordered_targets [linsert $ordered_targets 0 $target]
  } else {
    lappend ordered_targets $target
  }
}

set selected_target {}
foreach target $ordered_targets {
  puts "TRY_HW_TARGET: $target"
  if {[catch {
    current_hw_target $target
    open_hw_target $target
  } err]} {
    puts "WARN: open_hw_target failed for $target: $err"
    continue
  }

  set devices [get_hw_devices xc7a200t*]
  puts "DEVICES_ON_TARGET: $target => $devices"
  if {[llength $devices] != 0} {
    set selected_target $target
    break
  }

  catch {close_hw_target $target}
}

if {$selected_target eq {}} {
  puts "ERROR: no hw_target with xc7a200t device found"
  exit 2
}

puts "SELECTED_HW_TARGET: $selected_target"

set devices [get_hw_devices xc7a200t*]
if {[llength $devices] == 0} {
  puts "ERROR: no xc7a200t hardware device found"
  exit 2
}

set dev [lindex $devices 0]
current_hw_device $dev
refresh_hw_device -update_hw_probes false $dev
set_property PROGRAM.FILE $bit_file $dev
program_hw_devices $dev
refresh_hw_device $dev

puts "PROGRAM_DONE: $bit_file"
exit
