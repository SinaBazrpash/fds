# Local FDS_EAE integration — verified scoped installation

Installed `bin/fdseae.exe` is the newly compiled local development build. Native ordinary FDS/HT3D, supported1D EAE/TGA, tested MIN_LAYER_MASS initialization, restartv2 and the validated final08 fixed-volume EAE+HT3D path are operational in the tested scope. **This is NOT full native LTE/pore-network/geometry integration.** The new LTE, pore-network, reactive-residue, persistent-body, swept-transfer and separate body-checkpoint components are compiled/linked and independently operator-tested, but their native fluid/heat/geometry/MPI adapters are unfinished and were not enabled.

No new recession law or arbitrary burnout threshold was introduced. The original native layer-thickness, MIN_LAYER_MASS and delamination removal blocks are byte-identical to the pre-integration local source. The tested initialization correction stores the input minimum mass fractions and computes the HT3D thresholds from the actual initialized layer inventories. Existing rules remain responsible for ordinary native layer deletion; threshold loss is not silently reclassified as EAE gas. The supported fixed-volume EAE_HT3D path still rejects positive removal thresholds and other unsupported geometry. Ordinary native cases retain those capabilities.

## Recovery, source provenance and build

- Recoverable79-file byte-verified backup: `/mnt/c/Users/bazrpas1/Downloads/FDS_EAE/experimental_3d_20261021/local_integration_20261028_01/backup`; pre-integration hashes `reports/local_before.json`. Original executable SHA256 `4da86fc1c6255d42ed01ab1b446cf95fd1a0708fd49883c0fdab2627a8530c20`.
- Installed executable SHA256 `d17146541174acaf32b5c1aa09346e70ed188ac849dae7e6875ecb4c401349e2`; private MPI DLL and original launcher unchanged. Installed launcher `-v` succeeds without compiler-environment setup and identifies `EAE-local-integrated-20261028` / IntelMPI2021.18. Installed-binary G1 simulation matches the tested executable.
- Clean41-source native build: Intel ifx2026.1.0 Build20260617, MSVC2022, IntelMPI2021.18, private `eae_impi.dll` import library. `/Od /debug:full /traceback /check:bounds /fpp /D_WIN32 /wrap-margin-`, 1GB reserved stack, OpenMP off; no inherited objects. This is a runtime-checked local development executable, not an optimized performance release. Exact commands/compile order/source hashes/link inputs in `build/clean/build.cmd`, `build.log`, `build_manifest.json`.
- Actual complete local text patch: `patches/local_integration_complete.patch`, SHA256 `174e8de858041bcf85157980acd3735afd4a354f617d882da516b37c68e077f9` (17 files). Source/executable/install hashes: `reports/local_integration_manifest.json`. Tested MIN_LAYER_MASS and restart reference patches copied separately, not reapplied twice. Latest source modules verified against preserved manifests before transfer. No Git operation, upstream synchronization, official repository modification or publication occurred.
- `tools/Build-FDSEAE.cmd` now performs a clean timestamped local build through `tools/local_integrated_build.py`; it does not overwrite historical builds or automatically install. Native CMD build was executed; updated CMake/makefile registrations were reviewed but their alternate/platform configurations were not built. Original source files not part of the reviewed transfer retain their bytes, including TGA endpoint behavior.
- Rollback procedure: `ROLLBACK.md`. Preserve the then-current state, restore changed originals from the verified backup, archive newly added modules/helper files together with restoring build definitions, and restore the original executable. No deletion or automatic rollback was performed.

## Validation results

All original acceptance criteria retained.28 native simulation/rejection launches (including installed smoke;30rank-worker processes),2version-only probes and18operator processes completed. Previously successful simulations were reused when only analysis bookkeeping failed. All raw inputs, launchers, outputs and numerical reports are in this new isolated workspace.

| Category | Result | Evidence/scope |
|---|---|---|
| Ordinary multi-layer G1/G2 | PASS | Exact preserved candidate histories; initial inventories, yields and finite-step mass budgets pass |
| Native layer-removal G3 | PASS behavior; post-removal physical closure UNVERIFIED |12direction/material event times unchanged; native detachment remains native behavior, not a new conservation claim |
| Non-EAE variable-thickness G7 and ordinary opt-out | PASS | Matches preserved native controls |
| Supported1D EAE and forced burnout/removal | PASS | Fresh state histories and burnout accounting unchanged |
| Prescribed and thermal TGA | PASS | CSV outputs byte-identical to preserved controls |
| Native fixed-volume EAE kinetics/yields | PASS | Independent bin/distribution/yield/physical mass checks and source reference comparison |
| Nonuniform native HT3D conduction | PASS scoped | Physical temperatures/inventories match validated spatial case; prior convergence evidence reused |
| Native solid/reaction energy identity | PASS | Original relative1e-10 check; full resolved fluid energy NOT established |
| Ordinary and coupled adaptive restart | PASS | Device/physical state and actual timestep histories match full runs |
| Native1D historical restart | PASS historical trajectory; inherited full-vs-resume limitation retained | Preserved cycle7 resumed reference matched; no blanket uninterrupted1D restart equivalence claim |
| Native MPI1vs2 and restart1to2 | PASS | Same mesh decomposition; physical-cell/bin inventories and devices match exactly in rank-transition test |
| Unsupported/legacy rejection | PASS | Unopted EAE+HT3D, positive thresholds, inconsistent temperatures and missing HT3D footer rejected. Footer rejection can return exit0 in native FDS; explicit diagnostic and absence of successful completion are checked. No phase-zero fallback |
| Swept control-volume balances | PASS207 operator checks | Same compiled objects as installed native build; geometric/pressure-work/transactional oracles |
| Topology/porosity/depleted transfer | PASS23 operator checks | Explicit connectivity and conserved existing inventories; not native cell-opening proof |
| Zero-resistance network | PASS11 operator checks | Analytic blowdown/fill, unequal conductances, reverse flow, sealed/disconnected components, nonlinear properties, incompatible ports rejected |
| False burnout protection | PASS2 operator checks | Positive exponential populations retained, underflow rejected transactionally; no new native threshold |
| Reactive residue and histories | PASS6 operator cases | Two material-specific spectra, independent discrete/Bateman solutions and temporal convergence, material-order invariance |
| Separate body checkpoint | PASS10 checks in12launches |2adaptive sealed/connected byte-exact restarts plus8malformed/config/NaN/CRC rejections; fixed topology, single process |
| Persistent EAE/LTE/network body | PASS12 operator cases | Independently validated reference histories and exact conserved state |
| Native LTE/pore/fluid/geometry | NOT OPERATIONAL / GATED | No native metadata, port, heat, pressure/storage, cell-opening or geometry adapter |
| Native reactive EAE residue and new pore-state MPI/repartition | GATED / UNVERIFIED | Native parser restriction retained; separate body format requires identical topology/configuration |
| Complete fluid/solid/pore/radiation energy closure | NOT VERIFIED | Operators/reservoir and native solid/reaction checks do not establish full CFD energy closure |

Native comparison reports: 26 comparisons, 26 marked exact. Per-case results and unchanged criteria are retained, not replaced by this aggregate.

### Numerical budgets

- Native fixed-volume bin error: 4.02456e-16kg; physical solid+accepted gas mass residual 4.44089e-16kg.
- Native emitted gas ledger 0.0612978176529365kg; CFD inventory 0.061040588010125kg; integrated boundary release 0.061276730052126kg. Normalized by initial solid mass, residuals are -6.43074107e-05 and -5.2719002e-06; both pass the original1e-4 criterion. These are finite-step residuals, **not exact CFD mass closure**. Preserved prior startup/source/transport attribution and timestep refinement remain applicable.
- Native endothermic solid sensible change -1728.77226454568J; accepted reaction heat -1728.77226454744J; residual 1.75691639e-09J, limit 1.72877226e-07J. Reaction-source residual -2.27373675e-13J. This is the solid/reaction identity in the tested adiabatic case.
- Persistent LTE/pore-body mass residual <= 6.66133815e-16kg; combined solid+pore+port energy residual <= 3.66708264e-09J, within unchanged limits. This includes explicit reservoir ledgers, not resolved-fluid coupling.
- Reactive-residue material-order difference 1.38777878e-16kg. Independent Bateman errors decrease under the same timestep refinement; no tolerance altered.

## Preserved limitations and failed evidence

Shared-upstream G4lining mass deficit and G5fraction-provenance issue remain unresolved. The inherited decomposition discrepancy and supported1D cycle7 restart discrepancy are not repaired or waived by packaging. Their prior evidence remains unchanged. The old operator pressure-jump/algebraic projection and network stopping failures remain archived in evolution_02; corrected operator source is used, with the invalid shortcut gated. No native moving-front proof is inferred from remapping kernels.

Two copied-harness failures occurred after successful numerical results: missing journal `completed` field, and ambiguous binary clock scanning without a known-cycle filter. Both were diagnosed and corrected only in the new orchestration scripts. Original error logs/scripts/reports remain (`reports/orchestration_failure_01.json`, `_02.json`). Successful expensive simulations were verified and reused. No solver patch, rebuild or tolerance relaxation was used to make those checks pass.

## Preservation and next-phase boundary

Final full-project audit: PASS; 25985 pre-existing project files inventoried; prior experimental files verified: 12214. Only enumerated intended local source/build/helper/report/executable paths may change; no old evidence or official upstream files may change. `reports/preservation_audit.json` provides the exact list after completion.

Recommendation: the **tested ordinary/1D/fixed-volume native scope and packaged operator APIs** are verified for this local development installation. **Full native EAE/LTE/pore integration is incomplete.** Enabling the new operators in FDS requires a separate native integration phase: explicit pore metadata/ownership, consistent native thermochemical reference and combined heat capacity, conservative signed fluid mass/enthalpy/pressure coupling, geometry lifecycle/remapping, and native checkpoint/MPI/adaptive conservation checks. Existing protections remain. No additional physical law was introduced during this task. Work stops after this scoped local verification for the user's next instructions.
