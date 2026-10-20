	.text
	.file	"inst-cd-001.ll"
	.globl	"inst-cd-001"                   # -- Begin function inst-cd-001
	.p2align	4, 0x90
	.type	"inst-cd-001",@function
"inst-cd-001":                          # @inst-cd-001
	.cfi_startproc
# %bb.0:                                # %entry
	pushq	%r12
	.cfi_def_cfa_offset 16
	.cfi_offset %r12, -16
	movq	$0, -8(%rsp)
	movq	$4660, -16(%rsp)
	xorl	%eax, %eax
	#APP
	movq	%rax, %r10
	#NO_APP
	#APP
	movq	%rax, %r12
	#NO_APP
	#APP
	movq	%rax, %r8
	#NO_APP
	#APP
	movq	%rax, %r9
	#NO_APP
	#APP
	movq	%rax, %rdi
	#NO_APP
	#APP
	mfence
	#NO_APP
	#APP
	.globl	__litmus_inst_cd_001_pc0
__litmus_inst_cd_001_pc0:
	.globl	__litmus_inst_cd_001_first_noncommitted
__litmus_inst_cd_001_first_noncommitted:
	movq	$1, %rdx
	#NO_APP
	testq	%rdx, %rdx
	jne	.LBB0_6
# %bb.1:                                # %bb_1
	leaq	-8(%rsp), %rsi
	#APP
	.globl	__litmus_inst_cd_001_pc1
__litmus_inst_cd_001_pc1:
	movq	(%rsi), %rax
	#NO_APP
	#APP
	.globl	__litmus_inst_cd_001_pc2
__litmus_inst_cd_001_pc2:
	xorq	%rdx, %rdx
	#NO_APP
	testq	%rdx, %rdx
	jne	.LBB0_6
# %bb.2:                                # %bb_3
	#APP
	.globl	__litmus_inst_cd_001_pc3
__litmus_inst_cd_001_pc3:
	xorq	%rdx, %rdx
	#NO_APP
	testq	%rdx, %rdx
	jne	.LBB0_6
# %bb.3:                                # %bb_4
	#APP
	.globl	__litmus_inst_cd_001_pc4
__litmus_inst_cd_001_pc4:
	xorq	%rdx, %rdx
	#NO_APP
	testq	%rdx, %rdx
	jne	.LBB0_6
# %bb.4:                                # %bb_5
	#APP
	.globl	__litmus_inst_cd_001_pc5
__litmus_inst_cd_001_pc5:
	movq	%rax, %rcx
	#NO_APP
	testq	%rcx, %rcx
	je	.LBB0_6
# %bb.5:                                # %bb_6
	#APP
	.globl	__litmus_inst_cd_001_pc6
__litmus_inst_cd_001_pc6:
	leaq	-16(%rsp), %r11
	movq	(%r11), %r11
	#NO_APP
.LBB0_6:                                # %end_block
	xorl	%eax, %eax
	popq	%r12
	.cfi_def_cfa_offset 8
	retq
.Lfunc_end0:
	.size	"inst-cd-001", .Lfunc_end0-"inst-cd-001"
	.cfi_endproc
                                        # -- End function
	.section	".note.GNU-stack","",@progbits
	.addrsig
