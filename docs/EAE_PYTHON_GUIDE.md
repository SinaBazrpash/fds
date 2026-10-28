# Python EAE/DAEM analysis guide

## Scope and validation status

`eae.py` analyzes thermogravimetric mass curves under constant heating rates.
It fits a distributed activation energy model (DAEM): independent first-order
populations share one pre-exponential factor A, with a finite-range normalized
Gaussian-mixture activation-energy distribution. EAE denotes the survival-weighted
effective activation energy diagnostic. Neither a good fit nor a large R² proves
unique physical parameters, a unique reaction mechanism, or predictive validity
outside the calibrated thermal histories.

The supplied program was inspected and corrected for routing, logging, validation,
checkpoint identity and objective reporting. Only `compile(source, ..., 'exec')`
and static inspection were performed during this migration: **no imports, fitting,
Excel/plot execution or synthetic end-to-end run**. No runtime-supported Python/
package/platform matrix is newly established. The equations, constants, quadrature,
optimizers, objective, bounds, number of starts and selection method are retained.
See [static review](EAE_REFACTOR_REVIEW.md) and [output reference](EAE_OUTPUT_REFERENCE.md).

## Installation and running (commands for the user, not executed here)

Use a Python installation with NumPy, SciPy, pandas, matplotlib and openpyxl;
xlrd is needed for old `.xls`. Tkinter is optional for graphical path selection;
console path entry is the fallback. Python3.11/3.12 is a reasonable starting
choice, **not a tested support guarantee**. Use compatible current package releases.

```sh
python -m venv .venv
# Windows CMD:
.venv\Scripts\activate
# Linux/macOS instead: source .venv/bin/activate
python -m pip install -r requirements-eae.txt
python eae.py
```

Run interactively in a console. Select a parent output directory, number of
materials, a safe single-directory material name (defaultFS1,FS2,...), number
of rates, distinct rates in column order, then the CSV/Excel input. Choose one
**measured** reference rate (10K/min if present, otherwise first rate).
Review the final batch summary and answer `y` to start. Setup collects all choices;
after confirmation the run needs no prompts. It can be expensive: K1..15,
six starts per K, individual and global optimizations, up to800 function evaluations.
Do not interpret console “completed” as proof of optimizer convergence/identifiability;
inspect warnings, bound contacts, residuals, transferred predictions and the log.

## Input format and QC

Use the first Excel worksheet or a comma-separated CSV. Columns alternate
`T_rate1,Mass_rate1,T_rate2,Mass_rate2,...`; temperature is **°C**, mass is **%**,
rates are **K/min**, entered manually in column order. Optional text headers become
NaN and are dropped as paired nonnumeric rows. Blank tails permit unequal lengths.
At least five finite, distinct-temperature pairs per rate and a nonempty common
T overlap are required. Data are sorted by temperature; repeated temperatures
are merged by arithmetic mean mass. Absolute-zero-or-lower temperatures and
negative masses are rejected; masses above100% generate a warning. These checks
cannot detect swapped columns, wrong rate labels, buoyancy artifacts or wrong units.

Example (illustrative, not measurements or fitted reference):

```csv
T_5_C,Mass_5_pct,T_10_C,Mass_10_pct,T_40_C,Mass_40_pct
30,100,30,100,30,100
150,99,150,99.5,150,99.8
250,94,250,97,250,99
350,65,350,75,350,88
450,33,450,40,450,58
550,21,550,23,550,31
650,20,650,20,650,21
750,20,750,20,750,20
```

See [the small input file](../EAE/examples/illustrative_rates.csv). It illustrates
layout only; smooth/identifiable fits and plateau detection are not promised.
Duplicate rates are rejected (including distinct values colliding in formatted
filenames). Combine or analyze experimental replicates explicitly; do not assign
them fictitious heating rates. Material names cannot contain paths, Windows device
names or unsafe characters; case-insensitive duplicates in a batch are rejected.

Normalization is **per rate**: `alpha=(m_initial-m)/(m_initial-m_final_measured)`,
clipped to[0,1] as in the supplied program (overshoot is now warned).
Final mass must be below initial mass. The final measured point maps to alpha1
by definition, even if decomposition would continue. A terminal plateau check
uses the last max(8,ceil(10%N)) points, at least10°C span, slope<=0.02 percentage
points/°C and mass span<=1 percentage point. It is a QC indicator, **not proof of
complete conversion or a universal char yield**. Per-rate own/global fits use full
measured ranges; the common overlap flag limits comparative interpretation, not fitting.

## Three analyses

1. **Individual**: optimize separate A/distribution for each rate. A strong own-rate
   fit can conceal poor transferability or overparameterization.
2. **Reference transfer**: use one measured rate's fitted A/distribution unchanged
   at each target rate, evaluating at the target beta. No transfer refit occurs.
3. **Global**: optimize one A/distribution simultaneously across all rates. Failure
   to reproduce all curves may indicate model inadequacy, rate/temperature errors,
   thermal lag, endpoint normalization differences or optimization limitations.

Internal beta=rate/60 K/s; T=°C+273.15 K; E is J/mol in exponentials.
For bins `S(E,T)=exp[-(A/beta)*integral(T0..T) exp(-E/(RT'))dT']` and
`alpha=1-integral w(E) S(E,T)dE`. Fresh modeled populations are defined at
**each measured starting T0**; previous reaction before T0 is not inferred.
Finite support50..450kJ/mol is normalized by180-point Gauss–Legendre quadrature.
Temperature hazard integration uses12-point Gauss–Legendre quadrature with<=2K
segments. Bounds: A1e7..1e15s⁻¹, means80..400kJ/mol, widths2..200kJ/mol,
softmax weights. Candidate starts with weights<0.005 are filtered; the legacy
fallback does not apply that filter. Nonconverged optimizers can still supply a
candidate, as before, but now generate explicit warnings. Component labels are
exchangeable; reported means need not be sorted.

## Actual objective and model selection

For each rate r let n be its point count, d the analytic model dα/dT, d_ref the
smoothed/nonnegative experimental derivative, s=max(q95(d_ref),1e-5), and
c=max(3max(first min(12,n) d_ref),0.025s,1e-6). The minimized objective is:

`J = sum_rates [sum((alpha_model-alpha_exp)^2)/n
 + 0.03*sum((d-d_ref)^2)/(n*s^2)
 + 5*max(d(T0)-c,0)^2/s^2]`.

It is **not** only an alpha RSS, nor a time-derivative objective. The workbook's
legacy `RSS_global_equal_rate` field stores J; it is retained for compatibility.
`RSS_alpha_global_unweighted` now separately reports the raw summed alpha RSS.
BIC uses **unweighted alpha RSS**, total alpha point count and3K parameters;
K is selected by this BIC, not by minimizing J across K. Smoothed derivatives,
endpoint normalization and correlated data make BIC descriptive rather than a
proof of correct model order. Reaching a parameter bound, different local minima,
or near-identical predictions from different mixtures limits interpretation.

## Output, logging and checkpoints

```text
<parent>/<material>/
  setup_manifest.json           # input hash/rates/program identity
  run_manifest.json             # reference, endpoints and runtime versions
  Excel/<material>_DAEM_results.xlsx
  Plots/
    01_QC/
    02_DAEM_Fitting/
    03_Eeff_A_Reconstruction/
    04_Energy_Distributions/
    05_Eeff/
    06_f_alpha/
  Checkpoints/<identity>_<kind>[_rate_<rate>]_K<nn>.npz
  Logs/execution.log
```

The log appends UTC setup/run start/completion or failure/interruption, input
path/full SHA256, paired-row/duplicate-temperature QC, rates/units/reference,
endpoint masses, numerical settings/bounds, selected parameters, optimizer
warnings, tracebacks and output paths, while retaining stdout/stderr console output.
An OS crash/power loss may omit the final status line. A rejected unrelated output
folder is reported on the console without writing into that folder.

The program refuses existing directories without matching setup identity and
refuses changed run identity (including code, data, reference and runtime versions).
Use a new parent/name after changes. An identical rerun may reuse checkpoints and
replace its own same-identity output workbook/plots; it appends its log.
Checkpoints are optimizer-result caches, not full simulation states. They use
non-pickled NPZ, finite/shape checks, full data/code/settings/rate identity and
atomic replacement. They do not prove that the cached optimizer converged or
found a unique minimum. Do not edit caches or use untrusted files.

Before fitting, preflight writes/reopens temporary Excel, PNG and NPZ files in
category folders. Workbook replacement is atomic after basic sheet checks. Plot
figures close in `finally`, even on errors; a guard rejects uncategorized plot paths.
A per-material failure preserves its log/partial evidence and the batch continues.
Only a runtime run can establish actual Excel/GUI/renderer compatibility.
