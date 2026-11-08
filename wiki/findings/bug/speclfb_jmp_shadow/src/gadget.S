/*
 * jmp-shadow probe gadget (SpecLFB), 2026-11-08.
 * Natural Spectre-v1 shape: no SimSpect branch force, no resolve hold.
 *   void gadget(uint64_t x, uint64_t *sizep, uint8_t *array1, uint8_t *probe)
 *   rdi = x, rsi = sizep (a cold line, so the bounds check stays unresolved
 *   for a full memory round trip), rdx = array1, rcx = probe.
 * The bounds-check branch is trained not-taken by the driver (x in bounds),
 * then called once with x out of bounds (array1[x] = the secret byte).
 *
 * Body (wrong path on the last call):
 *   1. a sacrificial first speculative load (array1[1], an L1 hit): absorbs
 *      UV6 ("first speculative load is not protected") so it cannot explain
 *      the transmitter;
 *   2. 24 nops: push the secret load and the transmitter into a later rename
 *      group, so the ROB walk sees them after the LSQ walk has given the
 *      sacrificial load CUSL (rules out the walk-order / PrevNoUnsafe lag);
 *   3. SHADOW_OP: the instruction under test (see below);
 *   4. s = array1[x] (secret, an L1 hit), then the transmitter probe[s*4096]
 *      (a cold miss).
 *
 * SHADOW variants (-DSHADOW=<n>):
 *   0 none        nothing
 *   1 jmp         direct unconditional jmp to the next instruction (EB 00)
 *   2 nop2        same-length (2-byte) nop 66 90: timing/layout control for 1
 *   3 callret     direct call to a function that just returns (call + ret)
 *   4 callpop     direct call to the next instruction, then rsp += 8 (call, no ret)
 *   5 jcc_ready   younger conditional branch on a ready register (resolves fast)
 *   6 jmp_ind     indirect jmp through a register to the next instruction
 *   7 jmp_before  the direct jmp placed BEFORE the bounds-check branch (older)
 *   8 jmp_after   the direct jmp placed AFTER the transmitter (younger)
 *   9 ret_only    push next-address + ret (a return without a call)
 *  10 jmp_far     direct jmp with a 5-byte encoding (E9 rel32) to next instruction
 */
#ifndef SHADOW
#define SHADOW 0
#endif

    .text
    .globl gadget
    .type gadget, @function
gadget:
#if SHADOW == 7
    jmp 70f
70:
#endif
    movq (%rsi), %r8            /* cold: the bound */
    cmpq %r8, %rdi
    jae 99f                      /* bounds check (trained not-taken) */
    movzbl 1(%rdx), %r9d         /* sacrificial first speculative load (hit) */
    .rept 24
    nop
    .endr
#if SHADOW == 1
    jmp 10f
10:
#elif SHADOW == 2
    .byte 0x66, 0x90
#elif SHADOW == 3
    call ret_stub
#elif SHADOW == 4
    call 40f
40:
    leaq 8(%rsp), %rsp
#elif SHADOW == 5
    testq %rdx, %rdx
    je 50f
50:
#elif SHADOW == 6
    leaq 60f(%rip), %r11
    jmp *%r11
60:
#elif SHADOW == 9
    leaq 90f(%rip), %r11
    pushq %r11
    ret
90:
#elif SHADOW == 10
    .byte 0xe9
    .long 0
#endif
    movzbl (%rdx,%rdi), %eax     /* secret load s = array1[x] */
    shlq $12, %rax
    movzbl (%rcx,%rax), %eax     /* transmitter: probe[s * 4096] */
#if SHADOW == 8
    jmp 80f
80:
#endif
99:
    ret
    .size gadget, .-gadget

    .globl ret_stub
    .type ret_stub, @function
ret_stub:
    ret
    .size ret_stub, .-ret_stub
    .section .note.GNU-stack,"",@progbits
