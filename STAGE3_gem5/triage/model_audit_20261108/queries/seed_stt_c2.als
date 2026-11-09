// AUTO-GENERATED stage-2 seed from a stage-1 STT_6_core instance.
pred seed_core {
  some disj i0, i1, i2: Instruction, disj o0, o1, o2: Operand | {
    i0 in Branchns
    i1 in Branchxs
    i2 in Loads
    i2 in i0.^spo
    i1 in i2.^spo
    i0 not in resolved
    i1 in resolved
    i2 in resolved
    i0 not in committed
    i1 not in committed
    i2 not in committed
    i1 in xm
    o1 in i1.inreg
    o0 in i2.inmem
    o2 in i2.outreg
    o0.opstate in Mem_s
    o1.opstate in Reg_s
    o2.opstate in Reg_s
    o1 in o2.rf
    o2 in o0.ddi
  }
}
