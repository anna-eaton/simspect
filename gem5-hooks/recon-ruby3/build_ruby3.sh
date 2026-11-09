#!/bin/bash
# SimSpect recon-ruby (2026-11-08): authors' ReCon build. Tree = copy of /work/gem5-recon-modded
# (SimSpect hooks included; src/mem/ruby already == ruby-versions/ruby-singlecore), built with
# PROTOCOL=MESI_Three_Level per the authors' email (simspect documentation/docs/Files/email.txt).
# gem5.opt (not the authors' gem5.fast) because SimSpect needs O3PipeView/LSQUnit DPRINTFs.
cd /work/gem5-recon-ruby3
LOG=/work/gem5-recon-ruby3/build_ruby3.log
{
echo "START $(date -u)"; df -h /work
echo "ruby vs ruby-singlecore diff entries: $(diff -rq src/mem/ruby ruby-versions/ruby-singlecore | wc -l)"
/usr/bin/scons build/X86/gem5.opt PROTOCOL=MESI_Three_Level -j 24
echo "EXIT=$?"
echo "END $(date -u)"
} > $LOG 2>&1
