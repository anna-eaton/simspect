# SimSpect pipeline Makefile
#
# Variables (override on the command line):
#   MODEL     — Alloy model stem, e.g. SPT_6_oneLP        (required for most targets)
#   CONFIG    — generation config (paths/alloy/speculation; no gem5 build needed)
#   RUNCONFIG — execution config for testrun (the gem5 build/scheme to target)
#   FORCE     — set to 1 to re-run even if output exists  (default: unset)
#
# ── Recommended flow: pipelined producer + per-build consumers ───────────────
#   make gen   MODEL=SPT_6_oneLP CONFIG=runconfigs/run_config_SPT_6_oneLP.jsonc
#       Producer: xml + llvm + asm run CONCURRENTLY (all stages progress at
#       once); resumable; no gem5. Writes testsets/<MODEL>/.
#   make run   MODEL=SPT_6_oneLP RUNCONFIG=results/SPT_6_oneLP_fence/run_config.jsonc
#       Consumer: gem5 sweep, results split BY TRANSMITTER TYPE into a
#       timestamped results/<name>__<ts>/<mode>/<kind>/. Launch one per build;
#       run several (different RUNCONFIG) against the same MODEL concurrently.
#   make pipeline MODEL=... CONFIG=... RUNCONFIG=...
#       Producer in the background + one consumer in the foreground.
#
# ── Low-level engine (single build, sequential; used by the watchers) ────────
#   make xml/llvm/asm/gem5/all/clean MODEL=... CONFIG=...   (see pipeline.py)

MODEL     ?= STT_4
CONFIG    ?= run_config.jsonc
RUNCONFIG ?= $(CONFIG)
PY        := python3
SCRIPT    := pipeline.py

_FORCE := $(if $(filter 1,$(FORCE)),--force,)

.PHONY: all xml llvm asm gem5 clean help gen run pipeline

# ── Pipelined producer / consumer ────────────────────────────────────────────
gen:
	$(PY) testsetgen.py --model $(MODEL) --config $(CONFIG) $(_FORCE)

run:
	$(PY) testrun.py --model $(MODEL) --config $(RUNCONFIG)

pipeline:
	$(PY) testsetgen.py --model $(MODEL) --config $(CONFIG) $(_FORCE) \
	    > pipeline_gen_$(MODEL).log 2>&1 &
	$(PY) testrun.py --model $(MODEL) --config $(RUNCONFIG)

# ── Low-level engine ─────────────────────────────────────────────────────────
all:
	$(PY) $(SCRIPT) all --model $(MODEL) --config $(CONFIG) $(_FORCE)

xml:
	$(PY) $(SCRIPT) xml  --model $(MODEL) --config $(CONFIG) $(_FORCE)

llvm:
	$(PY) $(SCRIPT) llvm --model $(MODEL) --config $(CONFIG) $(_FORCE)

asm:
	$(PY) $(SCRIPT) asm  --model $(MODEL) --config $(CONFIG) $(_FORCE)

gem5:
	$(PY) $(SCRIPT) gem5 --model $(MODEL) --config $(CONFIG) $(_FORCE)

clean:
	$(PY) $(SCRIPT) clean --model $(MODEL) --config $(CONFIG)

help:
	@echo ""
	@echo "Recommended (pipelined):"
	@echo "  make gen      MODEL=<stem> CONFIG=<gen.jsonc>"
	@echo "                  Producer: xml+llvm+asm concurrently, resumable, no gem5."
	@echo "  make run      MODEL=<stem> RUNCONFIG=<build.jsonc>"
	@echo "                  Consumer: gem5 sweep, results split by transmitter type"
	@echo "                  into results/<name>__<ts>/<mode>/<kind>/. One per build."
	@echo "  make pipeline MODEL=<stem> CONFIG=<gen.jsonc> RUNCONFIG=<build.jsonc>"
	@echo "                  Producer (background) + one consumer (foreground)."
	@echo ""
	@echo "Engine (single build, sequential):"
	@echo "  make xml | llvm | asm | gem5 | all | clean   MODEL=<stem> CONFIG=<cfg>"
	@echo ""
	@echo "Vars: MODEL, CONFIG, RUNCONFIG (default=CONFIG), FORCE=1"
	@echo ""
	@echo "Examples:"
	@echo "  make gen MODEL=SPT_6_oneLP CONFIG=runconfigs/run_config_SPT_6_oneLP.jsonc"
	@echo "  make run MODEL=SPT_6_oneLP RUNCONFIG=results/SPT_6_oneLP_fence/run_config.jsonc"
	@echo ""
