#!/bin/bash
# SimSpect (2026-11-08, recon-ruby session): upstream STT master cwfletcher/stt @ 5bf41109477e1c9c5822674afa4103e6eb16ff09
# (tarball sha256 aa2281adff4d394e67a1618acdce9a3a7d64c9866f936ee5352433044604cc1c, /work/stt-master-src/),
# + SimSpect hooks = /work/stt's full working-tree diff vs e3283b9 (/work/stt-master-src/stt_worktree_vs_e3283b9.diff:
# stt.patch + resolve hooks incl. the wake edit), applied with patch -p1 (all hunks exact), + se_exp/se_futuristic/se_slowcomm.py.
# README -> README.md symlink as in /work/stt (SConscript info.py needs README).
# Same build command as /work/stt (gem5-hooks/resolve/rebuild_resolve_hooks.sh, python2 scons 2.5.1).
cd /work/stt-master
LOG=/work/stt-master/build_stt_master.log
{
echo "START $(date -u)"; df -h /work
SCONS_LIB_DIR=/usr/local/lib/python2.7/dist-packages/scons-2.5.1 python2 /usr/local/bin/scons -j16 build/X86/gem5.opt </dev/null
echo "EXIT=$?"; sha256sum build/X86/gem5.opt
echo "END $(date -u)"
} > $LOG 2>&1
