.section .bss
.align 4096
tb_buf:
    .skip 0x4000
.section .text
.globl uv2x
uv2x:
    pushq %rbp
    movq %rsp, %rbp
    leaq tb_buf(%rip), %rdi
    movq 0xf00(%rdi), %r11
    movq $1, %rdx
    testq %rdx, %rdx
uv2x_branch:
    jne uv2x_end
    movq 0x000(%rdi), %rax
    movq 0x040(%rdi), %r8
    movq 0x080(%rdi), %r9
    movq 0x0c0(%rdi), %r10
uv2x_end:
    movq %rbp, %rsp
    popq %rbp
    ret
