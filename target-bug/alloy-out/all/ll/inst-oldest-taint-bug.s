	.text
	.file	"inst-oldest-taint-bug.ll"
	.globl	"inst-oldest-taint-bug"         # -- Begin function inst-oldest-taint-bug
	.p2align	4, 0x90
	.type	"inst-oldest-taint-bug",@function
"inst-oldest-taint-bug":                # @inst-oldest-taint-bug
	.cfi_startproc
# %bb.0:                                # %entry
	pushq	%rbp
	.cfi_def_cfa_offset 16
	.cfi_offset %rbp, -16
	movq	%rsp, %rbp
	.cfi_def_cfa_register %rbp
	andq	$-64, %rsp
	subq	$2304, %rsp                     # imm = 0x900
	movq	$0, 184(%rsp)
	movq	$0, 192(%rsp)
	movq	$0, 200(%rsp)
	movq	$0, 208(%rsp)
	movq	$0, 216(%rsp)
	movq	$0, 224(%rsp)
	movq	$0, 232(%rsp)
	movq	$0, 240(%rsp)
	movq	$0, 248(%rsp)
	movq	$0, 256(%rsp)
	movq	$0, 264(%rsp)
	movq	$0, 272(%rsp)
	movq	$0, 280(%rsp)
	movq	$0, 288(%rsp)
	movq	$0, 296(%rsp)
	movq	$0, 304(%rsp)
	movq	$0, 312(%rsp)
	movq	$0, 320(%rsp)
	movq	$0, 328(%rsp)
	movq	$0, 336(%rsp)
	movq	$0, 344(%rsp)
	movq	$0, 352(%rsp)
	movq	$0, 360(%rsp)
	movq	$0, 368(%rsp)
	movq	$0, 376(%rsp)
	movq	$0, 384(%rsp)
	movq	$0, 392(%rsp)
	movq	$0, 400(%rsp)
	movq	$0, 408(%rsp)
	movq	$0, 416(%rsp)
	movq	$0, 424(%rsp)
	movq	$0, 432(%rsp)
	movq	$0, 440(%rsp)
	movq	$0, 448(%rsp)
	movq	$0, 456(%rsp)
	movq	$0, 464(%rsp)
	movq	$0, 472(%rsp)
	movq	$0, 480(%rsp)
	movq	$0, 488(%rsp)
	movq	$0, 496(%rsp)
	movq	$0, 504(%rsp)
	movq	$0, 512(%rsp)
	movq	$0, 520(%rsp)
	movq	$0, 528(%rsp)
	movq	$0, 536(%rsp)
	movq	$0, 544(%rsp)
	movq	$0, 552(%rsp)
	movq	$0, 560(%rsp)
	movq	$0, 568(%rsp)
	movq	$0, 576(%rsp)
	movq	$0, 584(%rsp)
	movq	$0, 592(%rsp)
	movq	$0, 600(%rsp)
	movq	$0, 608(%rsp)
	movq	$0, 616(%rsp)
	movq	$0, 624(%rsp)
	movq	$0, 632(%rsp)
	movq	$0, 640(%rsp)
	movq	$0, 648(%rsp)
	movq	$0, 656(%rsp)
	movq	$0, 664(%rsp)
	movq	$0, 672(%rsp)
	movq	$0, 680(%rsp)
	movq	$0, 688(%rsp)
	movq	$0, 696(%rsp)
	movq	$0, 704(%rsp)
	movq	$0, 712(%rsp)
	movq	$0, 720(%rsp)
	movq	$0, 728(%rsp)
	movq	$0, 736(%rsp)
	movq	$0, 744(%rsp)
	movq	$0, 752(%rsp)
	movq	$0, 760(%rsp)
	movq	$0, 768(%rsp)
	movq	$0, 776(%rsp)
	movq	$0, 784(%rsp)
	movq	$0, 792(%rsp)
	movq	$0, 800(%rsp)
	movq	$0, 808(%rsp)
	movq	$0, 816(%rsp)
	movq	$0, 824(%rsp)
	movq	$0, 832(%rsp)
	movq	$0, 840(%rsp)
	movq	$0, 848(%rsp)
	movq	$0, 856(%rsp)
	movq	$0, 864(%rsp)
	movq	$0, 872(%rsp)
	movq	$0, 880(%rsp)
	movq	$0, 888(%rsp)
	movq	$0, 896(%rsp)
	movq	$0, 904(%rsp)
	movq	$0, 912(%rsp)
	movq	$0, 920(%rsp)
	movq	$0, 928(%rsp)
	movq	$0, 936(%rsp)
	movq	$0, 944(%rsp)
	movq	$0, 952(%rsp)
	movq	$0, 960(%rsp)
	movq	$0, 968(%rsp)
	movq	$0, 976(%rsp)
	movq	$0, 984(%rsp)
	movq	$0, 992(%rsp)
	movq	$0, 1000(%rsp)
	movq	$0, 1008(%rsp)
	movq	$0, 1016(%rsp)
	movq	$0, 1024(%rsp)
	movq	$0, 1032(%rsp)
	movq	$0, 1040(%rsp)
	movq	$0, 1048(%rsp)
	movq	$0, 1056(%rsp)
	movq	$0, 1064(%rsp)
	movq	$0, 1072(%rsp)
	movq	$0, 1080(%rsp)
	movq	$0, 1088(%rsp)
	movq	$0, 1096(%rsp)
	movq	$0, 1104(%rsp)
	movq	$0, 1112(%rsp)
	movq	$0, 1120(%rsp)
	movq	$0, 1128(%rsp)
	movq	$0, 1136(%rsp)
	movq	$0, 1144(%rsp)
	movq	$0, 1152(%rsp)
	movq	$0, 1160(%rsp)
	movq	$0, 1168(%rsp)
	movq	$0, 1176(%rsp)
	movq	$0, 1184(%rsp)
	movq	$0, 1192(%rsp)
	movq	$0, 1200(%rsp)
	movq	$0, 1208(%rsp)
	movq	$0, 1216(%rsp)
	movq	$0, 1224(%rsp)
	movq	$0, 1232(%rsp)
	movq	$0, 1240(%rsp)
	movq	$0, 1248(%rsp)
	movq	$0, 1256(%rsp)
	movq	$0, 1264(%rsp)
	movq	$0, 1272(%rsp)
	movq	$0, 1280(%rsp)
	movq	$0, 1288(%rsp)
	movq	$0, 1296(%rsp)
	movq	$0, 1304(%rsp)
	movq	$0, 1312(%rsp)
	movq	$0, 1320(%rsp)
	movq	$0, 1328(%rsp)
	movq	$0, 1336(%rsp)
	movq	$0, 1344(%rsp)
	movq	$0, 1352(%rsp)
	movq	$0, 1360(%rsp)
	movq	$0, 1368(%rsp)
	movq	$0, 1376(%rsp)
	movq	$0, 1384(%rsp)
	movq	$0, 1392(%rsp)
	movq	$0, 1400(%rsp)
	movq	$0, 1408(%rsp)
	movq	$0, 1416(%rsp)
	movq	$0, 1424(%rsp)
	movq	$0, 1432(%rsp)
	movq	$0, 1440(%rsp)
	movq	$0, 1448(%rsp)
	movq	$0, 1456(%rsp)
	movq	$0, 1464(%rsp)
	movq	$0, 1472(%rsp)
	movq	$0, 1480(%rsp)
	movq	$0, 1488(%rsp)
	movq	$0, 1496(%rsp)
	movq	$0, 1504(%rsp)
	movq	$0, 1512(%rsp)
	movq	$0, 1520(%rsp)
	movq	$0, 1528(%rsp)
	movq	$0, 1536(%rsp)
	movq	$0, 1544(%rsp)
	movq	$0, 1552(%rsp)
	movq	$0, 1560(%rsp)
	movq	$0, 1568(%rsp)
	movq	$0, 1576(%rsp)
	movq	$0, 1584(%rsp)
	movq	$0, 1592(%rsp)
	movq	$0, 1600(%rsp)
	movq	$0, 1608(%rsp)
	movq	$0, 1616(%rsp)
	movq	$0, 1624(%rsp)
	movq	$0, 1632(%rsp)
	movq	$0, 1640(%rsp)
	movq	$0, 1648(%rsp)
	movq	$0, 1656(%rsp)
	movq	$0, 1664(%rsp)
	movq	$0, 1672(%rsp)
	movq	$0, 1680(%rsp)
	movq	$0, 1688(%rsp)
	movq	$0, 1696(%rsp)
	movq	$0, 1704(%rsp)
	movq	$0, 1712(%rsp)
	movq	$0, 1720(%rsp)
	movq	$0, 1728(%rsp)
	movq	$0, 1736(%rsp)
	movq	$0, 1744(%rsp)
	movq	$0, 1752(%rsp)
	movq	$0, 1760(%rsp)
	movq	$0, 1768(%rsp)
	movq	$0, 1776(%rsp)
	movq	$0, 1784(%rsp)
	movq	$0, 1792(%rsp)
	movq	$0, 1800(%rsp)
	movq	$0, 1808(%rsp)
	movq	$0, 1816(%rsp)
	movq	$0, 1824(%rsp)
	movq	$0, 1832(%rsp)
	movq	$0, 1840(%rsp)
	movq	$0, 1848(%rsp)
	movq	$0, 1856(%rsp)
	movq	$0, 1864(%rsp)
	movq	$0, 1872(%rsp)
	movq	$0, 1880(%rsp)
	movq	$0, 1888(%rsp)
	movq	$0, 1896(%rsp)
	movq	$0, 1904(%rsp)
	movq	$0, 1912(%rsp)
	movq	$0, 1920(%rsp)
	movq	$0, 1928(%rsp)
	movq	$0, 1936(%rsp)
	movq	$0, 1944(%rsp)
	movq	$0, 1952(%rsp)
	movq	$0, 1960(%rsp)
	movq	$0, 1968(%rsp)
	movq	$0, 1976(%rsp)
	movq	$0, 1984(%rsp)
	movq	$0, 1992(%rsp)
	movq	$0, 2000(%rsp)
	movq	$0, 2008(%rsp)
	movq	$0, 2016(%rsp)
	movq	$0, 2024(%rsp)
	movq	$0, 2032(%rsp)
	movq	$0, 2040(%rsp)
	movq	$0, 2048(%rsp)
	movq	$0, 2056(%rsp)
	movq	$0, 2064(%rsp)
	movq	$0, 2072(%rsp)
	movq	$0, 2080(%rsp)
	movq	$0, 2088(%rsp)
	movq	$0, 2096(%rsp)
	movq	$0, 2104(%rsp)
	movq	$0, 2112(%rsp)
	movq	$0, 2120(%rsp)
	movq	$0, 2128(%rsp)
	movq	$0, 2136(%rsp)
	movq	$0, 2144(%rsp)
	movq	$0, 2152(%rsp)
	movq	$0, 2160(%rsp)
	movq	$0, 2168(%rsp)
	movq	$0, 2176(%rsp)
	movq	$0, 2184(%rsp)
	movq	$0, 2192(%rsp)
	movq	$0, 2200(%rsp)
	movq	$0, 2208(%rsp)
	movq	$0, 2216(%rsp)
	movq	$0, 2224(%rsp)
	movq	$0, 2232(%rsp)
	xorl	%eax, %eax
	#APP
	movq	%rax, %r10
	#NO_APP
	#APP
	movq	%rax, %r11
	#NO_APP
	#APP
	movq	%rax, %rax
	#NO_APP
	movq	$0, 128(%rsp)
	movq	$1, 64(%rsp)
	leaq	64(%rsp), %rax
	movq	%rax, (%rsp)
	leaq	128(%rsp), %rdx
	movq	%rsp, %rcx
	#APP
	mfence
	clflush	(%rdx)
	clflush	(%rax)
	clflush	(%rcx)
	mfence
	#NO_APP
	#APP
	.globl	__litmus_inst_oldest_taint_bug_pc0
__litmus_inst_oldest_taint_bug_pc0:
	movq	(%rdx), %rsi
	#NO_APP
	testq	%rsi, %rsi
	jne	.LBB0_3
# %bb.1:                                # %bb_1
	leaq	184(%rsp), %rdi
	#APP
	.globl	__litmus_inst_oldest_taint_bug_pc1
__litmus_inst_oldest_taint_bug_pc1:
	.globl	__litmus_inst_oldest_taint_bug_last_committed
__litmus_inst_oldest_taint_bug_last_committed:
	movq	(%rdi), %rax
	#NO_APP
	movq	%rsp, %rsi
	#APP
	movq	(%rsi), %rdx
	#NO_APP
	#APP
	.globl	__litmus_inst_oldest_taint_bug_pc2
__litmus_inst_oldest_taint_bug_pc2:
	.globl	__litmus_inst_oldest_taint_bug_first_noncommitted
__litmus_inst_oldest_taint_bug_first_noncommitted:
	movq	(%rdx), %rsi
	#NO_APP
	testq	%rsi, %rsi
	jne	.LBB0_3
# %bb.2:                                # %bb_3
	#APP
	.globl	__litmus_inst_oldest_taint_bug_pc3
__litmus_inst_oldest_taint_bug_pc3:
	movq	(%rdi), %rcx
	#NO_APP
	#APP
	.globl	__litmus_inst_oldest_taint_bug_pc4
__litmus_inst_oldest_taint_bug_pc4:
	leaq	(%rax,%rcx), %rax
	#NO_APP
	leaq	192(%rsp), %rdx
	#APP
	.globl	__litmus_inst_oldest_taint_bug_pc5
__litmus_inst_oldest_taint_bug_pc5:
	movq	(%rdx,%rax), %rax
	#NO_APP
.LBB0_3:                                # %end_block
	xorl	%eax, %eax
	movq	%rbp, %rsp
	popq	%rbp
	.cfi_def_cfa %rsp, 8
	retq
.Lfunc_end0:
	.size	"inst-oldest-taint-bug", .Lfunc_end0-"inst-oldest-taint-bug"
	.cfi_endproc
                                        # -- End function
	.section	".note.GNU-stack","",@progbits
	.addrsig
