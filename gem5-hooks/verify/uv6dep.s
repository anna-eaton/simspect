# SimSpect hooks verification gadget (SpecLFB, dependent variant): 2nd spec load address depends on the 1st (Spectre shape) to exercise the LFB path.
# unresolved by the annotation's resolve stall) guards TWO speculative loads to cold lines
# on a TLB-warm page. UV6 = the first unsafe load is classified safe and installs in L1D
# in-window; the second is held (LFB / stalled). Committed load to +0x800 warms the page.
.section .bss
.align 4096
ub_buf:
    .skip 0x2000
.section .text
.globl uv6dep
uv6dep:
    pushq %rbp
    movq %rsp, %rbp
    leaq ub_buf(%rip), %rdi
    movq 0x800(%rdi), %rcx
    movq $1, %rdx
    testq %rdx, %rdx
uv6dep_branch:
    jne uv6dep_end
uv6dep_xmit:
    movq 0x0(%rdi), %rax
    movq 0x100(%rdi,%rax,1), %rbx
uv6dep_end:
    movq %rbp, %rsp
    popq %rbp
    ret
