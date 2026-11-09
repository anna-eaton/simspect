#!/usr/bin/env python3
"""Measurement queries for the STT_6_s4 / STT_6_a3c drafts (s4-variant, 2026-11-08).

Writes one .als per query into OUT_DIR (default: cwd); each is a copy of the draft with the
query as its FIRST run command (a6CountModels/a6CountOnly run the first command). Run from
STAGE1_alloy/, one java at a time, with a time limit, e.g.:
  gtimeout 600 /opt/homebrew/opt/openjdk@17/bin/java -Xmx4g -cp alloy6.jar:. a6CountOnly OUT/q1_s4_forced.als 20000
Results are recorded in wiki/state/ALLOY_MODEL_CHANGES.md ("2026-11-08 — STT_6_s4 / STT_6_a3c").
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else '.'
os.makedirs(OUT, exist_ok=True)
D=os.path.join(HERE,'STT_6_s4.als')
src=open(D).read()
SC=" for 9 but exactly 6 Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool\n"
extra='''
let glit_noboundary {
  not secure_speculation_scheme_p[no_p]
  all i: (unresolved - first_uncommitted) | secure_speculation_scheme_p[RR->i]
  all s: State | secure_speculation_scheme_p[RS->s]
}
let glit_nors {
  not secure_speculation_scheme_p[no_p]
  all i: (unresolved - first_uncommitted) | secure_speculation_scheme_p[RR->i]
  secure_speculation_scheme_p[RC->first_uncommitted + RR->first_uncommitted]
}
let glit_s4_rsonly {
  not secure_speculation_scheme_p[no_p]
  all i: (unresolved - first_uncommitted) | secure_speculation_scheme_p[RR->i]
  secure_speculation_scheme_p[RC->first_uncommitted + RR->first_uncommitted]
  all s: (State - s4_l1.outreg.opstate) | secure_speculation_scheme_p[RS->s]
}
// (q4 == q1 after the RS exemption was dropped from the draft)
let glit_s4_bdonly {
  not secure_speculation_scheme_p[no_p]
  all i: (unresolved - first_uncommitted) | secure_speculation_scheme_p[RR->i]
  (first_uncommitted in s4_b0) or secure_speculation_scheme_p[RC->first_uncommitted + RR->first_uncommitted]
  all s: State | secure_speculation_scheme_p[RS->s]
}
'''
Q={
 'q0_stt6_forced':'gen_useful_litmus\n  s4_shape',
 'q1_s4_forced':'gen_useful_litmus_s4\n  s4_shape',
 'q2_s4_unforced':'gen_useful_litmus_s4',
 'q3_s4_new_only':'gen_useful_litmus_s4\n  not gen_useful_litmus',
 'q4_s4_bdonly_forced':'glit_s4_bdonly\n  s4_shape',
 'q5_s4_rsonly_forced':'glit_s4_rsonly\n  s4_shape',
 'q6_stt6_unforced':'gen_useful_litmus',
 'q7_s4_new_not_s4shape':'gen_useful_litmus_s4\n  not gen_useful_litmus\n  not s4_shape',
}
anchor='run gen_lit_s4 {'
for k,body in Q.items():
    s=src.replace(anchor, extra+'run '+k+' {\n  '+body+'\n}'+SC+'\n'+anchor,1)
    open(os.path.join(OUT,f'{k}.als'),'w').write(s)
D2=os.path.join(HERE,'STT_6_a3c.als')
src2=open(D2).read()
Q2={
 'q8_stt6_a3c_forced':'gen_useful_litmus\n  a3c_shape',
 'q9_a3c_forced':'gen_useful_litmus_a3c\n  a3c_shape',
 'q10_a3c_unforced':'gen_useful_litmus_a3c',
 'q11_a3c_new_only':'gen_useful_litmus_a3c\n  not gen_useful_litmus',
}
for k,body in Q2.items():
    s=src2.replace('run gen_lit_a3c {','run '+k+' {\n  '+body+'\n}'+SC+'\nrun gen_lit_a3c {',1)
    open(os.path.join(OUT,f'{k}.als'),'w').write(s)
