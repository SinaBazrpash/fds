# FDS_EAE: optional1D distributed activation-energy kinetics

Native FDS physics/heat transfer/CFD/governing equations remain the scientific
foundation. This branch integrates opt-in1D EAE into the existing native Fortran
modules and provides the interactive Python analysis workflow.
**The new refactor is statically reviewed, not compiled or numerically verified.**
The installed local executable is unchanged.

| Branch | Purpose |
|---|---|
|[master](https://github.com/SinaBazrpash/fds/tree/master)|1D EAE in existing33native source units; Python workflow/docs; zero EAE object additions|
|[EAE_1D_MAKE](https://github.com/SinaBazrpash/fds/tree/EAE_1D_MAKE)|Frozen original master2f2733a84013faeeb6d705246b61678848f44ef5, original separate EAE module/build structure|
|[EAE_3D_MAKE](https://github.com/SinaBazrpash/fds/tree/EAE_3D_MAKE)|Exact verified installed source, optional fixed-volume EAE+HT3D, supported1D, MIN_LAYER_MASS correction, required extra units|

No new native LTE/pore network/Darcy/diffusion/port/total-energy physics is enabled.
3D has dormant operator modules only to preserve exact installed provenance.
No EAE HT3D recession/BURN_AWAY support is claimed.

Start here:

- [Python installation, data format, fitting and logging](docs/EAE_PYTHON_GUIDE.md)
- [Actual Python-global-output to FDS namelist mapping](docs/EAE_FDS_WORKFLOW.md)
- [Every plot and Excel worksheet](docs/EAE_OUTPUT_REFERENCE.md)
- [Refactor changes, static checks and evidence limitations](docs/EAE_REFACTOR_REVIEW.md)
- [Existing EAE model/TGA detail](EAE/README.md)

```sh
python -m pip install -r requirements-eae.txt
python eae.py
```

Use a virtual environment as described in the guide. FDS does not read the Excel
output directly. Follow the verified parser-field mapping; material yields and
thermal properties require independent physical inputs. Illustrative data and1D
namelist are under `EAE/examples`; no new example/fitting runs were performed.
Native Make/CMake files have no EAE registrations; use a fresh build directory and
retain existing compiler/MPI/library prerequisites. Do not replace installed
binaries on the strength of static checks.

The original FDS introduction and links are preserved below.

---

## Fire Dynamics Simulator and Smokeview

*Continuous Integration. Continuous Improvement.*

Fire Dynamics Simulator ([FDS](https://github.com/firemodels/fds)) is a large-eddy simulation (LES) code for low-speed flows, with an emphasis on smoke and heat transport from fires.

Smokeview ([SMV](https://github.com/firemodels/smv)) is a visualization program used to display the output of FDS and [CFAST](https://github.com/firemodels/cfast) simulations.

For more information, including a link to our discussion forum, please visit the [FDS-SMV website](https://pages.nist.gov/fds-smv/).

Here is a link to our [Firebot Build Status](https://pages.nist.gov/fds-smv/firebot_status.html).

Here is a link to [contributing](https://github.com/firemodels/fds/blob/master/CONTRIBUTING.md) to the FDS and Smokeview project.

Here are some other useful links:

[FDS-SMV Downloads (includes Release Documentation)](https://github.com/firemodels/fds/releases)

[Smokeview Downloads](https://github.com/firemodels/smv/releases)

[Discussions](https://github.com/firemodels/fds/discussions)

[FDS Issues](https://github.com/firemodels/fds/issues)

[Smokeview Issues](https://github.com/firemodels/smv/issues)

[Nightly Builds (includes Documentation)](https://github.com/firemodels/test_bundles/releases/tag/FDS_TEST)

Pull requests welcome!

