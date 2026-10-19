# Experimental FDS-EAE Global DAEM extension

This source-only publication is based on upstream firemodels/fds master
`b2bd16808fa3c76466b4a5eb83335575b611abf1`.

## Model and input

Activation energies are a finite-bound normalized Gaussian mixture sampled by
Gauss-Legendre quadrature. K is the number of Gaussian components, independently
of the quadrature-node count. Each active planar solid cell carries nonnegative
unreacted bin masses and a transported reference mass. The kernel integrates
`dM_i/dt=-A*exp(-E_i/(R*T(t)))*M_i`, with R=8.314462618 J/(mol K).
Conversion is `1-sum(M_i)/reference`. Eeff is the full survival-weighted effective
Arrhenius energy; it is diagnostic, not a replacement single-energy rate.

Opt-in MATL inputs: EAE_A (1/s), EAE_K, EAE_MU, EAE_SIGMA, EAE_PI, EAE_N=1,
EAE_NODES, EAE_EMIN, EAE_EMAX. All energy inputs are kJ/mol; the kernel uses
J/mol independently of the legacy J/kmol convention. K=1..15, nodes=8..512.
One EAE reaction per material is supported, with multiple independent materials.
Competing EAE/legacy reactions within one material and generated reactive EAE
residue are rejected. Keep physical gas/solid yields, reaction enthalpy and
transport properties in the ordinary MATL definitions. Legacy cases do not
activate EAE merely by using this executable.

## Coupling and persistence

Ordinary accepted FDS consumption caps pending bin losses; committed bin loss
is checked against accepted density loss times current cell width. Bin masses
and reference masses are conservatively remapped separately from cell volumes.
Forced-layer removal respects the burnout cap rather than consuming every bin
unconditionally. Product formation and source terms remain in the FDS solver.
Restart serialization includes bins/reference and a versioned kinetics identity
header; incompatible EAE restarts are rejected. Existing restrictions reject
unsupported particle, immersed and nonplanar/3-D solid paths. Serial source
presence does not certify MPI/OpenMP correctness.

Wall diagnostics: EAE_CONVERSION, EAE_REMAINING_MASS, EAE_EEFF (kJ/mol).
Remaining bin mass is local reactive mass per reference face area, **not total
sample mass**. At complete reactive exhaustion Eeff=0 is an undefined-value
sentinel. Local conversion uses the transported reference, not density ratios.

## TGA

Original SURF TGA controls and MISC TGA_ANALYSIS/TGA_HEATING_RATE are supported.
For a MISC request select exactly one material-bearing sample surface. Heating
rate is K/min and controls the furnace history only. The ordinary thermal TGA
path uses the accepted beginning-cell-temperature approximation, with timestep
convergence required. Upstream TGA enforces a single thin layer, insulated
backing, fixed convection and no radiation; input thickness is overridden.

Explicit MISC `EAE_TGA_PRESCRIBED=.TRUE.` imposes a uniform actual sample ramp
for kinetic verification and uses known beginning/end temperatures in hazard
quadrature. It is a thermostat experiment, not an equivalent furnace/thermal
prediction. EAE_TGA_LINEAR=.FALSE. selects the beginning-temperature approximation
for comparison. A rate-specific fitted kinetic parameter is never introduced.

The EAE path writes CHID_tga.csv with Time,Temp,T_surf,Total Mass; T_surf in
this EAE-specific schema is the mass-weighted sample temperature. Total Mass
integrates **all** remaining solids including char over current volumes,
normalized by actual initial total mass. CHID_eae_tga.csv supplies sample
mean/min/max temperatures, reactive mass, non-EAE solid mass, conversion,
Eeff, instantaneous derivatives, accepted cumulative gas, removed solid and
mass-closure error. Its Eeff is a remaining-mass weighted average of local
Eeff for nonuniform samples. Source energy is a net volumetric source integral,
not validated DSC calorimetry. CHID_eae_tga_bins.csv exposes final bin states.
The EAE native CSV has a reduced schema; non-EAE legacy TGA output is unchanged.
TGA_CONVERSION_FACTOR must equal1. The upstream startup TGA loop has no usable
checkpoint/resume clock; EAE TGA RESTART is explicitly unsupported.

The three FS1 example inputs retain identical global kinetics and supplied
properties but different supplied gas/char yields: 5K/min .50817265/.49182735;
10K/min .50786345/.49213655; 40K/min .47280965/.52719035. These are conditional
assumptions, not independently validated material properties. No experimental
workbooks or mass curves are included. Their controls start at30.25C, end at
furnace798.25C, and use dt0.05s; physical source inputs are not refitted.

## Building and verification status

CMake registers Source/eae.f90 and names the executable fdseae while retaining
the upstream logical target fds. The existing Build/makefile target names remain;
its object lists and .o/.obj dependencies include EAE, and resulting binary
basenames begin fdseae_ to distinguish them from standard FDS. Upstream compiler
and optional-library requirements remain. Do not run installation steps into an
existing FDS prefix or add unreviewed DLLs to its directory. No machine-specific
runtime libraries, compiler paths, executables or generated artifacts are shipped.

Only static source checks were performed for this publication. They establish
transfer coverage, module registration, clean diffs and absence of conflict
markers; they do not establish Fortran compilation, numerical accuracy, runtime
restart correctness, multimesh/parallel behavior, or physical FS1 validity.
See SOURCE_SYNC.md and `python3 EAE/check_source.py` for reproducible static checks.
