open util/ordering[Elem] as OOrd

sig Elem {
    next: lone Elem
}

run {} for 5 but exactly 3 Elem
