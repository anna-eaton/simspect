// a6RunAll: run EVERY command of one .als file in one JVM (ultimate-model agents, 2026-11-09).
// Build: javac -cp ../../../../alloy6.jar -d . a6RunAll.java
// Run:   java -cp <alloy6.jar>:<this dir> a6RunAll <model.als> <out_dir> [count_limit]
// For each command prints one line:  CMD <label> SAT|UNSAT <ms>   (flushed, so a gtimeout kill keeps earlier lines)
// A command whose label starts with "count_" is enumerated up to count_limit (default 1000):
//   CMD <label> COUNT <n> EXHAUSTED|CAPPED <ms>
// For a SAT non-count command the first instance is written to <out_dir>/<label>.txt and .xml (the witness).
import edu.mit.csail.sdg.alloy4.A4Reporter;
import edu.mit.csail.sdg.ast.Command;
import edu.mit.csail.sdg.ast.Func;
import edu.mit.csail.sdg.ast.Module;
import edu.mit.csail.sdg.parser.CompUtil;
import edu.mit.csail.sdg.translator.A4Options;
import edu.mit.csail.sdg.translator.A4Solution;
import edu.mit.csail.sdg.translator.TranslateAlloyToKodkod;
import kodkod.engine.satlab.SATFactory;
import java.nio.file.*;
import java.util.Collections;

public class a6RunAll {
  public static void main(String[] args) throws Exception {
    String path = args[0];
    Path out = Paths.get(args[1]);
    long limit = args.length >= 3 ? Long.parseLong(args[2]) : 1000;
    Files.createDirectories(out);
    A4Reporter rep = new A4Reporter();
    Module world = CompUtil.parseEverything_fromFile(rep, null, path);
    A4Options opt = new A4Options();
    opt.solver = SATFactory.DEFAULT;
    opt.symmetry = 80;
    for (Command cmd : world.getAllCommands()) {
      String label = cmd.label;
      long t0 = System.currentTimeMillis();
      A4Solution sol = TranslateAlloyToKodkod.execute_command(rep, world.getAllSigs(), cmd, opt);
      if (label.startsWith("count_")) {
        long n = 0;
        while (sol.satisfiable() && n < limit) { n++; sol = sol.next(); }
        String st = (n < limit) ? "EXHAUSTED" : "CAPPED";
        System.out.println("CMD " + label + " COUNT " + n + " " + st + " " + (System.currentTimeMillis() - t0));
      } else {
        boolean sat = sol.satisfiable();
        if (sat) {
          sol.writeXML(out.resolve(label + ".xml").toString(), Collections.<Func>emptyList());
          Files.writeString(out.resolve(label + ".txt"), sol.toString());
        }
        System.out.println("CMD " + label + " " + (sat ? "SAT" : "UNSAT") + " " + (System.currentTimeMillis() - t0));
      }
      System.out.flush();
    }
    System.out.println("DONE");
  }
}
