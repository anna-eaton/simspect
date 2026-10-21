.section .text
.globl kv1gadget
kv1gadget:
    pushq %rbp
    movq %rsp, %rbp
    movq $0, %rdx
    testq %rdx, %rdx
kv1_branch:
    jne kv1_far
    jmp kv1_end
    .align 64
    .skip 0x1000
kv1_far:
    nop
    nop
    nop
    jmp kv1_end
    .align 64
kv1_end:
    movq %rbp, %rsp
    popq %rbp
    ret
