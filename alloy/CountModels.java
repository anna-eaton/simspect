import edu.mit.csail.sdg.alloy4.A4Reporter;
import edu.mit.csail.sdg.alloy4.Err;
import edu.mit.csail.sdg.alloy4compiler.ast.Command;
import edu.mit.csail.sdg.alloy4compiler.ast.Module;
import edu.mit.csail.sdg.alloy4compiler.parser.CompUtil;
import edu.mit.csail.sdg.alloy4compiler.translator.A4Options;
import edu.mit.csail.sdg.alloy4compiler.translator.A4Solution;
import edu.mit.csail.sdg.alloy4compiler.translator.TranslateAlloyToKodkod;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
// java -cp alloy4.2.jar:. CountModels
// javac -cp alloy4.2.jar:. CountModels.java

// USAGE
// java -cp alloy4.2.jar:. CountModels <model.als> <out_dir> [limit]



public class CountModels {
  public static void main(String[] args) throws Err, IOException {

    if (args.length < 2) {
      System.err.println("Usage: java -cp alloy4.2.jar:. CountModels <model.als> <out_dir> [limit]");
      System.exit(1);
    }

    String path = args[0];           // model file
    Path outDir = Paths.get(args[1]); // output directory
    long limit = (args.length >= 3) ? Long.parseLong(args[2]) : 1000;

    A4Reporter rep = new A4Reporter();
    Module world = CompUtil.parseEverything_fromFile(rep, null, path);

    Command cmd = world.getAllCommands().get(0);

    A4Options opt = new A4Options();
    opt.solver = A4Options.SatSolver.SAT4J;
    opt.symmetry = 20;

    A4Solution sol =
        TranslateAlloyToKodkod.execute_command(rep, world.getAllSigs(), cmd, opt);

    Files.createDirectories(outDir);

    long count = 0;

    while (sol.satisfiable() && count < limit) {
      count++;

      Path xmlPath = outDir.resolve(String.format("inst-%06d.xml", count));
      sol.writeXML(xmlPath.toString());

      Path txtPath = outDir.resolve(String.format("inst-%06d.txt", count));
      Files.writeString(txtPath, sol.toString());

      sol = sol.next();
    }

    System.out.println("Total models: " + count);
  }
}