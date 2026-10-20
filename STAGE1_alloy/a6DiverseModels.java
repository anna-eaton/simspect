// javac -cp alloy6.jar:. a6DiverseModels.java
// java  -cp alloy6.jar:. a6DiverseModels <model.als> <out_dir> [limit]
//
// DIVERSITY-DRIVEN enumeration (see mdsToRead/ENUMERATION_OVERSPECIFICATION.md).
//
// a6CountModels uses Kodkod sol.next(), which blocks only the EXACT previous model — so the
// solver flips one padding/register bit and returns a structurally-identical "new" instance.
// Measured effect: 100k STT_6 tests collapse to ~2 leak shapes (47 leak-cores).
//
// This driver instead blocks the whole STRUCTURAL SKELETON after each accepted solution:
//   - kind by position (idx.IXk).kind
//   - speculation status by position (resolved? / is-xmit?)
//   - the rf dataflow edges, by (producer position, producer slot, consumer position, consumer slot)
// It appends a top-level `fact { not (<this skeleton>) }` to the model source and re-solves, so
// every emitted instance is a NEW structural class. One representative per skeleton => real
// leak-mechanism diversity instead of padding permutations.
//
// All references are by named one-sigs (IX0..IX5, TLoad.., rBool/tBool), so the blocking facts
// are atom-identity-free and sound under the model's idx symmetry-breaking.

import edu.mit.csail.sdg.alloy4.A4Reporter;
import edu.mit.csail.sdg.alloy4.Err;
import edu.mit.csail.sdg.ast.Command;
import edu.mit.csail.sdg.ast.Expr;
import edu.mit.csail.sdg.ast.Func;
import edu.mit.csail.sdg.ast.Module;
import edu.mit.csail.sdg.parser.CompUtil;
import edu.mit.csail.sdg.translator.A4Options;
import edu.mit.csail.sdg.translator.A4Solution;
import edu.mit.csail.sdg.translator.A4Tuple;
import edu.mit.csail.sdg.translator.A4TupleSet;
import edu.mit.csail.sdg.translator.TranslateAlloyToKodkod;
import kodkod.engine.satlab.SATFactory;

import java.io.IOException;
import java.util.*;
import java.nio.file.*;

public class a6DiverseModels {

  static final String[] POS = {"IX0","IX1","IX2","IX3","IX4","IX5"};
  static final String[] INSLOTS  = {"inreg","inaddr","inmem"};
  static final String[] OUTSLOTS = {"outreg","outmem"};

  // eval a named relation -> list of String[] tuples
  static List<String[]> ev(Module w, A4Solution s, String expr) throws Err {
    List<String[]> out = new ArrayList<>();
    Object o = s.eval(CompUtil.parseOneExpression_fromString(w, expr));
    if (o instanceof A4TupleSet) {
      for (A4Tuple t : (A4TupleSet) o) {
        String[] r = new String[t.arity()];
        for (int i = 0; i < t.arity(); i++) r[i] = t.atom(i);
        out.add(r);
      }
    }
    return out;
  }

  // strip the "$0" suffix Alloy puts on atoms of one-sigs
  static String base(String atom) { int i = atom.indexOf('$'); return i < 0 ? atom : atom.substring(0, i); }

  // Build a blocking fact for the current solution's LEAK-CORE SHAPE, position-INDEPENDENT.
  // The leak-core = the instructions backward-reachable from the transmitter via rf (the dataflow
  // that actually produces the leak); padding is ignored. We forbid that shape appearing ANYWHERE
  // (an existential over Instruction), so each emitted model has a structurally-new leak mechanism
  // rather than the same core wearing a new padding arrangement.
  static String skeletonBlock(Module w, A4Solution s, int id) throws Err {
    Map<String,String> kind = new HashMap<>();
    for (String[] t : ev(w, s, "kind")) kind.put(t[0], base(t[1]));
    String xmInst = null;
    for (String[] t : ev(w, s, "isxm")) xmInst = t[0];
    // operand -> (inst, slot)
    Map<String,String> opInst = new HashMap<>(), opSlot = new HashMap<>();
    for (String slot : new String[]{"inreg","inaddr","inmem","outreg","outmem"})
      for (String[] t : ev(w, s, slot)) { opInst.put(t[1], t[0]); opSlot.put(t[1], slot); }
    // rf edges as (prodInst, prodSlot, consInst, consSlot)
    List<String[]> rfEdges = new ArrayList<>();
    for (String[] e : ev(w, s, "rf")) {
      String pi = opInst.get(e[0]), ci = opInst.get(e[1]);
      if (pi != null && ci != null) rfEdges.add(new String[]{pi, opSlot.get(e[0]), ci, opSlot.get(e[1])});
    }
    // backward-reachable instruction set from the transmitter (the leak-core)
    Set<String> core = new LinkedHashSet<>();
    Deque<String> q = new ArrayDeque<>();
    if (xmInst != null) { core.add(xmInst); q.add(xmInst); }
    while (!q.isEmpty()) {
      String c = q.poll();
      for (String[] e : rfEdges) if (e[2].equals(c) && core.add(e[0])) q.add(e[0]);
    }
    // assign a quantifier variable per core instruction
    List<String> insts = new ArrayList<>(core);
    Map<String,String> var = new HashMap<>();
    for (int i = 0; i < insts.size(); i++) var.put(insts.get(i), "i" + i);

    List<String> terms = new ArrayList<>();
    for (String c : insts) terms.add(var.get(c) + ".kind = " + kind.get(c));
    if (xmInst != null) terms.add("some " + var.get(xmInst) + ".isxm");
    for (String[] e : rfEdges)
      if (core.contains(e[0]) && core.contains(e[2]))
        terms.add("some (" + var.get(e[0]) + "." + e[1] + " <: rf :> " + var.get(e[2]) + "." + e[3] + ")");

    StringBuilder conj = new StringBuilder();
    for (int i = 0; i < terms.size(); i++) conj.append(i == 0 ? "" : "\n      and ").append(terms.get(i));
    String decl = String.join(", ", new ArrayList<>(var.values()));
    String quant = (var.size() > 1 ? "some disj " : "some ") + decl + ": Instruction";
    return "fact block_" + id + " {\n  not (\n    " + quant + " |\n      " + conj + "\n  )\n}\n";
  }

  public static void main(String[] args) throws Err, IOException {
    if (args.length < 2) {
      System.err.println("Usage: java -cp alloy6.jar:. a6DiverseModels <model.als> <out_dir> [limit]");
      System.exit(1);
    }
    String path = args[0];
    Path outDir = Paths.get(args[1]);
    long limit  = (args.length >= 3) ? Long.parseLong(args[2]) : 1000;
    Files.createDirectories(outDir);

    String baseText = Files.readString(Paths.get(path));
    A4Reporter rep = new A4Reporter();
    A4Options opt = new A4Options();
    opt.solver   = SATFactory.DEFAULT;
    opt.symmetry = 80;

    StringBuilder blocks = new StringBuilder();
    long count = 0;
    Path work = outDir.resolve("_work.als");

    while (count < limit) {
      Files.writeString(work, baseText + "\n// ==== diversity blocking facts ====\n" + blocks);
      Module world = CompUtil.parseEverything_fromFile(rep, null, work.toString());
      Command cmd  = world.getAllCommands().get(0);
      A4Solution sol = TranslateAlloyToKodkod.execute_command(rep, world.getAllSigs(), cmd, opt);
      if (!sol.satisfiable()) { System.out.println("UNSAT after " + count + " distinct skeletons"); break; }
      count++;
      sol.writeXML(outDir.resolve(String.format("inst-%06d.xml", count)).toString(),
                   Collections.<Func>emptyList());
      blocks.append(skeletonBlock(world, sol, (int) count));
      if (count % 25 == 0) System.out.println("  ... " + count + " distinct skeletons");
    }
    Files.deleteIfExists(work);
    System.out.println("Total distinct-skeleton models: " + count);
  }
}
