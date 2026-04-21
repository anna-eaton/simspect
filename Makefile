# SimSpect pipeline Makefile
#
# Variables (override on the command line):
#   MODEL  — Alloy model stem, e.g. STT_4          (required for most targets)
#   CONFIG — path to the TOML config file           (default: run_config.toml)
#   FORCE  — set to 1 to re-run even if output exists  (default: unset)
#
# Targets:
#   make xml    MODEL=STT_4    Phase 1 — Alloy → XML instances
#   make llvm   MODEL=STT_4    Phase 2 — XML  → LLVM IR + bare annotations
#   make asm    MODEL=STT_4    Phase 3 — LLVM → x86 asm + resolved annotations
#   make gem5   MODEL=STT_4    Phase 4 — gem5 window check
#   make all    MODEL=STT_4    Run all four phases in sequence
#   make clean  MODEL=STT_4    Delete generated/<MODEL> entirely

MODEL  ?= STT_4
CONFIG ?= run_config.jsonc
PY     := python3
SCRIPT := pipeline.py

_FORCE := $(if $(filter 1,$(FORCE)),--force,)

.PHONY: all xml llvm asm gem5 clean help

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
	@echo "Usage:  make <target> MODEL=<stem> [CONFIG=run_config.toml] [FORCE=1]"
	@echo ""
	@echo "Targets:"
	@echo "  xml     Phase 1: enumerate Alloy instances → generated/<MODEL>/xml/"
	@echo "  llvm    Phase 2: XML → LLVM IR             → generated/<MODEL>/llvm/"
	@echo "  asm     Phase 3: LLVM → x86 asm            → generated/<MODEL>/asm/ + ann/"
	@echo "  gem5    Phase 4: gem5 window check          → generated/<MODEL>/results/"
	@echo "  all     Run phases 1-4 in sequence"
	@echo "  clean   Delete generated/<MODEL>/ entirely"
	@echo ""
	@echo "Examples:"
	@echo "  make all   MODEL=STT_4"
	@echo "  make gem5  MODEL=STT_4 CONFIG=my_config.jsonc"
	@echo "  make asm   MODEL=STT_4 FORCE=1"
	@echo "  make clean MODEL=STT_4"
	@echo ""
