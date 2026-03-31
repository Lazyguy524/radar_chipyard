    .section .text.init
    .global _start
    .type _start, @function

_start:
    .option push
    .option norelax
    la gp, __global_pointer$
    .option pop

    la sp, __stack_start
    lui t0, %hi(__stack_size)
    addi t0, t0, %lo(__stack_size)
    add sp, sp, t0

    la t0, trap_entry
    csrw mtvec, t0

    call main
    tail htif_exit

trap_entry:
    li a0, 129
    tail htif_exit
