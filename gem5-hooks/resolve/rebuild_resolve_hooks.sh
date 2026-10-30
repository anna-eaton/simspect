#!/bin/bash
# Back up, patch and rebuild one gem5 tree with the SimSpect resolve hooks (2026-10-30).
# Usage: rebuild_resolve_hooks.sh <build-name>     (names as in STAGE3_gem5/hook_audit.py BUILDS)
# Backups: <root>/build/<ISA>/gem5.opt.pre-resolve-hooks-20261030 (binary) and
#          /work/simspect_backups/resolve-hooks-20261030/<name>-src.tgz (the 3 patched files).
# Log: /work/simspect_backups/resolve-hooks-20261030/<name>.log
set -u
name=$1
HERE=$(cd "$(dirname "$0")" && pwd)
case $name in
  stt)                root=/work/stt;      isa=X86;                py=2 ;;
  stt-dbg)            root=/work/stt-dbg;  isa=X86;                py=2 ;;
  gem5-spt)           root=/work/gem5-spt; isa=X86_MESI_Two_Level; py=2 ;;
  amulet-InvisiSpec)  root=/work/amulet/amulet-gem5-InvisiSpec_AE-v1.1;  isa=X86_MESI_Two_Level; py=2 ;;
  amulet-CleanupSpec) root=/work/amulet/amulet-gem5-CleanupSpec_AE-v1.1; isa=X86_MESI_Two_Level; py=2 ;;
  amulet-STT)         root=/work/amulet/amulet-gem5-STT_AE-v1.1;         isa=X86; py=2 ;;
  amulet-SpecLFB)     root=/work/amulet/amulet-gem5-SpecLFB_AE-v1.1;     isa=X86; py=3 ;;
  gem5-recon-modded)  root=/work/gem5-recon-modded; isa=X86; py=3 ;;
  *) echo "unknown build $name"; exit 2 ;;
esac
BK=/work/simspect_backups/resolve-hooks-20261030
mkdir -p $BK
LOG=$BK/$name.log
bin=$root/build/$isa/gem5.opt
{
echo "[$(date -Iseconds)] START $name root=$root"
if [ ! -e $bin.pre-resolve-hooks-20261030 ]; then cp -p $bin $bin.pre-resolve-hooks-20261030; fi
sha256sum $bin.pre-resolve-hooks-20261030
cd $root || exit 1
o3=src/cpu/o3
files="src/cpu/pred/bpred_unit.cc $( [ -f $o3/iew_impl.hh ] && echo $o3/iew_impl.hh || echo $o3/iew.cc ) $( [ -f $o3/commit_impl.hh ] && echo $o3/commit_impl.hh || echo $o3/commit.cc )"
[ -e $BK/$name-src.tgz ] || tar czf $BK/$name-src.tgz $files
python3 $HERE/apply_resolve_hooks.py $root || exit 1
if [ $py = 3 ]; then
  SCONS_LIB_DIR= python3 /usr/bin/scons -j6 build/$isa/gem5.opt --ignore-style </dev/null
else
  SCONS_LIB_DIR=/usr/local/lib/python2.7/dist-packages/scons-2.5.1 python2 /usr/local/bin/scons -j6 build/$isa/gem5.opt </dev/null
fi
rc=$?
sha256sum $bin
echo "[$(date -Iseconds)] END $name rc=$rc"
} >> $LOG 2>&1
