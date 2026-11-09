	.text
	.file	"inst-000092.ll"
	.globl	"inst-000092"                   # -- Begin function inst-000092
	.p2align	4, 0x90
	.type	"inst-000092",@function
"inst-000092":                          # @inst-000092
	.cfi_startproc
# %bb.0:                                # %entry
	pushq	%r14
	.cfi_def_cfa_offset 16
	.cfi_offset %r14, -16
	movq	$0, -8(%rsp)
	xorl	%eax, %eax
	#APP
	movq	%rax, %r10
	#NO_APP
	#APP
	movq	%rax, %r11
	#NO_APP
	#APP
	movq	%rax, %r14
	#NO_APP
	#APP
	mfence
	#NO_APP
	#APP
	.globl	__litmus_inst_000092_pc0
__litmus_inst_000092_pc0:
	.globl	__litmus_inst_000092_last_committed
__litmus_inst_000092_last_committed:
	movq	%r10, %rax
	movq	%r11, %rcx
	orq	$1, %rcx
	cqto
	idivq	%rcx
	movq	%rax, %rax
	#NO_APP
	#APP
	.globl	__litmus_inst_000092_pc1
__litmus_inst_000092_pc1:
	.globl	__litmus_inst_000092_first_noncommitted
__litmus_inst_000092_first_noncommitted:
	movq	$1, %rdx
	#NO_APP
	testq	%rdx, %rdx
	jne	.LBB0_5
# %bb.1:                                # %bb_2
	#APP
	.globl	__litmus_inst_000092_pc2
__litmus_inst_000092_pc2:
	xorq	%rdx, %rdx
	#NO_APP
	testq	%rdx, %rdx
	je	.LBB0_2
.LBB0_5:                                # %end_block
	xorl	%eax, %eax
	popq	%r14
	.cfi_def_cfa_offset 8
	retq
.LBB0_2:                                # %bb_3
	.cfi_def_cfa_offset 16
	leaq	-8(%rsp), %rsi
	#APP
	.globl	__litmus_inst_000092_pc3
__litmus_inst_000092_pc3:
	movq	(%rsi), %rax
	#NO_APP
	#APP
	.globl	__litmus_inst_000092_pc4
__litmus_inst_000092_pc4:
	movq	%rax, %rcx
	#NO_APP
	testq	%rcx, %rcx
	je	.LBB0_5
# %bb.3:                                # %bb_5
	#APP
	.globl	__litmus_inst_000092_pc5
__litmus_inst_000092_pc5:
	xorq	%rdx, %rdx
	#NO_APP
	testq	%rdx, %rdx
	jne	.LBB0_5
# %bb.4:                                # %ftbypass_5
	#APP
	.globl	__litmus_inst_000092_ftbypass5
__litmus_inst_000092_ftbypass5:
	#NO_APP
	jmp	.LBB0_5
.Lfunc_end0:
	.size	"inst-000092", .Lfunc_end0-"inst-000092"
	.cfi_endproc
                                        # -- End function
	.section	".note.GNU-stack","",@progbits
	.addrsig
