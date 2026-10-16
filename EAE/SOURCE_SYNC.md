# Source synchronization review

Upstream baseline: `b2bd16808fa3c76466b4a5eb83335575b611abf1` (firemodels/fds master).
Previous fork master: `ca87cd08a1d8be60119d94287676256b3f5d1df7`.
Verified GitHub recovery branch: `backup/pre-eae-master-20261016-1019`.
Observed fork divergence: 25 ahead / 359 behind.

No old fork-specific commit is merged. The new commit has only the fetched upstream master as its parent. All original upstream Fortran files in the isolated snapshot match this upstream revision; a narrowly scoped patch was applied, not replacement of the upstream tree. CMake edits preserve the other upstream settings. Makefile receives the new module and explicit Unix/Windows dependencies; its target names remain and executable basenames are distinct.

## Transfer inventory

| File | Included changes | SHA-256 |
|---|---|---|
| Source/eae.f90 | Gaussian quadrature/mixture weights; constant and linear-temperature survival integration; diagnostics | 5a838804da7134a505436c83a48dbe3c02b1e0949dbd86e09744517352777906 |
| Source/cons.f90 | TGA request and prescribed/linear temperature controls | c6d52e2144c273ec55e57aabd0779a55327c550b99935ba6a14097ea94bc1cc2 |
| Source/data.f90 | EAE diagnostic registration | 80192d3e26638f61e0089e8508c5c6253641690fd765e9b1bbfca1d0fa717f49 |
| Source/dump.f90 | restart format identity/version checks and EAE diagnostic evaluation | af2aa201a0f6de4011018a64cdcddc466fc5d7502ebe203201a1f76395280a5d |
| Source/func.f90 | virgin bin/reference initialization and storage packing/unpacking | 20be06896b018cc492a20f6115e6077fb902abfc3fde2d32b45934c0c8fd56ba |
| Source/read.f90 | MATL EAE API, validation, geometry restrictions and TGA parsing/guards | 4f1cbcd40afea3cc5a435a8b7feac5370b082484c7c19f2a0d5b54a779e5b452 |
| Source/type.f90 | persistent configuration and per-material bin/reference/trial state | 2c80aa7b50dc9926613892f8621eea2d4f067cc2b42dbd23a32263ba07eeb69a |
| Source/wall.f90 | accepted depletion, conservative remap, forced-layer cap fix, TGA integration and char-inclusive total mass | 15f4b9f83d59f01aefd695b5cd2895acd5f7bc892fb8333c1457f3f6d98d3646 |

All eight Fortran files are byte-identical to the isolated implementation whose SHA manifest is recorded above. Additional changes: CMakeLists.txt; Build/makefile; EAE/README.md; EAE/check_source.py; three examples. Existing copyright and license notices are preserved.

## Static review

- PASS: original upstream Fortran baseline equality and exact transfer of all eight EAE files.
- PASS: EAE module listed in both build systems; .o/.obj dependencies registered.
- PASS: source feature markers and acyclic internal module graph.
- PASS: git diff --check and unresolved-conflict scan.
- PASS: staged file allowlist excludes binaries, DLLs, objects, outputs, workbooks and machine-specific paths.
- NOT VERIFIED: compilation or runtime compatibility with current upstream. No build/configure, simulation, or numerical/runtime test was run during synchronization.
- NOT VERIFIED: compiler/platform matrix, MPI/OpenMP behavior, numerical correctness and physical validation of FS1 examples.

The prior isolated implementation has known restrictions: planar1-D surfaces; one EAE reaction per material; unsupported particles/immersed paths rejected; no TGA restart. Its prior ordinary restart was numerically close but not bitwise identical, and TGA remesh/parallel coverage was incomplete. Transferring the source does not resolve those limitations. All source-validation scripts here are static only. Experimental data and previously generated validation artifacts are intentionally excluded.

The isolated project and existing FDS installations are read-only inputs throughout this synchronization. Audit manifests and Git operations live only in the separate publication workspace.
