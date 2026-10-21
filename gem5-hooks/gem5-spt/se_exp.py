# Copyright (c) 2012-2013 ARM Limited
# All rights reserved.
#
# The license below extends only to copyright in the software and shall
# not be construed as granting a license to any other intellectual
# property including but not limited to intellectual property relating
# to a hardware implementation of the functionality of the software
# licensed hereunder.  You may use the software subject to the license
# terms below provided that you ensure that this notice is replicated
# unmodified and in its entirety in all distributions of the software,
# modified or unmodified, in source code or in binary form.
#
# Copyright (c) 2006-2008 The Regents of The University of Michigan
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met: redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer;
# redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution;
# neither the name of the copyright holders nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# Authors: Steve Reinhardt

# Simple test script
#
# "m5 test.py"

import optparse
import sys
import os
import json

import m5
from m5.defines import buildEnv
from m5.objects import *
from m5.util import addToPath, fatal, warn


def load_branch_annotations(path, base):
    with open(path, 'r') as f:
        data = json.load(f)
    if 'annotations' not in data:
        fatal("branch annotation file %s has no 'annotations' key" % path)
    branch_pcs, forced_targets, stall_cycles = [], [], []
    for e in data['annotations']:
        br = e.get('branch_pc_addr_hex') or e.get('branch_pc_addr')
        if br is None:
            rel = e.get('x86_pc_offset_hex') or e.get('x86_pc_offset') or \
                  e.get('x86_branch_offset_hex') or e.get('x86_branch_offset')
            if rel is None: continue
            br = int(str(rel), 0) + base
        else:
            br = int(str(br), 0)
        mode = e.get('mode', '')
        if mode in ('correctly_not_taken', 'mispredict_not_taken'):
            tgt = 0
        else:
            # *_addr fields are absolute PCs; *_x86_offset fields are
            # function-relative and need `base` added — same convention as
            # branch PC above.
            tgt_abs = e.get('btb_forced_target_addr_hex') or e.get('btb_forced_target_addr')
            if tgt_abs is not None:
                tgt = int(str(tgt_abs), 0)
            else:
                tgt_rel = e.get('btb_forced_target_x86_offset_hex') or e.get('btb_forced_target_x86_offset')
                if tgt_rel is None: continue
                tgt = int(str(tgt_rel), 0) + base
        branch_pcs.append(br)
        forced_targets.append(tgt)
        stall_cycles.append(int(e.get('resolve_stall_cycles', 0)))
    return branch_pcs, forced_targets, stall_cycles


addToPath('../')

from ruby import Ruby

from common import Options
from common import Simulation
from common import CacheConfig
from common import CpuConfig
from common import MemConfig
from common.Caches import *
from common.cpu2000 import *

# Check if KVM support has been enabled, we might need to do VM
# configuration if that's the case.
have_kvm_support = 'BaseKvmCPU' in globals()
def is_kvm_cpu(cpu_class):
    return have_kvm_support and cpu_class != None and \
        issubclass(cpu_class, BaseKvmCPU)

def get_processes(options):
    """Interprets provided options and returns a list of processes"""

    multiprocesses = []
    inputs = []
    outputs = []
    errouts = []
    pargs = []

    workloads = options.cmd.split(';')
    if options.input != "":
        inputs = options.input.split(';')
    if options.output != "":
        outputs = options.output.split(';')
    if options.errout != "":
        errouts = options.errout.split(';')
    if options.options != "":
        pargs = options.options.split(';')

    idx = 0
    for wrkld in workloads:
        process = Process(pid = 100 + idx)
        process.executable = wrkld
        process.cwd = os.getcwd()

        if options.env:
            with open(options.env, 'r') as f:
                process.env = [line.rstrip() for line in f]

        if len(pargs) > idx:
            process.cmd = [wrkld] + pargs[idx].split()
        else:
            process.cmd = [wrkld]

        if len(inputs) > idx:
            process.input = inputs[idx]
        if len(outputs) > idx:
            process.output = outputs[idx]
        if len(errouts) > idx:
            process.errout = errouts[idx]

        multiprocesses.append(process)
        idx += 1

    if options.smt:
        assert(options.cpu_type == "DerivO3CPU")
        return multiprocesses, idx
    else:
        return multiprocesses, 1


parser = optparse.OptionParser()
Options.addCommonOptions(parser)
Options.addSEOptions(parser)

if '--ruby' in sys.argv:
    Ruby.define_options(parser)

(options, args) = parser.parse_args()

if args:
    print "Error: script doesn't take any positional arguments"
    sys.exit(1)

multiprocesses = []
numThreads = 1

if options.bench:
    apps = options.bench.split("-")
    if len(apps) != options.num_cpus:
        print "number of benchmarks not equal to set num_cpus!"
        sys.exit(1)

    for app in apps:
        try:
            if buildEnv['TARGET_ISA'] == 'alpha':
                exec("workload = %s('alpha', 'tru64', '%s')" % (
                        app, options.spec_input))
            elif buildEnv['TARGET_ISA'] == 'arm':
                exec("workload = %s('arm_%s', 'linux', '%s')" % (
                        app, options.arm_iset, options.spec_input))
            else:
                exec("workload = %s(buildEnv['TARGET_ISA', 'linux', '%s')" % (
                        app, options.spec_input))
            multiprocesses.append(workload.makeProcess())
        except:
            print >>sys.stderr, "Unable to find workload for %s: %s" % (
                    buildEnv['TARGET_ISA'], app)
            sys.exit(1)
elif options.cmd:
    multiprocesses, numThreads = get_processes(options)
else:
    print >> sys.stderr, "No workload specified. Exiting!\n"
    sys.exit(1)


(CPUClass, test_mem_mode, FutureClass) = Simulation.setCPUClass(options)
CPUClass.numThreads = numThreads

# Check -- do not allow SMT with multiple CPUs
if options.smt and options.num_cpus > 1:
    fatal("You cannot use SMT with multiple CPUs!")

np = options.num_cpus
system = System(cpu = [CPUClass(cpu_id=i) for i in xrange(np)],
                mem_mode = test_mem_mode,
                mem_ranges = [AddrRange(options.mem_size)],
                cache_line_size = options.cacheline_size)

if numThreads > 1:
    system.multi_thread = True

# Create a top-level voltage domain
system.voltage_domain = VoltageDomain(voltage = options.sys_voltage)

# Create a source clock for the system and set the clock period
system.clk_domain = SrcClockDomain(clock =  options.sys_clock,
                                   voltage_domain = system.voltage_domain)

# Create a CPU voltage domain
system.cpu_voltage_domain = VoltageDomain()

# Create a separate clock domain for the CPUs
system.cpu_clk_domain = SrcClockDomain(clock = options.cpu_clock,
                                       voltage_domain =
                                       system.cpu_voltage_domain)

# If elastic tracing is enabled, then configure the cpu and attach the elastic
# trace probe
if options.elastic_trace_en:
    CpuConfig.config_etrace(CPUClass, system.cpu, options)

# All cpus belong to a common cpu_clk_domain, therefore running at a common
# frequency.
for cpu in system.cpu:
    cpu.clk_domain = system.cpu_clk_domain

if is_kvm_cpu(CPUClass) or is_kvm_cpu(FutureClass):
    if buildEnv['TARGET_ISA'] == 'x86':
        system.kvm_vm = KvmVM()
        for process in multiprocesses:
            process.useArchPT = True
            process.kvmInSE = True
    else:
        fatal("KvmCPU can only be used in SE mode with x86")

# Sanity check
if options.fastmem:
    if CPUClass != AtomicSimpleCPU:
        fatal("Fastmem can only be used with atomic CPU!")
    if (options.caches or options.l2cache):
        fatal("You cannot use fastmem in combination with caches!")

if options.simpoint_profile:
    if not options.fastmem:
        # Atomic CPU checked with fastmem option already
        fatal("SimPoint generation should be done with atomic cpu and fastmem")
    if np > 1:
        fatal("SimPoint generation not supported with more than one CPUs")

for i in xrange(np):
    if options.smt:
        system.cpu[i].workload = multiprocesses
    elif len(multiprocesses) == 1:
        system.cpu[i].workload = multiprocesses[0]
    else:
        system.cpu[i].workload = multiprocesses[i]

    if options.fastmem:
        system.cpu[i].fastmem = True

    if options.simpoint_profile:
        system.cpu[i].addSimPointProbe(options.simpoint_interval)

    if options.checker:
        system.cpu[i].addCheckerCpu()

    if options.branch_ann_file:
        bpcs, btgts, bstall = load_branch_annotations(
            options.branch_ann_file, options.branch_ann_base)
        system.cpu[i].branchPred.annotationBranchPCs = bpcs
        system.cpu[i].branchPred.annotationForcedTargets = btgts
        system.cpu[i].branchPred.annotationResolveStallCycles = bstall

    system.cpu[i].createThreads()

if options.ruby:
    Ruby.create_system(options, False, system)
    assert(options.num_cpus == len(system.ruby._cpu_ports))

    system.ruby.clk_domain = SrcClockDomain(clock = options.ruby_clock,
                                        voltage_domain = system.voltage_domain)
    for i in xrange(np):
        ruby_port = system.ruby._cpu_ports[i]

        # Create the interrupt controller and connect its ports to Ruby
        # Note that the interrupt controller is always present but only
        # in x86 does it have message ports that need to be connected
        system.cpu[i].createInterruptController()

        # Connect the cpu's cache ports to Ruby
        system.cpu[i].icache_port = ruby_port.slave
        system.cpu[i].dcache_port = ruby_port.slave
        if buildEnv['TARGET_ISA'] == 'x86':
            system.cpu[i].interrupts[0].pio = ruby_port.master
            system.cpu[i].interrupts[0].int_master = ruby_port.slave
            system.cpu[i].interrupts[0].int_slave = ruby_port.master
            system.cpu[i].itb.walker.port = ruby_port.slave
            system.cpu[i].dtb.walker.port = ruby_port.slave
else:
    MemClass = Simulation.setMemClass(options)
    system.membus = SystemXBar()
    system.system_port = system.membus.slave
    CacheConfig.config_cache(options, system)
    MemConfig.config_mem(options, system)

# [SafeSpec] Configure simulation scheme
# Pipeline-compat: --scheme=2 (from SimSpect gem5_common.py) maps to
# SpectreSafeInvisibleSpec + applyDDIFT (STT/DDIFT taint tracking) with the
# conservative-untainting defaults used for the SPT_6 sweep (backward
# propagation on, forward off, ideal off, shadow-L1 off).
if options.scheme == "2":
    # Pipeline-compat: --scheme=2 (SimSpect gem5_common.py) maps to SpectreSafeFence.
    # All SPT-specific defense knobs (applyDDIFT, bwdUntaint, fwdUntaint,
    # configImpFlow, etc.) come from the run_config's gem5.extra_args list, not
    # from this se.py default. Note: SPT cpu.cc:504 ANDs fwdUntaint into
    # bwdUntaint, so the run_config must set both if it wants backward.
    options.scheme = "SpectreSafeFence"
if options.needsTSO is None:
    options.needsTSO = 0
if CPUClass == DerivO3CPU:
    CpuConfig.config_scheme(CPUClass, system.cpu, options)
    # Hold the architectural retire of the first non-committed instruction for
    # N cycles, widening the speculation window so check_ld's
    # `xmit < fnc_retire` test has time to fire. Requires the gem5-side
    # cpu.fncCommitStallPC / fncCommitStallCycles params (ported from
    # /work/stt/src/cpu/o3/). If gem5-spt's CPU doesn't expose these yet, the
    # assignment will fatal — port the source-side hook first.
    if options.fnc_commit_stall_cycles > 0:
        for cpu in system.cpu:
            cpu.fncCommitStallPC     = options.fnc_commit_stall_pc
            cpu.fncCommitStallCycles = options.fnc_commit_stall_cycles

    # [SimSpect slow-comm experiment] Stretch IEW<->commit communication and
    # drain squash one inst/cycle to widen the observable speculative window
    # (faithful port of /work/stt/configs/example/se_slowcomm.py). Runtime
    # params only — same binary. backComSize/forwardComSize MUST exceed the
    # delays (timebuffer read at getWire(-delay)). commitToIEWDelay LIVELOCKED
    # the STT O3 model at >=5 (capped at 4); gem5-spt is DerivO3CPU+Ruby — its
    # ceiling is UNVERIFIED, smoke-test before a full corpus run. See claudelog.
    # [SimSpect paper_fragility] env-driven so commitToIEWDelay can be SWEPT
    # (additive copy of se_slowcomm.py; se.py/se_slowcomm.py untouched). Only
    # applies a param when its SIMSPECT_* env var is set.
    import os as _os
    def _envi(n):
        v = _os.environ.get(n)
        return int(v) if v not in (None, "") else None
    for cpu in system.cpu:
        if _envi("SIMSPECT_IEW_COMMIT_DELAY") is not None: cpu.iewToCommitDelay = _envi("SIMSPECT_IEW_COMMIT_DELAY")
        if _envi("SIMSPECT_COMMIT_IEW_DELAY") is not None: cpu.commitToIEWDelay = _envi("SIMSPECT_COMMIT_IEW_DELAY")
        if _envi("SIMSPECT_BACK_COM_SIZE")    is not None: cpu.backComSize      = _envi("SIMSPECT_BACK_COM_SIZE")
        if _envi("SIMSPECT_FWD_COM_SIZE")     is not None: cpu.forwardComSize   = _envi("SIMSPECT_FWD_COM_SIZE")
        if _envi("SIMSPECT_SQUASH_WIDTH")     is not None: cpu.squashWidth      = _envi("SIMSPECT_SQUASH_WIDTH")

root = Root(full_system = False, system = system)
Simulation.run(options, root, system, FutureClass)
