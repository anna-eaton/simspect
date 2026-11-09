	.text
	.file	"inst-000001.ll"
	.globl	"inst-000001"                   # -- Begin function inst-000001
	.p2align	4, 0x90
	.type	"inst-000001",@function
"inst-000001":                          # @inst-000001
	.cfi_startproc
# %bb.0:                                # %entry
	pushq	%r13
	.cfi_def_cfa_offset 16
	.cfi_offset %r13, -16
	movq	$0, -8(%rsp)
	xorl	%eax, %eax
	#APP
	movq	%rax, %r10
	#NO_APP
	#APP
	movq	%rax, %r13
	#NO_APP
	#APP
	movq	%rax, %rdi
	#NO_APP
	#APP
	mfence
	#NO_APP
	leaq	-8(%rsp), %rsi
	#APP
	.globl	__litmus_inst_000001_pc0
__litmus_inst_000001_pc0:
	.globl	__litmus_inst_000001_first_noncommitted
__litmus_inst_000001_first_noncommitted:
	movq	%r10, (%rsi)
	#NO_APP
	#APP
	.globl	__litmus_inst_000001_pc1
__litmus_inst_000001_pc1:
	movq	(%rsi), %r11
	#NO_APP
	#APP
	.globl	__litmus_inst_000001_pc2
__litmus_inst_000001_pc2:
	movq	(%rsi), %rax
	#NO_APP
	#APP
	.globl	__litmus_inst_000001_pc3
__litmus_inst_000001_pc3:
	movq	%rax, %rcx
	#NO_APP
	testq	%rcx, %rcx
	je	.LBB0_3
# %bb.1:                                # %bb_4
	#APP
	.globl	__litmus_inst_000001_pc4
__litmus_inst_000001_pc4:
	movq	%r13, %rax
	imulq	%r10, %rax
	#NO_APP
	#APP
	.globl	__litmus_inst_000001_pc5
__litmus_inst_000001_pc5:
	xorq	%rdx, %rdx
	#NO_APP
	testq	%rdx, %rdx
	jne	.LBB0_3
# %bb.2:                                # %ftbypass_5
	#APP
	.globl	__litmus_inst_000001_ftbypass5
__litmus_inst_000001_ftbypass5:
	#NO_APP
.LBB0_3:                                # %end_block
	xorl	%eax, %eax
	popq	%r13
	.cfi_def_cfa_offset 8
	retq
.Lfunc_end0:
	.size	"inst-000001", .Lfunc_end0-"inst-000001"
	.cfi_endproc
                                        # -- End function
	.section	".note.GNU-stack","",@progbits
	.addrsig
