# SimSpect
SimSpect is a formal language and testing framework to specify and exercise security guarantees of a simulated implementation of a hardware Spectre defense. 

SimSpect's end-to-end pipeline applies to Spectre defense proposals with some hardware implementation in [gem5](https://www.gem5.org), a common academic computer architecture research simulator. However, it consists of multiple standalone components: a [[formal language]], a test-generation mechanism, a test-concretization mechanism, and a simulator instrumentation. 

This documentation will allow a user to reference the various components of SimSpect. The code for SimSpect is on Github. All my prior presentations and paper links are in [[submissions and presentations]].

**Goal**: For a proposed Spectre defense with defined security guarantees and a gem5 simulator implementation, generate and execute a *defense-specific* and *leakage-targeted* set of assembly litmus tests, to discover security contract violations in the implementation.

## Background
### Glossary
- **Transmitters**: instructions that leak one or more operands via a HSC
- **Speculation primitives:** instructions that initiate speculative executions, e.g., a conditional branch
- **Access instructions:** #towrite 
- **HSCA:** Hardware side channel attack
- **HSCD:** Hardware side channel defense (can be implemented in **hardware**, software, or **both**)
- **DUT:** Defense under test, a proposed hardware side channel defense that employs hardware modification implemented for proof of concept in the gem5 architectural simulator.
- **Security contract:** The defined Spectre security guarantees of a defense
- **Leakage path (LP):** The series of elements (instructions + their operands and state) that contribute to a microarchitectural leakage event.
- **Security property:** A high-level security property, specified architecturally, such as SNI. 
- **Execution**
- **Leakage path skeleton**
- **Transient**
- **Minimal**

### Executions vs. tests
**Program execution:** A snapshot of an assembly program at a specific cycle during its execution. Includes instructions, with metadata at the granularity of speculation direction and resolution, as well as committed status #towrite word this better. We need this metadata because the leakage we are studying occurs in the microarchitecture, so we are validating not on architectural outputs but on the occurrence of a particular microarchitectural state at some point in time. These are the minimal metadata components we deem necessary for the contract testing we are doing. #designchoice
**Litmus testing:** Litmus testing is the practice of running suites of (typically small and/or targeted) programs on an implementation under test to validate its functionality. #towrite cite and write this better.
**LILT: Leakage-inducing litmus tests** An execution is not a program. We want to generate programs to run on our implementation that *target* a particular microarchitectural execution. However, to have the best chance of inducing microarchitectural speculation and hitting the desired metadata state in this execution, we wish to grant ourselves control of microarchitectural knobs. These knobs include fixing branch predictor outcomes (to induce misprediction) both in direction and target, as well as fixing store set predictors for STL forwarding prediction (the mechanism for this is a separate point — we take advantage of the fact that we are operating on a simulator, which is a white box, to directly force these predictions, but one could also do this by training a predictor in the case where this instrumentation is not available, say while testing hardware #designchoice). Our LILTs therefore contain two components: an assembly program to be run, and an annotation which dictates speculation direction. They also have an output of sorts to check, not an architectural output, but rather they check that their #towrite #todo we will need to check that the committed instructions are committed and that nothing leaks when the program occurs as promised #designchoice. We initially generate abstracted target executions, then derive LILTs that target them.
# 1: Generation
#input*DUT with natural-language security guarantees* and a hardware proof-of-concept implementation in gem5**
#output*Set of program executions in Alloy xml output, with abstract instructions and partially specified state, as well as resolution and committed flags*
Our goal is to trigger leaking program **executions** by generating leakage-inducing **tests**. #todo repetitive. An **execution** in its final form as run on gem5 is an assembly program with annotations of speculation-force (mem and ctrl). In this generation phase, we generate all abstract executions in a particular syntax that contain a minimal leakage path as defined by the defense. See [[#1.2 Alloy]] for discussions of minimality.
## 1.1 Security contract
#input *Proposed Spectre defense natural-language security guarantees* 
#output *Formal specification in the Alloy execution syntax of the three security properties*
The goal is to define the security contract of each defense in the following three definitions. 
1. **Leakage contract:** A leakage contract is the set of pairs of *transmitters* (instructions that leak one or more operands via a hardware side channel) and their unsafe operand(s), as recognized by the defense.
2. **Execution contract:** An execution contract characterizes what speculative control- and data-flow is allowed on the microarchitecture by identifying what *speculation primitives* (instructions that initiate speculative executions, e.g., a conditional branch) the defense considers. 
3. **Protection set:** A protection set is the set of architectural state (memory and registers) that the defense promises to not leak architecturally and/or speculatively. Along with the protection set we encode a protection set update rule, that represents the updates that a given protection set undergoes with each instruction.
This definition is done manually.
## 1.2 Alloy
#input *Formal specification in the Alloy execution syntax of the three security properties*
#output *Set of program executions in Alloy xml output, with abstract instructions and partially specified state, as well as resolution and committed flags*
The defense-specific **protection set, leakage contract,** and **execution contract** are defined in the syntax of an execution. Then the Alloy Analyzer axiomatic model finder is used to enumerate all the possible abstract executions that contain a leakage path made up of these three components, and are minimal according to some metric. 
### 1.2.1 Execution syntax
In the generation phase we are only specifying instructions to the degree that a HSCD would differentiate. We do this to keep forms of violations limited, leaving enumeration across instruction types to the concretization phase of the pipeline #designchoice. The syntax of an abstract execution is as follows:

**Nodes:**
Instructions:
- Xmit
	- Ld
	- Str
	- Br
	- Other
- Non-xmit
	- Br
	- Other
State
- Reg
- Mem
Operands
- inmem
- inreg
- inaddr
- outreg
- outmem

An execution is made up of a series of instructions connected via spo which have some operands that are specific to that instruction and point to a state

**Booleans**
- committed (out of ROB, non-spec)
	- contiguous at end of SPO
- resolved
	- br knows target and condition
	- ld str knows address

**Edges**
- ordering
	- spo (i->i): speculative program order, defines the order of instructions #designchoice just including SPO vs PO, because we are targeting an execution
	- rf (o->o): reads-from relationship between output and input operands of instructions, used to calculate dataflow from protected state
	- ddi (o->o): data-dependence internal, relationship between input and output operands of the same instruction, used to calculate dataflow from protected state

**Instruction constraints**

| instr   | ops+xmits(*)              | dependency generation |
| ------- | ------------------------- | --------------------- |
| ld      | inaddr*, inmem, outreg    | ALLMEM->outreg        |
| str     | inaddr\*, inreg\*, outmem | inreg->outmem         |
| br_x    | inreg*                    |                       |
| other_x | inreg*, outreg            | inreg->outreg         |
| br_n    | inreg                     |                       |
| other_n | inreg, outreg             | inreg->outreg         |

#designchoice ld dependency generation assumption, #todo check if this is correct
### 1.2.2 Minimality
If we were to generate every execution up to a bound that contained a violating path, our test set, while it would be targeted, would be too large to feasibly run on our implementation. We adopt a method of relaxation that we model off of Lustig et al #todo cite in their work on memory consistency model verification. 
We degrade all of our tests within some set of relaxations until every component of the test is necessary for the leakage to occur, so that we do not include more state than we need. 
The space of relaxations is as follows:
- **Remove Instructions (RI):** remove an instruction from the test
- **Remove Operand (RO):** remove an operand from an instruction (link between instruction and state)
- **Remove State (RS):** remove a state element from the system
- **Shift Commit (RC):** make the last uncommitted instruction committed (only relevant when the execution contract uses the commit label/head of ROB)
- **Make Resolved (RR):** make an unresolved instruction resolved (only relevant when the execution contract uses resolved, note you can't do RC and RR at the same time. #todo need to do disjunction)
### 1.2.3 State specification
Classes of state: 
a. necessary for the leakage path
b. unnecessary for the leakage path

|                         | operand on LP | operand off LP but uses a | operand off LP no a |
| ----------------------- | ------------- | ------------------------- | ------------------- |
| **Instr on LP**         | ==y==         | ==?==                     | ?                   |
| **Instr off LP uses a** | ==n==         | ==y==                     | ?                   |
| **Instr off LP no a**   | n             | n                         | y                   |

Yellow boxes specified by the alloy model. We allow our model to be a little bigger than the minimal set of instructions, as long as all instructions use some amount of relevant state. This is because we can interleave later with irrelevant instructions in the concretization phase, and also flesh out irrelevant operands from that unassigned state space. We only need to make a statement about the existence of a leakage path, so we must determine all the state that has to do with that path and protect it in the Alloy phase such that we have complete control that it will leak. This method allows us to add spacer instructions that could interact with the leakage path without bloat. 
This approach leaves us with the following relaxations enabled: 
- **RS:** all state elements are necessary to the leakage path
- no **RI:** we can contain extra instructions as long as they have at least one necessary state operand
	- Fact {no Instructions - operands.Operand}
- no **RO:** we can contain extra operands as long as they have necessary state
	- Fact {no Operand - opstate.State}
- Execution contract
	- either **RR** or **RC**, depending on which one the execution contact utilizes, and if it uses both we have to say RR or RC fails but if both fail it doesn't matter

# 2: Concretization
#input*Set of program executions in Alloy xml output, with abstract instructions and partially specified state, as well as resolution and committed flags*
#output*Set of LILTs designed to trigger the input program executions, each consisting of a program with annotated speculation state*
## 2.1 Passes
[[concretization]] (too long)

## 2.2 Enumeration design space
- knobs in the jsonc
# 3: Simulation
## 3.1 Formatting programs
## 3.2 Fixing speculation
### 3.2.1 Ctrl
### 3.2.2 Dataflow


## 3.3 Observing outputs


#designchoice
#impl
#todo
#towrite


# Design choices
## Execution contract:
In testing we are broadly faced with the question of whether we will test to the conservative extent of the security contract, or to the space of possible leakage that intersects with the security contract.
### Gem5 speculation primitives and execution contract
The execution contract (defining which circumstances cause an instruction to be speculative) is defined in each defense in a conservative overarching definition. However, the effective space of *real* leakage is the intersection of the speculation in this contract and the speculation possible in gem5 (the *speculation primitives*)

We therefore distinguish two possible ways we could test a defense execution contract: 
1. test the execution contract broadly as specified by the defense
2. test the execution contract as projected onto *real speculation* in the gem5 speculation primitives
Option 2 is more gracious to the implementers, because it focuses on real bugs, but it is perhaps incomplete because the format of the defense implementation should theoretically cover the whole promised space of leakage, and should therefore match the broader execution contract. 
![[Pasted image 20260227143758.png]]
### Misprediction vs. correct prediction
We could test that the defense prevents leakage under speculation that will resolve to be incorrect (mispredicted taken, mispredicted not taken), but we could also test that the defense prevents leakage under speculation that will resolve to be correct, while it is speculative. This is another execution contract interpretation question. 
### Dependency chains
Even under actual speculation, if the window is conservative (e.g. any instruction that follows an unresolved load, even things that don't depend that load) we have the same issue. Does a real leakage path have to exist in our test that could arise and leak on the defense, or are we encroaching upon the defense's ability to specify its own security contract by deigning to define *real* leakage. We should have the opportunity to test both directions for all of these divides, and make a reasonable first assumption. 

Right now there exists two versions of many models, one that contains the raw execution contract and the other that contains the intersected execution contract. This design choice also arises in the non-Alloy later stages as well though, and is yet to be 100% resolved. 
## Scope of defenses
#towrite
[[Defense security contracts]]

## Bounds
- How long of tests we run

## todo:
- appendix of all the studied defenses and their contracts
- numbers on the defenses we have pushed through the pipeline
-

## questions
- what if it's not possible for a program to complete

- would we ever want excess unresolved instructions 