#!/usr/bin/env python3
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List
import re


def load_json_with_comments(path: Path):
    text = path.read_text()

    # Remove /* block comments */
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)

    # Remove // comments
    text = re.sub(r'//.*$', '', text, flags=re.M)

    # Remove # comments
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
    # key is already the long option name without leading "--"
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
        # Allow repeated flags like --foo=a --foo=b
        for item in val:
            if not isinstance(item, (int, float, str)):
                _die(f'script arg "{key}" list items must be str/int/float')
            cmd.append(f"--{key}={item}")
        return
    _die(f'script arg "{key}" has unsupported type: {type(val).__name__}')


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

    # Config script
    cmd.append(script)

    # Script args
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
        _die("usage: run_gem5.py path/to/run_gem5.json")

    jpath = Path(sys.argv[1])
    if not jpath.exists():
        _die(f"json file not found: {jpath}")

    cfg = load_json_with_comments(jpath)

    if not isinstance(cfg, dict):
        _die("top-level JSON must be an object")

    cwd = cfg.get("cwd")
    if cwd is not None and (not isinstance(cwd, str) or not cwd):
        _die('"cwd" must be a non-empty string if provided')

    cmd = build_command(cfg)

    # Print exact command (copy/pasteable)
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
