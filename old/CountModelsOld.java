import edu.mit.csail.sdg.alloy4.A4Reporter;
import edu.mit.csail.sdg.alloy4.Err;
import edu.mit.csail.sdg.alloy4compiler.ast.Command;
import edu.mit.csail.sdg.alloy4compiler.ast.Module;
import edu.mit.csail.sdg.alloy4compiler.parser.CompUtil;
import edu.mit.csail.sdg.alloy4compiler.translator.A4Options;
import edu.mit.csail.sdg.alloy4compiler.translator.A4Solution;
import edu.mit.csail.sdg.alloy4compiler.translator.TranslateAlloyToKodkod;

// java -cp alloy4.2.jar:. CountModels
// javac -cp alloy4.2.jar:. CountModels.java

public class CountModels {
  public static void main(String[] args) throws Err {
    // String path = "model_overloaded.als";
    // String path = "STT_edge.als";
    // String path = "bigmodel.als";
    // String path = "/Users/annaeaton/Downloads/Relaxed-new.als";
        String path = "/Users/annaeaton/Downloads/relaxed-double.als";
    A4Reporter rep = new A4Reporter();
    Module world = CompUtil.parseEverything_fromFile(rep, null, path);

    // pick the command by name or use the first ‘run’
    Command cmd = world.getAllCommands().get(0);

    A4Options opt = new A4Options();
    opt.solver = A4Options.SatSolver.SAT4J;      // or MiniSatProver/Glucose
    opt.symmetry = 20;                           // 0 disables symmetry breaking

    A4Solution sol = TranslateAlloyToKodkod.execute_command(rep, world.getAllSigs(), cmd, opt);

    long count = 0;
    while (sol.satisfiable()) {
      count++;

      // Optional: export each instance
      // sol.writeXML("out/inst-" + count + ".xml");

      sol = sol.next(); // advance to next distinct solution
    }
    System.out.println("Total models: " + count);
  }
}
