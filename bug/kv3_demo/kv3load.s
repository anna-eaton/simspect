.section .data
.align 8
kv_index:
    .quad 8
.section .bss
.align 4096
kv_buf:
    .skip 0x20000
.section .text
.globl kv3load
kv3load:
    pushq %rbp
    movq %rsp, %rbp
    leaq kv_index(%rip), %r8
    leaq kv_buf(%rip), %rdi
    movq $1, %rdx
    testq %rdx, %rdx
kv3load_branch:
    jne kv3load_end
    movq (%r8), %rax
    shlq $12, %rax
kv3load_xmit:
    movq (%rdi,%rax), %rcx
kv3load_end:
    movq %rbp, %rsp
    popq %rbp
    ret
