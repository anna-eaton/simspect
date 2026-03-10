// javac -cp alloy6.jar:. a6CountModels.java
// java  -cp alloy6.jar:. a6CountModels <model.als> <out_dir> [limit]

import edu.mit.csail.sdg.alloy4.A4Reporter;
import edu.mit.csail.sdg.alloy4.Err;
import edu.mit.csail.sdg.ast.Command;
import edu.mit.csail.sdg.ast.Func;
import edu.mit.csail.sdg.ast.Module;
import edu.mit.csail.sdg.parser.CompUtil;
import edu.mit.csail.sdg.translator.A4Options;
import edu.mit.csail.sdg.translator.A4Solution;
import edu.mit.csail.sdg.translator.TranslateAlloyToKodkod;
import kodkod.engine.satlab.SATFactory;

import java.io.IOException;
import java.util.Collections;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

public class a6CountModels {
  public static void main(String[] args) throws Err, IOException {

    if (args.length < 2) {
      System.err.println("Usage: java -cp alloy6.jar:. a6CountModels <model.als> <out_dir> [limit]");
      System.exit(1);
    }

    String path  = args[0];
    Path outDir  = Paths.get(args[1]);
    long limit   = (args.length >= 3) ? Long.parseLong(args[2]) : 1000;

    A4Reporter rep = new A4Reporter();
    Module world   = CompUtil.parseEverything_fromFile(rep, null, path);

    Command cmd = world.getAllCommands().get(0);

    A4Options opt = new A4Options();
    opt.solver    = SATFactory.DEFAULT;
    // opt.symmetry  = 20;
    opt.symmetry  = 80; // Disable symmetry breaking to get all models.

    A4Solution sol =
        TranslateAlloyToKodkod.execute_command(rep, world.getAllSigs(), cmd, opt);

    Files.createDirectories(outDir);

    long count = 0;
    while (sol.satisfiable() && count < limit) {
      count++;
      Path xmlPath = outDir.resolve(String.format("inst-%06d.xml", count));
      sol.writeXML(xmlPath.toString(), Collections.<Func>emptyList());
      Path txtPath = outDir.resolve(String.format("inst-%06d.txt", count));
      Files.writeString(txtPath, sol.toString());
      sol = sol.next();
    }

    System.out.println("Total models: " + count);
  }
}
