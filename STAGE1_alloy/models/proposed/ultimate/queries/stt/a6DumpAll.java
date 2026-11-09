// a6DumpAll (STT agent 2026-11-09): for EVERY command of a file, enumerate up to <limit> instances and
// write each as <out_dir>/<label>/inst-NNNNNN.xml (+ .txt); prints "CMD <label> DUMPED <n> EXHAUSTED|CAPPED <ms>".
// Used to feed Stage-2 smoke tests (STAGE2_compilation/batch_generate.py) with forced shapes.
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

public class a6DumpAll {
  public static void main(String[] args) throws Exception {
    Path out = Paths.get(args[1]);
    long limit = args.length >= 3 ? Long.parseLong(args[2]) : 50;
    A4Reporter rep = new A4Reporter();
    Module world = CompUtil.parseEverything_fromFile(rep, null, args[0]);
    A4Options opt = new A4Options();
    opt.solver = SATFactory.DEFAULT;
    opt.symmetry = 80;
    for (Command cmd : world.getAllCommands()) {
      long t0 = System.currentTimeMillis();
      Path d = out.resolve(cmd.label);
      Files.createDirectories(d);
      A4Solution sol = TranslateAlloyToKodkod.execute_command(rep, world.getAllSigs(), cmd, opt);
      long n = 0;
      while (sol.satisfiable() && n < limit) {
        n++;
        sol.writeXML(d.resolve(String.format("inst-%06d.xml", n)).toString(), Collections.<Func>emptyList());
        Files.writeString(d.resolve(String.format("inst-%06d.txt", n)), sol.toString());
        sol = sol.next();
      }
      System.out.println("CMD " + cmd.label + " DUMPED " + n + " " + (n < limit ? "EXHAUSTED" : "CAPPED") + " " + (System.currentTimeMillis() - t0));
      System.out.flush();
    }
    System.out.println("DONE");
  }
}
