.section .data
.align 8
kv_index:
    .quad 8
.section .bss
.align 4096
kv_buf:
    .skip 0x20000
.section .text
.globl kv3store
kv3store:
    pushq %rbp
    movq %rsp, %rbp
    leaq kv_index(%rip), %r8
    leaq kv_buf(%rip), %rdi
    movq $1, %rdx
    testq %rdx, %rdx
kv3store_branch:
    jne kv3store_end
    movq (%r8), %rax
    shlq $12, %rax
kv3store_xmit:
    movq $0, (%rdi,%rax)
kv3store_end:
    movq %rbp, %rsp
    popq %rbp
    ret
