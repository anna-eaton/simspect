#!/usr/bin/env python3
"""
Alloy instance visualizer for SimSpect models.

Layout: Instructions (left) | Operands (middle) | State (right)
Instructions arranged top-to-bottom in spo order.

Usage:
    python visualize.py <instance.xml> [--out <file.png>] [--format svg|png|pdf]
    python visualize.py <folder_of_xmls> [--out <output_folder>]
"""

import xml.etree.ElementTree as ET
import argparse
import sys
import os
from pathlib import Path

# ── Colors matching execution-theme.thm ──────────────────────────────────────

INSTR_FILL = "#FFFF99"       # yellow (egg shape in theme)
INSTR_XM_FILL = "#FF6666"    # red for transmitter
OPERAND_FILL = "#CCCCCC"     # gray
OPERAND_LEAK_FILL = "#FFB6C1" # pink for leakage function operands
STATE_FILL = "#6699CC"       # blue (trapezoid in theme)
STATE_PROT_FILL = "#ADD8E6"  # light blue for hardware protection policy

EDGE_SPO = "#000000"         # black
EDGE_RF = "#0000CC"          # blue
EDGE_DDI = "#0000CC"         # blue dashed
EDGE_OPERAND = "#CC0000"     # red (inreg, inaddr, outreg, inmem, outmem)
EDGE_OPSTATE = "#666666"     # gray

# ── Kind labels ──────────────────────────────────────────────────────────────

KIND_LABELS = {
    "TLoad$0": "Load", "TStore$0": "Store",
    "TBranchn$0": "Br", "TBranchx$0": "BrX",
    "TOthern$0": "ALU", "TOtherx$0": "ALUX",
}

OPERAND_SHORT = {
    "Inreg": "ir", "Inaddr": "ia", "Inmem": "im",
    "Outreg": "or", "Outmem": "om",
}


def parse_instance(xml_path):
    """Parse an Alloy XML instance into a structured dict."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    inst = root.find("instance")

    data = {
        "instructions": [],   # list of atom labels
        "operands": [],
        "states": [],
        "kind": {},           # instr -> kind atom
        "spo": {},            # instr -> next instr
        "inreg": {},          # instr -> [operand]
        "inaddr": {},
        "outreg": {},
        "inmem": {},
        "outmem": {},
        "isresolved": set(),
        "iscommitted": set(),
        "isxm": set(),
        "opstate": {},        # operand -> state
        "rf": [],             # (src, dst)
        "ddi": [],            # (src, dst)
    }

    # Parse sigs to get atoms
    for sig in inst.findall("sig"):
        label = sig.get("label", "")
        atoms = [a.get("label") for a in sig.findall("atom")]
        if label == "this/Instruction":
            data["instructions"] = atoms
        elif label == "this/Mem_s":
            data["states"].extend(atoms)
        elif label == "this/Reg_s":
            data["states"].extend(atoms)
        elif label in ("this/Inreg", "this/Inaddr", "this/Inmem",
                        "this/Outreg", "this/Outmem"):
            data["operands"].extend(atoms)

    # Parse fields
    for field in inst.findall("field"):
        fname = field.get("label")
        tuples = [(t[0].get("label"), t[1].get("label"))
                  for t in field.findall("tuple")]

        if fname == "kind":
            for a, b in tuples:
                data["kind"][a] = b
        elif fname == "spo":
            for a, b in tuples:
                data["spo"][a] = b
        elif fname in ("inreg", "inaddr", "outreg", "inmem", "outmem"):
            for a, b in tuples:
                data[fname].setdefault(a, []).append(b)
        elif fname == "isresolved":
            for a, _ in tuples:
                data["isresolved"].add(a)
        elif fname == "iscommitted":
            for a, _ in tuples:
                data["iscommitted"].add(a)
        elif fname == "isxm":
            for a, _ in tuples:
                data["isxm"].add(a)
        elif fname == "opstate":
            for a, b in tuples:
                data["opstate"][a] = b
        elif fname == "rf":
            data["rf"] = tuples
        elif fname == "ddi":
            data["ddi"] = tuples

    # ── Compute derived sets from kind + operand fields ─────────────────
    # leakage_function = Loads.inaddr + (Branchxs+Otherxs).inreg
    leak_ops = set()
    for instr, kind_atom in data["kind"].items():
        if kind_atom == "TLoad$0":
            leak_ops.update(data["inaddr"].get(instr, []))
        elif kind_atom in ("TBranchx$0", "TOtherx$0"):
            leak_ops.update(data["inreg"].get(instr, []))
    data["leakage_function"] = leak_ops

    # hardware_protection_policy = Mem_s
    data["hw_prot_policy"] = {s for s in data["states"] if s.startswith("Mem_s")}

    return data


def topo_sort_spo(data):
    """Sort instructions by spo (program order)."""
    instrs = data["instructions"]
    spo = data["spo"]

    # find first: not a target of any spo edge
    targets = set(spo.values())
    first = [i for i in instrs if i not in targets]
    if not first:
        return instrs  # fallback

    ordered = []
    cur = first[0]
    while cur:
        ordered.append(cur)
        cur = spo.get(cur)
    # add any not in chain
    for i in instrs:
        if i not in ordered:
            ordered.append(i)
    return ordered


def instr_label(data, instr):
    """Build a label for an instruction node."""
    kind = KIND_LABELS.get(data["kind"].get(instr, ""), "?")
    # spo index
    ordered = topo_sort_spo(data)
    idx = ordered.index(instr) if instr in ordered else "?"

    flags = []
    if instr in data["iscommitted"]:
        flags.append("C")
    if instr in data["isresolved"]:
        flags.append("R")
    if instr in data["isxm"]:
        flags.append("XM")

    flag_str = " [" + ",".join(flags) + "]" if flags else ""
    return f"I{idx}: {kind}{flag_str}"


def operand_label(atom):
    """Short label for an operand atom, e.g. 'ir0' from 'Inreg$0'."""
    for prefix, short in OPERAND_SHORT.items():
        if atom.startswith(prefix):
            num = atom.split("$")[1]
            return f"{short}{num}"
    return atom


def state_label(atom):
    """Label for state atom, e.g. 'Mem0' from 'Mem_s$0'."""
    if atom.startswith("Mem_s"):
        num = atom.split("$")[1]
        return f"Mem{num}"
    elif atom.startswith("Reg_s"):
        num = atom.split("$")[1]
        return f"Reg{num}"
    return atom


def generate_dot(data):
    """Generate a Graphviz DOT string for the instance.

    Layout: Instructions top-to-bottom on the left, operands in the middle,
    state on the far right.  Uses rank=same rows to align each instruction
    with its operands horizontally.
    """
    ordered_instrs = topo_sort_spo(data)

    # Build operand ownership map
    op_owner = {}
    for fname in ("inreg", "inaddr", "outreg", "inmem", "outmem"):
        for instr, ops in data[fname].items():
            for op in ops:
                op_owner[op] = instr

    lines = []
    lines.append("digraph instance {")
    lines.append("  rankdir=TB;")
    lines.append("  newrank=true;")
    lines.append("  nodesep=0.4;")
    lines.append("  ranksep=0.5;")
    lines.append("  splines=true;")
    lines.append("")

    # ── Define all nodes ─────────────────────────────────────────────────
    for instr in ordered_instrs:
        lbl = instr_label(data, instr)
        fill = INSTR_XM_FILL if instr in data["isxm"] else INSTR_FILL
        lines.append(
            f'  "{instr}" [label="{lbl}", shape=egg, '
            f'style=filled, fillcolor="{fill}", fontsize=11];'
        )
    lines.append("")

    for op in data["operands"]:
        lbl = operand_label(op)
        fill = OPERAND_LEAK_FILL if op in data["leakage_function"] else OPERAND_FILL
        lines.append(
            f'  "{op}" [label="{lbl}", shape=box, '
            f'style=filled, fillcolor="{fill}", fontsize=10];'
        )
    lines.append("")

    for st in data["states"]:
        lbl = state_label(st)
        fill = STATE_PROT_FILL if st in data["hw_prot_policy"] else STATE_FILL
        fc = "black" if st in data["hw_prot_policy"] else "white"
        lines.append(
            f'  "{st}" [label="{lbl}", shape=trapezium, '
            f'style=filled, fillcolor="{fill}", '
            f'fontcolor={fc}, fontsize=11];'
        )
    lines.append("")

    # ── Row alignment: each instruction + its operands at same rank ─────
    # Build ddi lookup for ordering operands: ddi sources before targets
    ddi_set = set(data["ddi"])  # set of (src, dst) tuples
    for i, instr in enumerate(ordered_instrs):
        owned = [op for op, owner in op_owner.items() if owner == instr]
        # sort by ddi: if (a, b) in ddi, a comes before b
        if len(owned) > 1:
            # topo-sort owned by ddi edges within this instruction
            intra_ddi = [(s, d) for s, d in ddi_set if s in owned and d in owned]
            if intra_ddi:
                # simple: put ddi sources first, then targets
                srcs = {s for s, d in intra_ddi}
                dsts = {d for s, d in intra_ddi}
                heads = [o for o in owned if o in srcs and o not in dsts]
                tails = [o for o in owned if o in dsts and o not in srcs]
                mid = [o for o in owned if o not in heads and o not in tails]
                owned = heads + mid + tails
        members = [f'"{instr}"']
        members += [f'"{op}"' for op in owned]
        lines.append(f"  {{ rank=same; {'; '.join(members)}; }}")
        # invisible chain: instruction -> operands (left to right)
        chain = [instr] + owned
        for j in range(len(chain) - 1):
            lines.append(
                f'  "{chain[j]}" -> "{chain[j+1]}" '
                f'[style=invis, minlen=1, weight=10];'
            )
    lines.append("")

    # ── State column: stacked vertically, pushed to the right ────────────
    # Align first state with first instruction row, rest chain downward
    states = list(data["states"])
    if states:
        # put first state on same rank as first instruction
        lines.append(f"  {{ rank=same; \"{ordered_instrs[0]}\"; \"{states[0]}\"; }}")
        # invisible edge from first instruction's row to state (push right)
        lines.append(
            f'  "{ordered_instrs[0]}" -> "{states[0]}" '
            f'[style=invis, minlen=3, weight=1];'
        )
        # chain state nodes vertically
        for j in range(len(states) - 1):
            lines.append(
                f'  "{states[j]}" -> "{states[j+1]}" '
                f'[style=invis, weight=100];'
            )
    lines.append("")

    # ── Vertical ordering: invisible chain down instructions ─────────────
    for i in range(len(ordered_instrs) - 1):
        lines.append(
            f'  "{ordered_instrs[i]}" -> "{ordered_instrs[i+1]}" '
            f'[style=invis, weight=100];'
        )
    lines.append("")

    # ── Visible edges ────────────────────────────────────────────────────

    # spo edges
    for src, dst in data["spo"].items():
        lines.append(
            f'  "{src}" -> "{dst}" [color="{EDGE_SPO}", '
            f'label="spo", fontsize=10, constraint=false];'
        )
    lines.append("")

    # instruction -> operand edges
    for fname in ("inreg", "inaddr", "outreg", "inmem", "outmem"):
        for instr, ops in data[fname].items():
            for op in ops:
                lines.append(
                    f'  "{instr}" -> "{op}" [color="{EDGE_OPERAND}", '
                    f'label="{fname}", fontsize=10, arrowsize=0.7];'
                )
    lines.append("")

    # rf edges
    for src, dst in data["rf"]:
        lines.append(
            f'  "{src}" -> "{dst}" [color="{EDGE_RF}", '
            f'label="rf", fontsize=8, style=bold, constraint=false];'
        )
    lines.append("")

    # ddi edges
    for src, dst in data["ddi"]:
        lines.append(
            f'  "{src}" -> "{dst}" [color="{EDGE_DDI}", '
            f'label="ddi", fontsize=8, style=dashed, constraint=false];'
        )
    lines.append("")

    # opstate edges
    for op, st in data["opstate"].items():
        lines.append(
            f'  "{op}" -> "{st}" [color="{EDGE_OPSTATE}", '
            f'style=dotted, arrowsize=0.5, constraint=false];'
        )

    lines.append("}")
    return "\n".join(lines)


def render(dot_str, output_path, fmt="png"):
    """Render DOT string to file using graphviz."""
    try:
        import graphviz
    except ImportError:
        # fallback: write dot file and shell out
        dot_path = str(output_path) + ".dot"
        with open(dot_path, "w") as f:
            f.write(dot_str)
        os.system(f"dot -T{fmt} {dot_path} -o {output_path}")
        if os.path.exists(dot_path):
            os.remove(dot_path)
        return

    src = graphviz.Source(dot_str)
    # graphviz lib appends the format extension
    out_no_ext = str(output_path)
    if out_no_ext.endswith(f".{fmt}"):
        out_no_ext = out_no_ext[: -len(fmt) - 1]
    src.render(out_no_ext, format=fmt, cleanup=True)


def process_file(xml_path, output_path=None, fmt="png"):
    """Parse one XML and render to image."""
    data = parse_instance(xml_path)
    dot_str = generate_dot(data)

    if output_path is None:
        output_path = Path(xml_path).with_suffix(f".{fmt}")

    render(dot_str, str(output_path), fmt)
    print(f"  {Path(xml_path).name} -> {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Visualize Alloy SimSpect instances")
    parser.add_argument("input", help="XML file or folder of XML files")
    parser.add_argument("--out", "-o", help="Output file or folder")
    parser.add_argument("--format", "-f", default="png", choices=["png", "svg", "pdf"],
                        help="Output format (default: png)")
    parser.add_argument("--dot", action="store_true",
                        help="Output raw DOT instead of rendering")
    args = parser.parse_args()

    inp = Path(args.input)

    if inp.is_file():
        if args.dot:
            data = parse_instance(str(inp))
            print(generate_dot(data))
        else:
            out = args.out or str(inp.with_suffix(f".{args.format}"))
            process_file(str(inp), out, args.format)

    elif inp.is_dir():
        xmls = sorted(inp.glob("*.xml"))
        if not xmls:
            print(f"No XML files in {inp}")
            sys.exit(1)

        out_dir = Path(args.out) if args.out else inp / "viz"
        out_dir.mkdir(parents=True, exist_ok=True)

        print(f"Rendering {len(xmls)} instances to {out_dir}/")
        for xml in xmls:
            out_path = out_dir / xml.with_suffix(f".{args.format}").name
            process_file(str(xml), str(out_path), args.format)
        print("Done.")
    else:
        print(f"Not found: {inp}")
        sys.exit(1)


if __name__ == "__main__":
    main()
