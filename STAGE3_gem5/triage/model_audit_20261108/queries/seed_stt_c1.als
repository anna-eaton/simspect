// AUTO-GENERATED stage-2 seed from a stage-1 STT_6_core instance.
pred seed_core {
  some disj i0, i1, i2: Instruction, disj o0, o1, o2: Operand | {
    i0 in Branchns
    i1 in Loads
    i2 in Loads
    i1 in i0.^spo
    i2 in i1.^spo
    i0 not in resolved
    i1 in resolved
    i2 in resolved
    i0 not in committed
    i1 not in committed
    i2 not in committed
    i2 in xm
    o0 in i2.inaddr
    o1 in i1.inmem
    o2 in i1.outreg
    o0.opstate in Reg_s
    o1.opstate in Mem_s
    o2.opstate in Reg_s
    o0 in o2.rf
    o2 in o1.ddi
  }
}
