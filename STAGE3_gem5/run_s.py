#!/usr/bin/env python3
"""
run_s.py — like run.py, but if config.script_args.cmd points at a .s file,
assemble + link it into a static ELF first, then run gem5 against the ELF.

The .s must define a global function whose label matches the filename stem
(e.g. foo.s → `.globl foo` / `foo:`). A tiny _start stub is generated that
calls that function and exits via SYS_exit.

Usage: python3 run_s.py path/to/run.json
"""
import json
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List


def load_json_with_comments(path: Path):
    text = path.read_text()
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    text = re.sub(r'//.*$', '', text, flags=re.M)
    text = re.sub(r'#.*$', '', text, flags=re.M)
    return json.loads(text)


def _die(msg: str, code: int = 2) -> None:
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(code)


def _as_list(x: Any, field: str) -> List[str]:
    if x is None:
        return []
    if isinstance(x, list) and all(isinstance(i, str) for i in x):
        return x
    _die(f'"{field}" must be a list of strings')


def _add_script_arg(cmd: List[str], key: str, val: Any) -> None:
    if isinstance(val, bool):
        if val:
            cmd.append(f"--{key}")
        return
    if val is None:
        return
    if isinstance(val, (int, float, str)):
        cmd.append(f"--{key}={val}")
        return
    if isinstance(val, list):
        for item in val:
            if not isinstance(item, (int, float, str)):
                _die(f'script arg "{key}" list items must be str/int/float')
            cmd.append(f"--{key}={item}")
        return
    _die(f'script arg "{key}" has unsupported type: {type(val).__name__}')


_ENTRY_STUB = """\
.section .text
.globl _start
_start:
    call "{func}"
    mov  $60, %rax
    xor  %rdi, %rdi
    syscall
"""


def assemble_s_to_elf(s_path: Path, workdir: Path) -> Path:
    """Assemble + static-link s_path into an ELF. Returns the ELF path."""
    if not s_path.exists():
        _die(f".s file not found: {s_path}")
    stem = s_path.stem
    workdir.mkdir(parents=True, exist_ok=True)

    start_s   = workdir / "_start.s"
    start_o   = workdir / "_start.o"
    patched_s = workdir / f"{stem}_patched.s"
    obj_o     = workdir / f"{stem}.o"
    elf       = workdir / stem

    # clang emits .addrsig / .addrsig_sym directives that GNU `as` rejects — strip them.
    text = s_path.read_text()
    text = re.sub(r'^\s*\.addrsig(_sym\b.*)?\s*$', '', text, flags=re.MULTILINE)
    patched_s.write_text(text)

    start_s.write_text(_ENTRY_STUB.format(func=stem))

    def _run(cmd: List[str]) -> None:
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            _die(f"{cmd[0]} failed (exit {e.returncode}): {' '.join(cmd)}",
                 code=e.returncode)

    _run(["as", "-o", str(start_o), str(start_s)])
    _run(["as", "-o", str(obj_o),   str(patched_s)])
    _run(["ld", "-static", "-o", str(elf), str(start_o), str(obj_o)])

    return elf


def _lookup_func_base(elf: Path, func: str) -> Optional[int]:
    """Return the load address of `func` in `elf` via nm, or None if absent."""
    try:
        out = subprocess.check_output(
            ["nm", "--defined-only", str(elf)], text=True)
    except subprocess.CalledProcessError:
        return None
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[-1] == func:
            try:
                return int(parts[0], 16)
            except ValueError:
                return None
    return None


def maybe_compile_cmd(cfg: Dict[str, Any]) -> None:
    """If config.script_args.cmd is a .s file, compile it and swap the path."""
    config = cfg.get("config", {})
    if not isinstance(config, dict):
        return
    args = config.get("script_args", {})
    if not isinstance(args, dict):
        return
    cmd_val = args.get("cmd")
    if not isinstance(cmd_val, str) or not cmd_val.endswith(".s"):
        return

    s_path = Path(cmd_val).expanduser().resolve()
    workdir = Path(tempfile.mkdtemp(prefix="run_s_"))
    elf = assemble_s_to_elf(s_path, workdir)

    print(f"Built ELF: {elf}")
    args["cmd"] = str(elf)

    # If the user supplied --branch-ann-file but no explicit --branch-ann-base,
    # resolve the litmus function's absolute load address in the freshly-linked
    # ELF and inject it, so compile_annotate's function-relative x86 offsets
    # land at the right PCs.
    if args.get("branch-ann-file") and "branch-ann-base" not in args:
        func = s_path.stem
        base = _lookup_func_base(elf, func)
        if base is not None:
            args["branch-ann-base"] = hex(base)
            print(f"Resolved --branch-ann-base={hex(base)} from {func} in {elf}")
        else:
            print(f"warning: could not resolve symbol {func!r} in {elf}; "
                  "--branch-ann-base not set")


def build_command(cfg: Dict[str, Any]) -> List[str]:
    gem5_bin = cfg.get("gem5_bin")
    if not isinstance(gem5_bin, str) or not gem5_bin:
        _die('"gem5_bin" must be a non-empty string')

    config = cfg.get("config", {})
    if not isinstance(config, dict):
        _die('"config" must be an object')

    script = config.get("script")
    if not isinstance(script, str) or not script:
        _die('"config.script" must be a non-empty string')

    cmd: List[str] = [gem5_bin]

    debug = cfg.get("debug", {})
    if debug is not None:
        if not isinstance(debug, dict):
            _die('"debug" must be an object')
        flags = _as_list(debug.get("flags"), "debug.flags")
        if flags:
            cmd.append(f"--debug-flags={','.join(flags)}")
        dbg_file = debug.get("file")
        if dbg_file is not None:
            if not isinstance(dbg_file, str) or not dbg_file:
                _die('"debug.file" must be a non-empty string if provided')
            cmd.append(f"--debug-file={dbg_file}")

    cmd.append(script)

    script_args = config.get("script_args", {})
    if not isinstance(script_args, dict):
        _die('"config.script_args" must be an object')
    for k, v in script_args.items():
        if not isinstance(k, str) or not k:
            _die("script_args keys must be non-empty strings")
        _add_script_arg(cmd, k, v)

    return cmd


def main() -> None:
    if len(sys.argv) != 2:
        _die("usage: run_s.py path/to/run.json")

    jpath = Path(sys.argv[1])
    if not jpath.exists():
        _die(f"json file not found: {jpath}")

    cfg = load_json_with_comments(jpath)

    if not isinstance(cfg, dict):
        _die("top-level JSON must be an object")

    cwd = cfg.get("cwd")
    if cwd is not None and (not isinstance(cwd, str) or not cwd):
        _die('"cwd" must be a non-empty string if provided')

    maybe_compile_cmd(cfg)

    cmd = build_command(cfg)

    print("Running:")
    print("  " + " ".join(shlex.quote(x) for x in cmd))
    print()

    try:
        subprocess.run(cmd, cwd=cwd, check=True)
    except subprocess.CalledProcessError as e:
        _die(f"command failed with exit code {e.returncode}", code=e.returncode)
    except FileNotFoundError as e:
        _die(str(e))


if __name__ == "__main__":
    main()
