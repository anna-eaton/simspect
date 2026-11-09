// PosthocEval.java -- herd-style evaluation of an Alloy model's predicates on GIVEN instances (no SAT search).
// graph-checker design prototype, 2026-11-08 (wiki/design/POSTHOC_GRAPH_CHECKER.md). Read-only on the model.
// Build: javac -cp ../../../STAGE1_alloy/alloy6.jar -d . PosthocEval.java
// Run:   java -cp ../../../STAGE1_alloy/alloy6.jar:. PosthocEval <model.als> <exprs.txt> <inst.xml>...
//   exprs.txt: one Alloy expression/formula per line, evaluated in the model's namespace (e.g.
//   "secure_speculation_scheme_p[no_p]", "speculative_xmit_p[no_p]"). Every fact of the model is also
//   evaluated and the violated ones are listed (well-formedness of the instance against the skeleton).
// Loads the model ONCE, then for each XML: A4SolutionReader.read (rebuild the instance) + A4Solution.eval.
import edu.mit.csail.sdg.alloy4.*;
import edu.mit.csail.sdg.ast.*;
import edu.mit.csail.sdg.parser.CompUtil;
import edu.mit.csail.sdg.translator.*;
import java.io.File;
import java.nio.file.*;
import java.util.*;

public class PosthocEval {
  public static void main(String[] a) throws Exception {
    long t0 = System.nanoTime();
    A4Reporter rep = new A4Reporter();
    edu.mit.csail.sdg.ast.Module world = CompUtil.parseEverything_fromFile(rep, null, a[0]);
    List<String> exprs = new ArrayList<>();
    for (String l : Files.readAllLines(Paths.get(a[1]))) if (!l.isBlank() && !l.startsWith("#")) exprs.add(l.trim());
    List<Expr> parsed = new ArrayList<>();
    for (String s : exprs) parsed.add(CompUtil.parseOneExpression_fromString(world, s));
    long t1 = System.nanoTime();
    System.out.printf("# model parsed in %.0f ms%n", (t1 - t0) / 1e6);
    long tEval = 0; int n = 0;
    for (int k = 2; k < a.length; k++) {
      long s0 = System.nanoTime();
      A4Solution sol = A4SolutionReader.read(world.getAllReachableSigs(), new XMLNode(new File(a[k])));
      StringBuilder out = new StringBuilder(new File(a[k]).getName());
      for (int i = 0; i < parsed.size(); i++) out.append("\n  ").append(exprs.get(i)).append(" = ").append(sol.eval(parsed.get(i)));
      List<String> bad = new ArrayList<>();
      for (Pair<String, Expr> f : world.getAllFacts()) {
        Object v = sol.eval(f.b);
        if (!Boolean.TRUE.equals(v)) bad.add(f.a);
      }
      out.append("\n  violated_facts = ").append(bad);
      tEval += System.nanoTime() - s0; n++;
      System.out.println(out);
    }
    System.out.printf("# %d instances, %.2f ms/instance (read+eval), total %.0f ms%n", n, n > 0 ? tEval / 1e6 / n : 0.0, (System.nanoTime() - t0) / 1e6);
  }
}
