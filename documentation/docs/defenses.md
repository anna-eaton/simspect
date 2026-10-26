#todo 
## Defense table

Hardware component defenses

| Defense name                                                                                | Authors + Conference   | Gem5?                                                            |
| ------------------------------------------------------------------------------------------- | ---------------------- | ---------------------------------------------------------------- |
| [STT](https://iacoma.cs.uiuc.edu/iacoma-papers/micro19_2.pdf)                               | Yu+, MICRO '19         | [yes](https://github.com/cwfletcher/stt)                         |
| [SpecShield](https://dl.acm.org/doi/10.1109/PACT.2019.00020)                                | Barber+, PACT '19      | [boom only](https://github.com/MoeinGhaniyoun/BOOMv3-SpecShield) |
| [NDA](https://dl.acm.org/doi/10.1145/3352460.3358306)                                       | Weisse+, MICRO '19     | no                                                               |
| [Delay-on-Miss](https://dl.acm.org/doi/pdf/10.1145/3307650.3322216)                         | Sakalis+, ISCA '19     | no open source                                                   |
| [SDO](https://iacoma.cs.uiuc.edu/iacoma-papers/isca20_2.pdf)                                | Yu+, ISCA '20          | [yes](https://github.com/cwfletcher/sdo)                         |
| [SPT](https://cwfletcher.github.io/content/research/2021.micro.spt.paper.pdf)               | Choudhary+, MICRO '21  | [yes](https://github.com/FPSG-UIUC/SPT)                          |
| [Recon](https://dl.acm.org/doi/10.1145/3613424.3623770)                                     | Aimoniotus+, MICRO '23 | [closed source](Files/email.txt)                                 |
| [Doppelganger loads](https://dl.acm.org/doi/abs/10.1145/3579371.3589088)                    | Kvalsvik+, ISCA '23    | [closed source](Files/email.txt)                                 |
| [Protean](https://www.computer.org/csdl/proceedings-article/hpca/2026/11408570/2eA8gbMKaf6) | Mosier+, HPCA '26      | [yes](https://github.com/StanfordPLArchSec/protean-gem5)         |
| Invisispec                                                                                  | (amulet versions)      | [yes](https://github.com/mjyan0720/InvisiSpec-1.0)               |
| SpecLFB                                                                                     |                        |                                                                  |
| CleanupSpec                                                                                 |                        |                                                                  |

## AMuLeT baseline
- amulet runs insecure baseline, the three load-only defenses(Invisispec, SpecLFB, CleanupSpec), and STT
All of last three are load only i think, CT-SEQ, implementations in the [AMuLeT repo](https://github.com/sith-lab/amulet)
%% - invisispec they are inviisble to the cache hierarchy
- lfb load fill buffer, copy it into real cache later
- track cache lines that were touched and erase that after %%
%% - what if the cache was all full and that makes it far??
- final cache state is leakage model %%


## SimSpect defense scoping
#todo hardware vs software

## SimSpect defense specifications




