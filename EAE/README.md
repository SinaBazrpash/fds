# Fixed-volume native EAE+HT3D — EAE_3D_MAKE

This branch publishes the **exact41-source installed snapshot** identified by
[the provenance manifest](../docs/EAE_3D_SOURCE_PROVENANCE.json) and
[the existing installation report](../docs/LOCAL_INTEGRATION_20261028.md).
Installed executable SHA256:
`d17146541174acaf32b5c1aa09346e70ed188ac849dae7e6875ecb4c401349e2`.
No executable is shipped or changed by this publication.

Optional1D EAE remains available. Fixed-volume3D uses explicit SURF
`HT3D=T,EAE_HT3D=T`; it does not activate on ordinary FDS inputs.
Material Gaussian-mixture parameters use the same MATL interface as1D.
Preserve native heat conduction, gas/source conventions and governing equations.
The tested MIN_LAYER_MASS initialization and restart-v2 corrections are included.
Ordinary native layer-removal rules remain; coupled EAE+HT3D requires zero
minimum layer mass fraction/thickness, a persistent inert residue matrix,
no shrink/swell, no linings/variable thickness, Cartesian cell-aligned nodes,
exposed backing and normalized positive directional weights. Review coupled.f90
for all gates. No recession, BURN_AWAY, reactive EAE residue or arbitrary
moving geometry is certified.

Dormant eae_remap/eae_swept/eae_pore/eae_pore_network/eae_retained/
eae_pore_checkpoint modules are deliberately retained for exact provenance.
They are compiled standalone operators, **not active native LTE, pore storage,
Darcy/diffusion, pressure/port or total-energy extensions**. There are no native
LTE/port input flags in this snapshot. SOURCE23 is excluded. Presence of operators
does not qualify native geometry, fluid energy, MPI or restart for those operators.
Do not resume their development as part of this final scientific scope.

Build registration is the exact installed-source CMake/Makefile structure,
including required extra modules. Existing Build target names apply; for example,
from a fresh build directory below Build, `make -f ../makefile ompi_gnu_linux`
requires the pre-existing supported MPI/compiler/optional-library setup. See Build
scripts and CMake presets for platform-specific requirements. The recorded local
build used ifx2026.1, MSVC2022, IntelMPI2021.18, bounds checks and a private MPI
import library. Alternate Make/CMake builds were not newly built or validated.

Historical scope, finite-step mass residuals, incomplete full CFD energy closure,
shared-upstream findings and restart/MPI restrictions remain exactly as documented.
The publication performs no builds/simulations and makes no broader claims.

## Runnable historical reference and Python mapping

[EAE/examples/fixed_volume_native_reference.fds](examples/fixed_volume_native_reference.fds)
is the exact previously executed native fixed_gas input, copied without rerunning.
Its Gaussian mixture/32-node quadrature is a numerical reference, **not** the
Python program's fitted50..450kJ/mol180-node model. Do not silently substitute
its parameters for a fitted material. Native output is CHID-based; run in a fresh
output directory with an appropriately built executable. The source SHA matches
the existing installed validation; alternate platform builds remain unverified.

See the [master Python-to-FDS guide](https://github.com/SinaBazrpash/fds/blob/master/docs/EAE_FDS_WORKFLOW.md)
for actual input keyword mapping and [Python/output documentation](https://github.com/SinaBazrpash/fds/blob/master/docs/EAE_PYTHON_GUIDE.md).
The same Gaussian MATL fields apply on this branch; no LTE/pore/port fields are
needed or supported. The [historical build manifest](../docs/EAE_3D_HISTORICAL_BUILD.json)
records exact source hashes, compile order/flags and private MPI link-input hashes.
It is historical evidence, not a newly executed build.
