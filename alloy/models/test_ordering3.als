open util/ordering[Elem] as OOrd

abstract sig Tag {}
one sig TA extends Tag {}
one sig TB extends Tag {}

sig Elem {
    tag: one Tag,
    next: lone Elem
}

run {} for 5 but exactly 3 Elem
