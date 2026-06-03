#!/usr/bin/env python3
# Insert an observation-only DPRINTF (loaded value) into completeDataAccess.
from pathlib import Path
f = Path("/work/stt-dbg/src/cpu/o3/lsq_unit_impl.hh")
t = f.read_text()
anchor = ("    LSQSenderState *state = dynamic_cast<LSQSenderState *>(pkt->senderState);\n"
          "    DynInstPtr inst = state->inst;\n")
assert anchor in t, "anchor not found"
ins = anchor + (
    "    { uint64_t _pocv = 0;\n"
    "      if (pkt->isRead() && pkt->hasData() && pkt->getSize() <= 8)\n"
    "          memcpy(&_pocv, pkt->getConstPtr<uint8_t>(), pkt->getSize());\n"
    "      DPRINTF(LSQUnit, \"POCVAL [sn:%lli] PC %s pa:%#x sz:%d val:%#llx squashed:%d\\n\",\n"
    "              inst->seqNum, inst->pcState(), pkt->getAddr(), pkt->getSize(),\n"
    "              (unsigned long long)_pocv, inst->isSquashed()); }\n")
f.write_text(t.replace(anchor, ins, 1))
print("edit applied")
