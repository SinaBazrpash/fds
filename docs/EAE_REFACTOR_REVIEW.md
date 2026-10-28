# Repository migration and static-only refactor review —2026-10-28

## Preservation and branch provenance

Remote original master: `2f2733a84013faeeb6d705246b61678848f44ef5`.
`EAE_1D_MAKE` was created/pushed at that exact commit before modifying master.
It is frozen: no amendment, rewrite or force push. The migration occurred in a
fresh clone, leaving all original local project source, reports, experiments,
Python input program and installed executable unchanged.

The installed executable SHA256 remains
`d17146541174acaf32b5c1aa09346e70ed188ac849dae7e6875ecb4c401349e2`.
Its41source hashes matched the preserved installation manifest before transfer.
`EAE_3D_MAKE` publishes those exact source bytes and existing CMake/Makefile
registrations, with provenance and the full historical local integration report.
Dormant operators are disclosed, not silently removed or substituted. SOURCE23
is excluded. One trailing-whitespace line in the installed wall.f90 snapshot is
preserved for hash equality; its whitespace warning is not disguised as PASS.
Master's diff has no whitespace errors.

The native source/build comparator is original master's existing upstream parent
`a93da69565cd724e977a34b152fc1f71d4648367`, not a newly fetched upstream revision.
Original master already contains commit `c8ddf16e8331f0026bce4ef099e2ea99815a0037`
(PR16687 MIN_LAYER_MASS initialization). No duplicate reapplication or new threshold
was introduced. Source/init.f90 stays byte-identical to original master.

## Master Fortran integration

- cons.f90 / GLOBAL_CONSTANTS: original EAE_ACTIVE defaultfalse, MAX_K15,
  MAX_NODES512, serialized version1 now use the existing shared module.
- type.f90 / TYPES: EAE_CONFIG and EAE_STATE are native derived types, with
  identical fields/defaults and persistent bin/reference/trial allocation shape.
- func.f90 / PHYSICAL_FUNCTIONS: six actual module procedures EAE_GL, EAE_SETUP,
  EAE_ALLOCATE, EAE_TRIAL, EAE_ACCEPT and EAE_DIAGNOSTICS. They use native types,
  explicit interfaces, intrinsic IEEE_IS_FINITE, and private EAE_RG8.314462618.
  No concatenated standalone module or new compilation unit remains.
- MEMORY_FUNCTIONS imports allocation from the existing PHYSICAL_FUNCTIONS.
  read/wall/dump imports use explicit procedure lists; restart flags/constants
  resolve through the existing GLOBAL_CONSTANTS host. READ_MATL semantics and
  wall consumption/remapping/heat/species logic are otherwise unchanged.
- Removed Source/eae.f90; exact original remains in frozen branch/history.
- Build/makefile and CMakeLists.txt match the native-parent bytes exactly,
  including original output names.33native .f90 units; zero extra EAE units,
  zero EAE object dependencies, zero EAE build registrations.

Static routine comparison covers the entire six bodies: text is identical except
private identifier RG->EAE_RG. This does not prove compiler/module/link/runtime
correctness. Native init/main/mass/divg/pres/velo/fire/radi/chem/data stay
byte-identical to original master. Ordinary physics is not newly rewritten;
this publication does not claim universal off-path behavior verification.
No3D coupling, LTE, pore, diffusion/ports or new energy equations enter master.

## Python corrections and evidence

Original supplied Python SHA256:
`389a166ef8f7a9564207594c96d613b87f948bffaabf5c9958603b6c644d9bb0`.
The local original was preserved; root repository eae.py is the corrected copy.

- Explicit category folders for every plot and a central save-path guard;
  close figures in finally, including failure paths.
- Per-material SETUP/RUN tee logs, timestamps/status, full input hash,
  rates/reference/units, QC and endpoint normalization, selected parameters,
  settings, warnings, optimizer failures and full tracebacks.
- Reject duplicate/nonfinite rates, colliding rate labels, unsafe/reused names,
  ambiguous output directories, insufficient/empty curves, nonphysical absolute
  temperatures and negative mass. Warn rather than silently hide overshoot,
  mass above100%, nonconverged optimizer candidates or legacy empty-core fallback.
- Setup/run identity and source/data/settings/library-aware checkpoint keys;
  atomic writes and finite/dimension cache checks. Identical runs may resume;
  changed identities require a new output directory. No pickle loading.
- Correct the **description**, not the actual fitting objective: it includes
  conversion, scaled smoothed-derivative and initial-rate penalties.
  Keep legacy RSS_global_equal_rate column, explain its meaning, add a separate
  alpha-only raw global RSS. BIC selection remains alpha-only,3K parameters.
- Exact Gaussian model, quadrature, starts/seeds, bounds, optimizer calls,
  individual/global objectives, normalization and output interpretations retained.
  A finite-positive PDF normalization guard and clearer degenerate reconstruction
  rejection expose genuine failures without substituting another model.

`docs/EAE_PYTHON_STATIC.json` records AST equality of14core scientific functions
and unchanged least_squares call arguments in both fitting routines. These are
source comparisons, not numerical tests. The legacy numerical f_alpha sheet
and analytic identity f_all sheets remain distinct and explicitly documented;
raw versus smoothed derivative definitions are not silently unified.

## Checks and explicit omissions

| Check | Result |
|---|---|
|Original master/frozen branch SHA equality|PASS via remote SHA verification|
|3D installed source/build provenance|PASS41source hashes plus build-file hashes|
|Master native33-file inventory|PASS; no added EAE units|
|Master native Makefile/CMake equality|PASS against existing native parent|
|Six moved routine body equivalence|PASS static text apart from constant identifier|
|Internal module/file dependency graph|PASS static acyclic; not compiler validation|
|Native control source unchanged|PASS hash/byte comparison listed above|
|Python syntax|PASS compile-only; program not imported/executed|
|Python scientific AST and optimizer argument comparison|PASS static|
|Plot routing/logging/sheet definitions/parser mapping|Inspected statically; runtime UNVERIFIED|
|Whitespace / ancestry / publication inventory|Reviewed during publication|
|Fortran compile/link, simulations, MPI/restart or regressions|NOT RUN, explicitly prohibited|
|DAEM optimization/synthetic fits/import/Excel/plot/log execution|NOT RUN, explicitly prohibited|

Run `python -B EAE/check_source.py` for repeatable **static-only** checks.
Historical installed validation covers ordinary1D/TGA and fixed-volume3D within
[its documented scope](https://github.com/SinaBazrpash/fds/blob/EAE_3D_MAKE/docs/LOCAL_INTEGRATION_20261028.md),
not newly refactored master. Existing preserved limitations include inherited
restart/decomposition differences, native lining mass/provenance findings,
finite-step gas-transport residuals and unestablished complete CFD energy closure.
No runtime verification is transferred simply because routine text matches.

## Rollback and limitations

To inspect the original1D layout, use a separate checkout of EAE_1D_MAKE at the
frozen SHA. Do not force-reset/push shared master. To undo publication later,
prepare an explicit normal revert commit after review; never mutate the frozen
branch.3D source can be reproduced from its manifest; local binary rollback is
unnecessary because no executable or installed project file was changed.

Master is limited to supported planar1D EAE, not HT3D EAE. Both branches retain
native pyrolysis when EAE is off and require physical yields/properties supplied
independently. Python endpoint-normalized curves do not identify complete-char
mass, kinetics uniquely or a new native heat/energy/transport law. Use Gaussian
parameters, not Eeff/f(alpha) curves, for the supported native namelist mapping.
