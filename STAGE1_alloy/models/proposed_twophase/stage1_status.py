#!/usr/bin/env python3
"""stage1_status.py — print the live Stage-1 status table from launch_stage1.py's status JSON.

Usage: python3 stage1_status.py [<ws>/status/stage1_status.json]
"""
import json
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "/tests/simspect_alloy_20261108/status/stage1_status.json"
s = json.load(open(path))
hl = s["host_load"]
print("updated %s  load %.1f/%d  mem %.0f GB  disk %.0f GB  contention=%s %s" % (
    s["updated"], hl["load1"], hl["ncpu"], hl["mem_available_gb"] or -1, hl["disk_free_gb"],
    hl["contention"], "; ".join(hl["reasons"])))
for fam, v in s["families"].items():
    print("%-24s done %2d/%2d running %2d  instances %8d  %s" % (
        fam, v["done"], v["partitions"], v["running"], v["instances"], v["verdicts"]))
print()
for p in s["partitions"]:
    print("%-24s %-14s %-8s %-10s %8d  %s s" % (
        p["family"], p["part"], p["state"], p["verdict"], p["instances"] or 0, p["elapsed_s"]))
