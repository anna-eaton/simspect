open util/ordering[Elem] as OOrd

abstract sig State {}
sig Mem_s extends State {}
sig Reg_s extends State {}

abstract sig Op {
    opstate: one State,
    rf: set Op,
}
sig InOp extends Op {}
sig OutOp extends Op {}

sig Elem {
    tag: one State,
    ins: set InOp,
    outs: set OutOp,
    next: lone Elem,
}

run {} for 5 but exactly 3 Elem
