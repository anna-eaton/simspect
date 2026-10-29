# SimSpect hooks verification gadget (SpecLFB UV6 shape): a mispredicted branch (held
# unresolved by the annotation's resolve stall) guards TWO speculative loads to cold lines
# on a TLB-warm page. UV6 = the first unsafe load is classified safe and installs in L1D
# in-window; the second is held (LFB / stalled). Committed load to +0x800 warms the page.
.section .bss
.align 4096
ub_buf:
    .skip 0x2000
.section .text
.globl uv6x
uv6x:
    pushq %rbp
    movq %rsp, %rbp
    leaq ub_buf(%rip), %rdi
    movq 0x800(%rdi), %rcx
    movq $1, %rdx
    testq %rdx, %rdx
uv6x_branch:
    jne uv6x_end
uv6x_xmit:
    movq 0x0(%rdi), %rax
    movq 0x100(%rdi), %rbx
uv6x_end:
    movq %rbp, %rsp
    popq %rbp
    ret
