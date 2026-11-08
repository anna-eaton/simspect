set -u
W=/work/amulet/hooks_v2_work
b=$1
LOG=$W/make_refs_$b.log
exec >> $LOG 2>&1
echo "[$(date -Iseconds)] START ref $b"
SRC=/work/amulet/amulet-gem5-${b}_AE-v1.1
REF=$W/ref_$b
if [ ! -d $REF ]; then cp -a $SRC $REF || { echo "cp failed"; exit 1; }; fi
# restore the v1+resolve snapshot of every file v2 touched
cd $W/v1snap_$b
for f in $(diff -rq -x '*.pyc' -x '._*' src $SRC/src 2>/dev/null | awk '/^Files/{print $2}'); do
  echo "restore $f"; cp -p $f $REF/$f
done
# re-apply the wake fix (resolve-hooks session, 2026-10-30 21:27) to iew_impl.hh
python3 - $REF/src/cpu/o3/iew_impl.hh <<'PY'
import re, sys
p=sys.argv[1]; s=open(p).read()
if "SimSpect resolve wake" in s:
    print("wake fix already present")
else:
    m=re.findall(r"\n( *)stall_inst->setExecuted\(\); instToCommit\(stall_inst\);\n", s)
    assert len(m)==1, "wake anchor not found"
    ind=m[0]; old="\n"+ind+"stall_inst->setExecuted(); instToCommit(stall_inst);\n"
    s=s.replace(old,"\n"+ind+"// SimSpect resolve wake (2026-10-30): wake the CPU, as a late memory response does.\n"+ind+"wakeCPU();\n"+ind+"stall_inst->setExecuted(); instToCommit(stall_inst);\n"+ind+"activityThisCycle();\n")
    open(p,"w").write(s); print("wake fix applied")
PY
cd $REF
if [ $b = SpecLFB ]; then
  SCONS_LIB_DIR= python3 /usr/bin/scons -j40 build/X86/gem5.opt --ignore-style </dev/null
else
  SCONS_LIB_DIR=/usr/local/lib/python2.7/dist-packages/scons-2.5.1 python2 /usr/local/bin/scons -j40 build/X86_MESI_Two_Level/gem5.opt </dev/null
fi
echo "[$(date -Iseconds)] END ref $b rc=$?"
