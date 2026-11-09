#!/usr/bin/env python3
"""launch_campaigns.py — start one testrun.py per campaign in campaigns.json, each in its own window
of tmux session fv2_gem5 (skips a campaign whose window already exists). Run from the code root.
Per-campaign log: ../logs/gem5_<results_name>.log; testrun.py itself writes results/<name>__<ts>/.
Launch events append to ../logs/fv2_gem5_launcher.log.
"""
import datetime as dt
import json
import subprocess
from pathlib import Path

ROOT = Path.cwd()
camps = json.loads((ROOT / "runconfigs/twostage_fv2_20261109/campaigns.json").read_text())
log = open(ROOT.parent / "logs/fv2_gem5_launcher.log", "a")
if subprocess.run(["tmux", "has-session", "-t", "fv2_gem5"], capture_output=True).returncode:
    subprocess.run(["tmux", "new-session", "-d", "-s", "fv2_gem5", "-n", "ctl"], check=True)
have = subprocess.run(["tmux", "list-windows", "-t", "fv2_gem5", "-F", "#W"], capture_output=True, text=True).stdout.split()
for c in camps:
    name = c["results_name"]
    if name in have:
        continue
    cmd = (f"cd {ROOT} && python3 -u testrun.py --config {c['config']} --model {c['model']} "
           f"--interval 120 --max-new 300 >> ../logs/gem5_{name}.log 2>&1")
    subprocess.run(["tmux", "new-window", "-d", "-t", "fv2_gem5", "-n", name, cmd], check=True)
    log.write(f"{dt.datetime.now().astimezone().isoformat(timespec='seconds')} LAUNCH {name} {c['config']}\n")
print("windows:", subprocess.run(["tmux", "list-windows", "-t", "fv2_gem5", "-F", "#W"],
                                 capture_output=True, text=True).stdout.split())
