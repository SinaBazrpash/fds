# Output reference

Names below use `<name>` and `<r>` for material and formatted heating rate.
All plots are PNG; temperature axes are °C, conversion is dimensionless. Good
agreement must be judged across rates, residual structure and derivatives, not
only legend R². No plot establishes a unique mechanism or parameter identification.

## Every plot family

| Folder / filename | Axes, curves and interpretation |
|---|---|
|01_QC / `<name>_QC_mass.png`|T°C vs mass%; one measured/cleaned curve per rate. Inspect lag, noise, shoulders, endpoints and residue consistency. A flat tail alone cannot prove all chemistry finished.|
|01_QC / `<name>_QC_alpha.png`|T°C vs endpoint-normalized alpha, one curve per rate. Endpoint1 is imposed by normalization, not predicted complete burnout. Compare shape/rate shifts and common T range.|
|02_DAEM_Fitting / `<name>_alpha_exp_DAEM_<r>Kmin.png`|T°C vs alpha; experiment and individual direct DAEM, own-rate R². Local agreement says nothing about rate transfer.|
|02_DAEM_Fitting / `<name>_comparison_<r>Kmin.png`|T°C vs alpha; experiment, own-rate, reference-transfer and global direct predictions. Transfer/global mismatch reveals cross-rate inconsistency, not uniquely its cause.|
|02_DAEM_Fitting / `<name>_GLOBAL_all_rates.png`|T°C vs alpha; measured and global curves for every rate. One common distribution should explain rate shifts; overloaded curves can hide local errors.|
|02_DAEM_Fitting / `<name>_<r>_alpha.png`|T°C vs alpha; experiment and direct individual/reference/global DAEM with R² legends. Numerical duplicate of the comparison purpose, retained for compatibility.|
|02_DAEM_Fitting / `<name>_<r>_dalpha_dT.png`|T°C vs dα/dT in1/K; raw measured numerical gradient and **analytic** direct DAEM derivatives for three methods. Inspect peaks, shoulders and tails. Raw noise may lower R²; this differs from the smoothed derivative used in fitting/quality summary.|
|03_Eeff_A_Reconstruction / `<name>_<r>_alpha.png`|T°C vs alpha; experiment and independently integrated Eeff(T)/A/f ODE predictions for all three methods. Close reconstruction checks the representation/interpolation, not an independent kinetic mechanism.|
|03_Eeff_A_Reconstruction / `<name>_<r>_dalpha_dT.png`|T°C vs1/K; raw measured gradient and reconstructed ODE derivatives. Compare with direct derivatives; interpolation or ODE error may cause differences.|
|04_Energy_Distributions / `<name>_Ea_PDF_<r>Kmin.png`|Ea kJ/mol vs density in (kJ/mol)⁻¹; weighted individual Gaussian components and their sum for each own-rate fit. Curves show the underlying Gaussian mixture over finite support **before quadrature renormalization**; fitted bin weights are renormalized over50..450kJ/mol. Peaks are fitted populations, not uniquely identified reactions. Broad/truncated/overlapping components may be nonidentifiable. No separate global-PDF PNG is generated; global components are in Excel.|
|05_Eeff / `<name>_Eeff_<r>Kmin.png`|T°C vs effective energy kJ/mol for the individual fit. Survival weighting changes it along a heating history; it is not the Gaussian mean or necessarily a single material constant. Legacy numerically stabilized evaluation may differ at nearly exhausted tails.|
|05_Eeff / `<name>_<r>_Eeff_three_methods.png`|T°C vs effective energy kJ/mol; individual/reference/global curves, each evaluated at target rate. Divergence can reflect different fitted distributions/survival histories. Do not use these as a replacement constant E in FDS.|
|06_f_alpha / `<name>_<r>_f_alpha.png`|alpha vs dimensionless f; individual/reference/global exact DAEM identity1−alpha. Coincident curves are mathematically expected under the chosen Eeff definition; they do not independently demonstrate universal reaction order.|
|06_f_alpha / `<name>_global_f_all_rates.png`|alpha vs global f for all rates. Same identity means curves overlap; this is not independent evidence for a unique global kinetic law.|

No plots are intended directly in `Plots` or its parent. The preflight PNG is
removed after checking; it is not a scientific output. Plot comparisons use raw
measured gradients; derivative fit-quality columns use the smoothed nonnegative
reference. Celsius increments and Kelvin increments are equal, but exponentials
always use absolute K. Multiply dα/dT by beta(K/s) for dα/dt(s⁻¹).

## Every Excel worksheet and column group

Workbook: `Excel/<name>_DAEM_results.xlsx`. Rate labels are unique; names are
truncated to Excel's31-character limit. Duplicate formatted rates are rejected
before fitting, preventing rate-sheet/output overwrite. No workbook content
has been newly runtime-tested during this migration.

| Sheet | Important columns and meaning |
|---|---|
|Summary|Sample, HeatingRate_Kmin, Tmin_C/Tmax_C, EndpointResidualMass_pct, alpha_at_endpoint; A_DAEM_s_inv, Ea_mean_kJmol, K_best describe **individual** fits. RSS is the joint objective, BIC uses alpha-only residuals. R2_alpha and smoothed derivative R²/RMSE, Peak_T_error_K and Peak_height_relative_error summarize own-rate agreement.|
|Range_Plateau_QC|HeatingRate_Kmin, Tmin_C, Tmax_C, N_points; TerminalPlateauDetected, TerminalMassMedian_pct, TerminalSlope_pct_per_C and TerminalMassSpan_pct. Median is a QC diagnostic; it is **not** the endpoint mass used for normalization.|
|Method_Metadata|CommonOverlap_Tmin_C/Tmax_C; EndpointResidualMass_pct dictionary and explicit Normalization text. Overlap flags interpretation only; fits use complete per-rate measured curves.|
|PDF_Parameters|Sample, HeatingRate_Kmin, Component, mu_kJmol, sigma_kJmol, weight_pi for individual mixtures. Components are reported in sorted-mean order with original component IDs.|
|Reference_Transfer|Sample, ReferenceRate_Kmin, TargetRate_Kmin; R2_reference_transfer, RMSE_reference_transfer and RSS_reference_transfer are **alpha-only** transfer metrics with no target refit.|
|Global_Summary|Sample; A_global_s_inv(s⁻¹); Ea_mean_global_kJmol=sum(pi*mu) of underlying Gaussian components, not survival Eeff nor exactly truncated-quadrature mean; K_best_global(component count); RSS_global_equal_rate(legacy name for full joint objective); BIC_global(alpha-only selection score); RSS_alpha_global_unweighted(separate raw alpha RSS).|
|Global_Fit_Quality|Sample, HeatingRate_Kmin; R2_global, RMSE_global, RSS_global_rate are alpha-only per-rate quality; smoothed derivative R²/RMSE(1/K), peak temperature error K and relative peak-height error assess shape.|
|Global_PDF_Parameters|Sample, Component, mu_kJmol, sigma_kJmol, weight_pi for the **one shared global mixture**. Rows match component IDs, not necessarily sorted energies. Use these rows, not the per-rate PDF rows, for global FDS mapping.|
|Fit_<r>Kmin|T_K/T_C, in_common_T_overlap; alpha_exp, alpha_DAEM_own, alpha_reference_transfer, alpha_DAEM_global; dalpha_dT_* are **numerical gradients** on this measured grid in1/K, not necessarily analytic DAEM derivatives; Eeff_kJmol_own is the legacy own-rate Eeff diagnostic.|
|f_alpha_<r>Kmin|alpha and f_DAEM from the legacy individual binned/trimmed/smoothed and physically rescaled **numerical-gradient** procedure, interpolated/extrapolated onto0.005..0.995. It can differ from the exact identity tables/plots. An empty core uses a warned unit-shape fallback, not identified kinetics. Do not export this as a new FDS reaction-order law.|
|Kinetics_<r>Kmin|T_K,T_C,alpha_exp,dalpha_dT_exp(raw gradient). For individual/reference/global: alpha_*, deriv_*(analytic1/K), Eeff_*(kJ/mol), f_*(dimensionless survival), alpha_recon_* and deriv_recon_*(ODE1/K). R2_alpha_DAEM_*, R2_deriv_DAEM_*, R2_alpha_recon_* and R2_deriv_recon_* repeat scalar metrics in every row; these derivative R² values compare against the **raw** gradient. A is in Summary/Global_Summary (reference A is the selected individual Summary row), not a separate Kinetics column.|
|f_all_<r>Kmin|alpha common grid0.005..0.995; f_individual,f_reference,f_global all equal1−alpha by the exact selected Eeff identity. This intentionally differs from the legacy f_alpha sheet.|
|Scientific_Definitions|Sample, ReferenceRate_Kmin; Eeff_definition, f_alpha_exact, Reconstruction, Global_fit_objective, Legacy_RSS_label, Model_selection, Derivative_conventions, PDF_support_kJmol, Quadrature_nodes, R2_derivative and Checkpoint_key. The explicit derivative conventions distinguish summary versus raw-gradient tables.|

R²=1−RSS/max(sum((y−mean(y))²),epsilon); it can be negative and is misleading
for almost-flat data. RMSE is in the dependent variable's units. RSS grows with
point count; the optimized global objective balances per-rate mean residuals and
scaled derivative penalties. Neither BIC nor R² measures physical parameter uniqueness.

## Scientific definitions and export cautions

`Eeff=-R*T*ln[integral(w*S*exp(-E/RT))/integral(w*S)]` with R8.314462618J/mol/K.
It depends on T, rate and survival. `f=(dα/dt)/(A exp(-Eeff/RT))=1−α_model`
under this definition. Reconstruction uses the fitted constant A and interpolated
Eeff(T) plus corresponding f(alpha), DOP853 with rtol1e-8/atol1e-10. It is a
representation consistency exercise, not a new independent experiment.

`K_best_global` is a number of Gaussians, **not** quadrature nodes, reaction order
or number of independently identified chemical steps. Gaussian widths are standard
deviations, not variance or FWHM; pi are nonnegative dimensionless mixture weights.
Bounds/truncation and nonunique mixture decompositions require sensitivity checks
outside this publication. [FDS mapping](EAE_FDS_WORKFLOW.md) explains the supported
finite-bin first-order interface and the inputs that TGA fitting cannot supply.
