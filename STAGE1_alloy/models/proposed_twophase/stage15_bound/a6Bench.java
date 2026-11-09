// a6Bench - timing/memory benchmark for one Alloy run (stage15-bound session, 2026-11-08).
// Same solver settings as the production driver STAGE1_alloy/a6CountModels.java
// (SATFactory.DEFAULT = SAT4J, symmetry = 80), plus measurements:
//   parse time, Kodkod translation time (translate() -> solve() reporter callbacks),
//   CNF size (primary vars, total vars, clauses), time to the first instance,
//   instances enumerated in a fixed wall-clock window, peak JVM heap.
// Optionally dumps the first <dump> instances as inst-%06d.txt (sol.toString(), same
// format as a6CountModels) for censuses.
//
// Build: javac -cp <path>/alloy6.jar:. a6Bench.java
// Run:   java -Xmx16g -cp <path>/alloy6.jar:. a6Bench <model.als> <enum_seconds> <limit> [dump_dir] [dump_n]
// Output: one "BENCH key=value ..." line per milestone, final "RESULT ..." line.

import edu.mit.csail.sdg.alloy4.A4Reporter;
import edu.mit.csail.sdg.alloy4.Err;
import edu.mit.csail.sdg.ast.Command;
import edu.mit.csail.sdg.ast.Module;
import edu.mit.csail.sdg.parser.CompUtil;
import edu.mit.csail.sdg.translator.A4Options;
import edu.mit.csail.sdg.translator.A4Solution;
import edu.mit.csail.sdg.translator.TranslateAlloyToKodkod;
import kodkod.engine.satlab.SATFactory;

import java.lang.management.ManagementFactory;
import java.lang.management.MemoryPoolMXBean;
import java.lang.management.MemoryType;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

public class a6Bench {
  static long t0;
  static double secs() { return (System.nanoTime() - t0) / 1e9; }

  static long peakHeapMB() {
    long sum = 0;
    for (MemoryPoolMXBean p : ManagementFactory.getMemoryPoolMXBeans())
      if (p.getType() == MemoryType.HEAP && p.getPeakUsage() != null) sum += p.getPeakUsage().getUsed();
    return sum / (1024 * 1024);
  }

  public static void main(String[] args) throws Exception {
    if (args.length < 3) {
      System.err.println("Usage: a6Bench <model.als> <enum_seconds> <limit> [dump_dir] [dump_n]");
      System.exit(1);
    }
    String path = args[0];
    double enumSecs = Double.parseDouble(args[1]);
    long limit = Long.parseLong(args[2]);
    Path dump = args.length >= 4 ? Paths.get(args[3]) : null;
    long dumpN = args.length >= 5 ? Long.parseLong(args[4]) : 0;
    if (dump != null) Files.createDirectories(dump);

    t0 = System.nanoTime();
    final double[] tTrans = {-1}, tSolve = {-1};
    final int[] cnf = {0, 0, 0, 0};
    A4Reporter rep = new A4Reporter() {
      @Override public void translate(String solver, int bitwidth, int maxseq, int mintrace, int maxtrace, int skolem, int sym, String strat) {
        tTrans[0] = secs();
        System.out.printf("BENCH event=translate_start t=%.2f solver=%s bitwidth=%d%n", tTrans[0], solver, bitwidth);
      }
      @Override public void solve(int plength, int primaryVars, int totalVars, int clauses) {
        tSolve[0] = secs();
        cnf[0] = plength; cnf[1] = primaryVars; cnf[2] = totalVars; cnf[3] = clauses;
        System.out.printf("BENCH event=translated t=%.2f primary_vars=%d total_vars=%d clauses=%d heap_peak_mb=%d%n",
            tSolve[0], primaryVars, totalVars, clauses, peakHeapMB());
      }
    };
    Module world = CompUtil.parseEverything_fromFile(rep, null, path);
    double tParse = secs();
    Command cmd = world.getAllCommands().get(0);
    System.out.printf("BENCH event=parsed t=%.2f cmd=%s%n", tParse, cmd.toString().replace(' ', '_'));

    A4Options opt = new A4Options();
    opt.solver = SATFactory.DEFAULT;
    opt.symmetry = 80;

    A4Solution sol = TranslateAlloyToKodkod.execute_command(rep, world.getAllSigs(), cmd, opt);
    double tFirst = secs();
    boolean sat = sol.satisfiable();
    System.out.printf("BENCH event=first_result t=%.2f sat=%b heap_peak_mb=%d%n", tFirst, sat, peakHeapMB());

    long count = 0;
    double tEnumStart = secs();
    boolean exhausted = false;
    while (sol.satisfiable() && count < limit) {
      count++;
      if (dump != null && count <= dumpN)
        Files.writeString(dump.resolve(String.format("inst-%06d.txt", count)), sol.toString());
      if (secs() - tEnumStart > enumSecs) break;
      sol = sol.next();
      if (!sol.satisfiable()) exhausted = true;
    }
    double tEnd = secs();
    double window = tEnd - tEnumStart;
    String verdict = !sat ? "UNSAT" : exhausted ? "EXHAUSTED" : count >= limit ? "CAPPED" : "WINDOW";
    System.out.printf("RESULT sat=%b verdict=%s parse_s=%.2f translate_s=%.2f first_s=%.2f primary_vars=%d total_vars=%d clauses=%d " +
        "instances=%d enum_window_s=%.1f inst_per_min=%.1f heap_peak_mb=%d%n",
        sat, verdict, tParse, (tSolve[0] >= 0 && tTrans[0] >= 0) ? tSolve[0] - tTrans[0] : -1, tFirst,
        cnf[1], cnf[2], cnf[3], count, window, window > 0 ? 60.0 * count / window : 0.0, peakHeapMB());
  }
}
