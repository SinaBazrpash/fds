# From Python global output to native FDS EAE

## Choose the branch deliberately

- `EAE_1D_MAKE`: frozen original master `2f2733a84013faeeb6d705246b61678848f44ef5`.
  Original separate eae.f90 and original EAE build registrations; rollback reference.
- `master`:1D EAE integrated into existing native modules. **Static review only;
  this refactor has not been compiled or numerically verified.** No extra Fortran
  units or EAE Makefile entries; output binary naming returns to native FDS names.
- `EAE_3D_MAKE`: exact source snapshot of the verified local installed development
  executable, SHA256 `d17146541174acaf32b5c1aa09346e70ed188ac849dae7e6875ecb4c401349e2`.
  Optional fixed-volume native HT3D coupling and supported1D EAE, with extra modules.
  See that branch's provenance manifest and scoped historical validation report.

None enables new native LTE, pore networks, Darcy/diffusion, pore-to-CFD ports
or a total-energy extension. Dormant operator modules remain only on3D for exact
installed-source provenance. Ordinary native FDS governing equations remain.
No EAE3D recession/BURN_AWAY claim. Installed local executable is untouched.

## Exact parser mapping (statically verified, not a new numerical test)

FDS reads **namelists**, not the Python Excel workbook. There is no automatic
workbook import or generic Eeff-to-reaction conversion. Map the selected material's
**global** rows, keeping component association:

| Python workbook | Actual FDS MATL keyword | Units/action |
|---|---|---|
|Global_Summary.A_global_s_inv|EAE_A|s⁻¹; transfer directly, not log(A)|
|Global_Summary.K_best_global|EAE_K|integer1..15, number of Gaussian components|
|Global_PDF_Parameters.mu_kJmol|EAE_MU(i)|kJ/mol; no factor1000 in input|
|Global_PDF_Parameters.sigma_kJmol|EAE_SIGMA(i)|kJ/mol standard deviation, not variance|
|Global_PDF_Parameters.weight_pi|EAE_PI(i)|dimensionless nonnegative weights; positive total; keep component ID/order|
|Scientific_Definitions.PDF_support_kJmol|EAE_EMIN,EAE_EMAX|50,450 for this program; preserve actual fit support|
|Scientific_Definitions.Quadrature_nodes|EAE_NODES|180 for this program; node count is not K|
|First-order per-bin model|EAE_N=1|only accepted reaction order; not exported diagnostic f(alpha)|
|Ea_mean_global_kJmol|**No replacement keyword**|descriptive sum(pi*mu); do not substitute it for the mixture|
|Kinetics Eeff(T), f_all or f_alpha sheets|**No direct native table input here**|diagnostics/reconstruction, not alternative FDS rate laws|

The parser is READ_MATL in `Source/read.f90`; setup/kinetics are now in
`PHYSICAL_FUNCTIONS` in `Source/func.f90`, state in `Source/type.f90`.
`EAE_A`, `EAE_K` and exactlyK means/widths/weights are required when any EAE
parameter is supplied. Defaults: EAE_N1, EAE_NODES180, EAE_EMIN50, EAE_EMAX450.
Bounds accepted natively: K1..15, nodes8..512, A>0 and<=1e100,
0<EMIN<EMAX<=10000kJ/mol, positive means/widths<=10000, nonnegative pi with
positive total. The Python fit uses narrower bounds; preserve the actual fitted
values. Both normalize finite-range Gaussian weights by Gauss–Legendre quadrature.
FDS converts input kJ/mol to internal J/mol and uses the independent gas constant
8.314462618J/(molK), not the legacy FDS J/(kmolK) convention. **No interpolation
or energy-unit scaling is required for the Gaussian mapping.** Do not replace
EAE inputs with ordinary FDS `A,E`, whose conventions/model differ.

One intrinsic EAE reaction per material; different materials can have distinct
mixtures. The parser rejects competing legacy Arrhenius/oxidation/liquid channels,
non-first-order modifiers and generated reactive EAE residue. Inert residue is
supported. EAE is off unless opted in; its state/energy/source coupling is used
only on supported EAE material paths. Master gates nonplanar/non1D, variable
thickness, immersed geometry, particle paths and time scaling. Native geometric
and layer-removal behavior outside EAE remains native.

## Transparent mapping example

The following **illustrative values are not a fit result**:

```text
Global_Summary: Sample=Demo, A_global_s_inv=1e12, K_best_global=2,
               Ea_mean_global_kJmol=180
Global_PDF_Parameters:
  Demo, Component1, mu_kJmol150, sigma_kJmol15, weight_pi0.4
  Demo, Component2, mu_kJmol200, sigma_kJmol20, weight_pi0.6
```

Corresponding real parser fields:

```fortran
&MATL ID='DEMO', DENSITY=500., CONDUCTIVITY=0.2, SPECIFIC_HEAT=1.,
      N_REACTIONS=1, HEAT_OF_REACTION=0.,
      EAE_A=1.E12, EAE_K=2, EAE_N=1, EAE_NODES=180,
      EAE_EMIN=50., EAE_EMAX=450.,
      EAE_MU=150.,200., EAE_SIGMA=15.,20., EAE_PI=0.4,0.6,
      SPEC_ID='CARBON DIOXIDE', NU_SPEC=0.8,
      MATL_ID='INERT_RESIDUE', NU_MATL=0.2 /
```

Complete illustrative1D input: [global_mapping_1d.fds](../EAE/examples/global_mapping_1d.fds).
It follows the existing published thermal-TGA input structure, with an optional
prescribed actual-sample ramp for kinetic comparison. No example was executed in
this migration. Independent property/yield values in it are illustrative, **not
inferred from the Gaussian fit**, and are not validated material data.

The raw example CSV illustrates format and is unrelated to these chosen parameters;
no fitted relation between them is claimed. Existing FS1 examples are preserved
with their original global mixtures/properties/rate-specific residue assumptions.

## Conditions needed for meaningful comparison

The workbook does not supply density(kg/m³), conductivity(W/m/K), solid Cp(kJ/kg/K
in FDS input), reaction heat(kJ/kg under native convention), emissivity, transport,
thickness, boundary heating, species identities or gas/solid mass yields. Supply
these from physically supported measurements/model assumptions, not inferred
unique values from a mass-curve fit. Endpoint residual mass is not automatically
a physical final char yield: if mass is still decreasing, interpreting it as
complete residue changes both conversion and yields.

Python starts fresh surviving bins at each measured T0. Native FDS starts from
its initialized material state and actual temperature history. Use comparable
initial conditions and no undocumented preconversion. TGA heating rate isK/min;
Python converts toK/s internally; never pass rate/60 to a K/min input. Thermal
TGA heats a furnace/boundary and permits sample lag; explicit MISC
`EAE_TGA_PRESCRIBED=T` imposes a uniform actual sample ramp and is a thermostat
verification experiment. `EAE_TGA_LINEAR=T` uses the specified linear beginning/
end temperature hazard quadrature; otherwise beginning-temperature approximation
requires timestep convergence. Neither mode proves full calorimetry.

SURF `TGA_ANALYSIS=T,TGA_HEATING_RATE=...` and MISC TMPA,
TGA_FINAL_TEMPERATURE,TGA_DT,TGA_DUMP are actual existing controls; dedicated
TGA overrides native thin-sample/backing/convection/radiation setup. TGA_CONVERSION_FACTOR
must be1. TGA restart is explicitly rejected. Avoid using short endpoints to claim
physical complete burnout; preserve the program's measured-endpoint warning.

## Fixed-volume3D branch

The same MATL Gaussian mapping applies. Explicit SURF `HT3D=T,EAE_HT3D=T`
opts into the physical-cell adapter on `EAE_3D_MAKE`; these flags must **not** be
put on master as a way to enable unsupported3D. Required restrictions include
fixed Cartesian, one-to-one cell-aligned physical nodes, no linings or variable
thickness, no shrinking/swelling, persistent inert residue with positive solid
yield, nonnegative gas/solid yields summing to1, normalized positive directional
weights, exposed backing and midpoint routing (`BACKING='EXPOSED',LAYER_DIVIDE=-1`).
Set `MINIMUM_LAYER_MASS_FRACTION=0,MINIMUM_LAYER_THICKNESS=0` **only for this
supported fixed-volume coupling**, as required by its gate. This does not alter
ordinary FDS removal rules. There is no supported EAE HT3D cell-opening,
geometry recession, detached-solid or BURN_AWAY path. Dedicated TGA is1D only.

The MIN_LAYER_MASS initialization correction was already merged into the original
remote master via upstream PR16687, and is retained without reapplication.
Native thresholds and layer-thickness rules are unchanged. The3D installed
snapshot also includes validated restart-v2 changes; this migration does not
merge those additional3D interfaces into1D master.

## Build and evidence boundary

Use native Build scripts/Makefile or CMake prerequisites documented by FDS.
Master uses the **exact native-parent Make/CMake files** and33native source units;
there is no EAE object entry or new module file. Native executable names are
therefore `fds_*`/the CMake target name, unlike the frozen branch's `fdseae_*`.
Build into a fresh directory/prefix and do not overwrite an installed FDS binary.
This publication performs no build/configure/install step. On3D, extra module
registrations remain exactly as in the installed snapshot.

Historical installed1D/TGA/fixed-volume3D controls passed within their recorded
scope. Master's moved routine bodies are statically identical except a private
constant identifier, but module/interface/build changes have **not** been compiled
or run. No claim of new runtime equivalence, general MPI/restart equivalence,
exact CFD mass closure or full coupled CFD energy closure is made.
