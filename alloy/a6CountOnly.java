// javac -cp alloy6.jar:. a6CountOnly.java
// java  -cp alloy6.jar:. a6CountOnly <model.als> [limit]

import edu.mit.csail.sdg.alloy4.A4Reporter;
import edu.mit.csail.sdg.alloy4.Err;
import edu.mit.csail.sdg.ast.Command;
import edu.mit.csail.sdg.ast.Module;
import edu.mit.csail.sdg.parser.CompUtil;
import edu.mit.csail.sdg.translator.A4Options;
import edu.mit.csail.sdg.translator.A4Solution;
import edu.mit.csail.sdg.translator.TranslateAlloyToKodkod;
import kodkod.engine.satlab.SATFactory;

public class a6CountOnly {
  public static void main(String[] args) throws Err {
    if (args.length < 1) {
      System.err.println("Usage: java -cp alloy6.jar:. a6CountOnly <model.als> [limit]");
      System.exit(1);
    }
    String path = args[0];
    long limit  = (args.length >= 2) ? Long.parseLong(args[1]) : Long.MAX_VALUE;

    A4Reporter rep = new A4Reporter();
    Module world   = CompUtil.parseEverything_fromFile(rep, null, path);
    Command cmd    = world.getAllCommands().get(0);

    A4Options opt = new A4Options();
    opt.solver   = SATFactory.DEFAULT;
    opt.symmetry = 80;

    A4Solution sol = TranslateAlloyToKodkod.execute_command(rep, world.getAllSigs(), cmd, opt);

    long count = 0;
    while (sol.satisfiable() && count < limit) {
      count++;
      sol = sol.next();
    }
    System.out.println(count);
  }
}
