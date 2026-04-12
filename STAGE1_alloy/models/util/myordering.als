module util/myordering[elem]

/*
 * Like util/ordering but without the [exactly elem] constraint,
 * so it works when elem has zero atoms (ordering is vacuously skipped).
 */

private one sig Ord {
   First: set elem,
   Next: elem -> elem
} {
   some elem => pred/totalOrder[elem,First,Next]
}

fun first : set elem        { Ord.First }
fun last  : set elem        { elem - (next.elem) }
fun prev  : elem->elem      { ~(Ord.Next) }
fun next  : elem->elem      { Ord.Next }
fun prevs [e: elem]: set elem { e.^(~(Ord.Next)) }
fun nexts [e: elem]: set elem { e.^(Ord.Next) }
pred lt  [e1, e2: elem] { e1 in prevs[e2] }
pred gt  [e1, e2: elem] { e1 in nexts[e2] }
pred lte [e1, e2: elem] { e1=e2 || lt[e1,e2] }
pred gte [e1, e2: elem] { e1=e2 || gt[e1,e2] }
