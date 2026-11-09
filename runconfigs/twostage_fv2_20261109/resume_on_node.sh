#!/usr/bin/env bash
# resume_on_node.sh — runs INSIDE a node's gem5_dev container (fed on stdin by move_campaigns.sh):
#   ssh <node> docker exec -i gem5_dev env TS=<testset> JOBS=<n> NODE=<node> bash -s < resume_on_node.sh
# Recreates the workspace symlinks, writes <row>_<TS>_<NODE>.jsonc (the campaign config with gem5.jobs = JOBS)
# and starts one `testrun.py --resume` per campaign of TS in tmux session fv2_gem5 (skips existing windows).
# 2026-11-09, simspect-c8.
set -eu
W=/tests/simspect_alloy_20261108
cd "$W"
ln -sfn ../${XMLSRC:-STT_6}/xml "testsets_twostage/$TS/xml"
# testrun.py --resume resolves results/<name>__latest and then needs it under the code root (relative_to),
# so results must be a REAL directory inside code_20261109 (results_fv2 becomes a symlink to it).
if [ ! -d code_20261109/results ] || [ -L code_20261109/results ]; then
  rm -f code_20261109/results
  if [ -d results_fv2 ] && [ ! -L results_fv2 ]; then mv results_fv2 code_20261109/results; else mkdir -p code_20261109/results; fi
  ln -sfn code_20261109/results results_fv2
fi
ln -sfn ../testsets_twostage code_20261109/testsets_twostage
mkdir -p logs
echo "asm stems (not_taken): $(ls "testsets_twostage/$TS/mispredict_not_taken/asm" | wc -l)"
cd code_20261109
CAMPAIGNS=${CAMPAIGNS:-runconfigs/twostage_fv2_20261109/campaigns.json} python3 - "$TS" "$JOBS" "$NODE" <<'EOF'
import json, subprocess, sys, datetime
ts, jobs, node = sys.argv[1], int(sys.argv[2]), sys.argv[3]
import os
camps = [r for r in json.load(open(os.environ.get("CAMPAIGNS", "runconfigs/twostage_fv2_20261109/campaigns.json"))) if r["model"] == ts]
if subprocess.run(["tmux", "has-session", "-t", "fv2_gem5"], capture_output=True).returncode:
    subprocess.run(["tmux", "new-session", "-d", "-s", "fv2_gem5", "-n", "ctl"], check=True)
have = subprocess.run(["tmux", "list-windows", "-t", "fv2_gem5", "-F", "#W"], capture_output=True, text=True).stdout.split()
log = open("../logs/fv2_gem5_launcher.log", "a")
for r in camps:
    text = open(r["config"]).read()
    cfg = json.loads(text.split("\n", 1)[1] if text.startswith("//") else text)
    cfg["gem5"]["jobs"] = jobs
    p = r["config"].replace(".jsonc", f"_{node}.jsonc")
    open(p, "w").write(f"// {r['config']} with gem5.jobs = {jobs} for {node} (resume_on_node.sh)\n" + json.dumps(cfg, indent=2) + "\n")
    name = r["results_name"]
    if name in have:
        continue
    cmd = (f"cd /tests/simspect_alloy_20261108/code_20261109 && python3 -u testrun.py --config {p} --model {ts} "
           f"--resume --interval 120 --max-new 300 >> ../logs/gem5_{name}.log 2>&1")
    subprocess.run(["tmux", "new-window", "-d", "-t", "fv2_gem5", "-n", name, cmd], check=True)
    log.write(f"{datetime.datetime.now().astimezone().isoformat(timespec='seconds')} LAUNCH {node} {name} {p} --resume\n")
print("windows:", subprocess.run(["tmux", "list-windows", "-t", "fv2_gem5", "-F", "#W"], capture_output=True, text=True).stdout.split())
EOF
