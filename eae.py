"""Interactive DAEM analysis converted from the supplied MATLAB workflow.

Input workbook layout for N heating rates:
    [T_rate1, Mass_rate1, T_rate2, Mass_rate2, ...]
Temperature: degC; Mass: percent.

Dependencies:
    numpy pandas scipy matplotlib openpyxl
Optional GUI file/folder dialogs use tkinter (standard with many Python installs).
"""
from __future__ import annotations
import math, time, warnings, os, hashlib, json, traceback, sys
from contextlib import contextmanager, redirect_stdout, redirect_stderr
from datetime import datetime, timezone
from importlib.metadata import version
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.integrate import cumulative_trapezoid, solve_ivp
from scipy.interpolate import PchipInterpolator, interp1d
from scipy.optimize import least_squares, minimize
from scipy.special import roots_legendre, softmax
from scipy.signal import savgol_filter

R = 8.314462618
EMIN, EMAX, NE = 50e3, 450e3, 180
KMAX, NSTARTS = 15, 6
ALPHA_MIN, ALPHA_MAX, DERIV_THR = 0.005, 0.995, 0.002
NBINS, MIN_PER_BIN, TRIM_FRAC = 100, 3, 0.02
EPSF, EPSE = 1e-12, 1e3
RNG_SEED = 1
# Fit-quality controls; original K range, mass normalization, Eeff/f and outputs retained.
FIT_VERSION = 'joint_rate_gauss_v3_20261012'
DERIVATIVE_WEIGHT = 0.03
INITIAL_RATE_PENALTY = 5.0
QUAD_ORDER = 12
MAX_QUAD_STEP_K = 2.0
A_UPPER_WARNING_FRACTION = 0.999

# Exact-speed settings: optimization tolerances/grid are unchanged. Parallelism only
# changes wall-clock execution, not the objective/model used for final selection.
MAX_WORKERS = max(1, min(NSTARTS, (os.cpu_count() or 2)))




# Checkpoint identity includes source data, rate and numerical settings.
CHECKPOINT_DIR = None
CHECKPOINT_TAG = None

def file_digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

PLOT_CATEGORIES = ('01_QC', '02_DAEM_Fitting', '03_Eeff_A_Reconstruction',
                   '04_Energy_Distributions', '05_Eeff', '06_f_alpha')
GLOBAL_OBJECTIVE = ('Sum over rates of mean squared alpha residual + '
                    '0.03 * mean squared derivative residual / derivative_scale^2 + '
                    '5 * positive initial-rate excess^2 / derivative_scale^2; '
                    'derivatives in 1/K; scale=max(95th percentile smoothed derivative,1e-5)')

class ConsoleAndLog:
    """Keep console output while persisting stdout/stderr, including tracebacks."""
    def __init__(self, console, log):
        self.console, self.log = console, log
    def write(self, text):
        self.console.write(text)
        self.log.write(text)
        self.log.flush()
        return len(text)
    def flush(self):
        self.console.flush()
        self.log.flush()

@contextmanager
def material_log(base, name, stage):
    directory = base / name / 'Logs'
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'execution.log').open('a', encoding='utf-8') as log:
        with redirect_stdout(ConsoleAndLog(sys.stdout, log)), redirect_stderr(ConsoleAndLog(sys.stderr, log)):
            print(f'\n[{datetime.now(timezone.utc).isoformat()}] {stage} START: {name}', flush=True)
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter('always')
                    yield
            except BaseException:
                traceback.print_exc()
                print(f'{stage} FAILED or interrupted: {name}', flush=True)
                raise
            else:
                print(f'{stage} COMPLETED: {name}', flush=True)

def validate_rates(rates):
    if not rates or not all(np.isfinite(x) and x > 0 for x in rates):
        raise ValueError('Heating rates must be finite positive K/min values.')
    if len(set(rates)) != len(rates):
        raise ValueError('Duplicate heating rates would overwrite fits; combine replicates explicitly first.')
    if len({f'{r:g}' for r in rates}) != len(rates):
        raise ValueError('Heating rates collide in output labels; choose distinct representable rate labels.')

def validate_material_name(name):
    if (not name or name in ('.', '..') or name[-1] in '. ' or
            any(c in '<>:"/\\|?*' or ord(c) < 32 for c in name) or
            name.split('.')[0].upper() in {'CON','PRN','AUX','NUL',
                                         *(f'COM{i}' for i in range(1,10)),
                                         *(f'LPT{i}' for i in range(1,10))}):
        raise ValueError('Material name must be a safe single directory name (Windows compatible).')

def run_identity(job):
    return {'input_sha256': file_digest(job['path']), 'rates_Kmin': job['rates'],
            'reference_rate_Kmin': job['reference_rate'],
            'endpoint_residual_masses_pct': job['residual_masses'],
            'program_sha256': file_digest(Path(__file__)), 'fit_version': FIT_VERSION,
            'numpy': np.__version__, 'scipy': version('scipy'), 'pandas': pd.__version__}

def reserve_material_output(base, name, path, rates):
    """Reserve only an input/program-identical directory before logging SETUP."""
    directory=base/name
    marker=directory/'setup_manifest.json'
    expected={'input_sha256':file_digest(path),'rates_Kmin':rates,
              'program_sha256':file_digest(Path(__file__))}
    if directory.exists():
        if not marker.is_file() or json.loads(marker.read_text(encoding='utf-8')) != expected:
            raise ValueError(f'{directory}: unrelated/changed output directory; choose a new parent/name.')
    else:
        directory.mkdir(parents=True)
        temp=marker.with_suffix('.tmp')
        temp.write_text(json.dumps(expected,indent=2)+'\n',encoding='utf-8')
        os.replace(temp,marker)
    return expected['input_sha256']

def prepare_material_output(base, job):
    """Same-identity resume only; never overwrite another run's results."""
    if file_digest(job['path']) != job['input_sha256']:
        raise ValueError('Input changed after SETUP; restart setup with a new output directory.')
    directory=base/job['name']; marker=directory/'run_manifest.json'
    expected=json.loads(json.dumps(run_identity(job)))
    if marker.exists() and json.loads(marker.read_text(encoding='utf-8')) != expected:
        raise ValueError(f'{directory}: changed run settings; choose a new parent/name.')
    if not marker.exists():
        temporary=marker.with_suffix('.tmp')
        temporary.write_text(json.dumps(expected,indent=2)+'\n',encoding='utf-8')
        os.replace(temporary,marker)
    return directory

def checkpoint_path(kind, rate=None, K=None):
    if CHECKPOINT_DIR is None: return None
    suffix=f'{kind}_rate_{rate:g}' if rate is not None else kind
    if K is not None: suffix+=f'_K{K:02d}'
    return CHECKPOINT_DIR/f'{CHECKPOINT_TAG}_{suffix}.npz'

def checkpoint_fit(path, compute):
    if path is not None and path.exists():
        try:
            with np.load(path,allow_pickle=False) as d:
                rss=float(d['rss']); p=d['p'].copy()
            expected_K=int(path.stem.rsplit('_K',1)[1])
            if p.shape != (3*expected_K,) or rss < 0:
                raise ValueError('Checkpoint parameter shape or objective invalid')
            if np.isfinite(rss) and np.all(np.isfinite(p)):
                print(f'  [checkpoint] loaded {path.name}',flush=True)
                return rss,p
        except Exception as exc: print(f'  [checkpoint] invalid, recomputing: {exc}',flush=True)
    rss,p=compute()
    if path is not None:
        temp=path.with_name(path.name+'.tmp.npz')
        np.savez_compressed(temp,rss=rss,p=p)
        os.replace(temp,path)
    return rss,p

def preflight_output(base,jobs):
    import openpyxl
    for job in jobs:
        mat=base/job['name']
        for sub in ['Excel','Plots/01_QC','Plots/02_DAEM_Fitting','Plots/03_Eeff_A_Reconstruction',
                    'Plots/04_Energy_Distributions','Plots/05_Eeff','Plots/06_f_alpha','Checkpoints','Logs']:
            (mat/sub).mkdir(parents=True,exist_ok=True)
        # Actually write and reopen an Excel file, not just check folder existence.
        dest=mat/'Excel'/'_preflight_test.xlsx'
        with pd.ExcelWriter(dest,engine='openpyxl') as writer:
            pd.DataFrame({'test':[1.25]}).to_excel(writer,sheet_name='Test',index=False)
        book=openpyxl.load_workbook(dest,read_only=True,data_only=True)
        assert book.sheetnames==['Test'] and book['Test']['A2'].value==1.25
        book.close(); dest.unlink()
        png=mat/'Plots'/'01_QC'/'_preflight_test.png'
        save_plot(png,[(np.array([0.,1.]),np.array([0.,1.]),'test','-')],'x','y','Preflight')
        assert png.stat().st_size>1000
        png.unlink()
        cp=mat/'Checkpoints'/'_preflight_test.npz'
        np.savez_compressed(cp, test=np.array([3.]))
        with np.load(cp,allow_pickle=False) as data: assert data['test'][0]==3.
        cp.unlink()
        print(f'  PREFLIGHT PASS: {job["name"]}: Excel / PNG / checkpoints / directories',flush=True)

def daem_kinetics(p,K,T,beta):
    """Rate-specific effective Arrhenius energy and exact DAEM derivative.
    Eeff = -RT ln(weighted survival/Arrhenius ratio), matching the legacy code.
    f(alpha) = (dalpha/dt) / (A exp(-Eeff/RT)), with time in seconds.
    """
    T=np.asarray(T,float)
    logA,_,_,_=parse_params(p,K); A=np.exp(logA)
    w=energy_weights(p,K)*EWEIGHTS
    integ,J=prepare_daem_kernel(T)
    S=np.exp(-(A/beta)*J)
    den=w@S
    num=w@(S*integ)
    ratio=np.maximum(num/np.maximum(den,1e-300),1e-300)
    ee=-R*T*np.log(ratio)
    alpha=np.clip(1-den,0,1-1e-9)
    deriv=(A/beta)*num
    f_exact=np.maximum(den,1e-12)  # Exact DAEM identity under this Eeff definition.
    return alpha,deriv,ee/1000,f_exact

def reconstruct_from_eeff(T,alpha_model,ee_kj,A,beta,f_of_alpha):
    """Integrate d(alpha)/dT=(A/beta) exp(-Eeff(T)/RT) f(alpha).
    Eeff is interpolated only within the measured temperature grid.
    """
    T=np.asarray(T,float)
    efunc=PchipInterpolator(T,np.asarray(ee_kj)*1000,extrapolate=False)
    # Robust monotone alpha->f mapping, with physical boundary behavior.
    aa=np.asarray(alpha_model,float); ff=np.asarray(f_of_alpha,float)
    unique,idx=np.unique(aa,return_index=True)
    if len(unique)<2: raise ValueError('Reconstruction requires at least2 distinct modeled conversion values.')
    f_interp=PchipInterpolator(unique,np.maximum(ff[idx],1e-12),extrapolate=True)
    def ode(t,y):
        a=np.clip(y[0],0,1)
        return [(A/beta)*np.exp(-float(efunc(t))/(R*t))*max(float(f_interp(a)),0)]
    sol=solve_ivp(ode,(float(T[0]),float(T[-1])),[float(aa[0])],t_eval=T,
                  rtol=1e-8,atol=1e-10,method='DOP853')
    if not sol.success: raise RuntimeError(f'Reconstruction ODE failed: {sol.message}')
    ar=np.clip(sol.y[0],0,1)
    dr=(A/beta)*np.exp(-np.asarray(ee_kj)*1000/(R*T))*np.maximum(f_interp(ar),0)
    return ar,dr

def plot_comparison(path,T,exp,individual,reference,global_y,title,ylabel):
    curves=[(T-273.15,exp,'Experimental','-')]
    for name,y,style in [('Individual',individual,'--'),('Reference transfer',reference,':'),('Global',global_y,'-.')]:
        curves.append((T-273.15,y,f'{name} (R²={r2(y,exp):.5f})',style))
    save_plot(path,curves,'Temperature (°C)',ylabel,title)

def safe_excel_export(target,writer_fn):
    """Atomic output; retain first error, verify workbook and required sheets."""
    import openpyxl
    temp=target.with_name(target.stem+'.writing.xlsx')
    try:
        with pd.ExcelWriter(temp,engine='openpyxl') as writer:
            # Avoid openpyxl's 'At least one sheet must be visible' masking
            # the actual DataFrame.to_excel error.
            writer.book.create_sheet('_EXPORT_GUARD')
            writer_fn(writer)
            del writer.book['_EXPORT_GUARD']
        book=openpyxl.load_workbook(temp,read_only=True)
        names=book.sheetnames
        assert 'Summary' in names and 'Global_Summary' in names and len(names)>5, names
        book.close()
        os.replace(temp,target)
    except Exception:
        print('Excel export FAILED. Original traceback follows:',flush=True)
        traceback.print_exc()
        raise

def ask_int(prompt, min_value=1):
    while True:
        try:
            x = int(input(prompt).strip())
            if x >= min_value: return x
        except ValueError: pass
        print(f"Please enter an integer >= {min_value}.")


def ask_rates(n):
    while True:
        s = input(f"Enter {n} heating rates in K/min, in Excel-column order (e.g. 5,10,40): ").strip()
        try:
            r = [float(x.strip()) for x in s.replace(';', ',').split(',') if x.strip()]
            if len(r) == n:
                validate_rates(r)
                return r
        except ValueError: pass
        print(f"Please enter exactly {n} positive numbers.")


def choose_file(title):
    try:
        import tkinter as tk
        from tkinter import filedialog
        root=tk.Tk(); root.withdraw(); root.attributes('-topmost', True)
        p=filedialog.askopenfilename(title=title, filetypes=[('Excel/CSV','*.xlsx *.xls *.csv'),('All files','*.*')])
        root.destroy()
        if p: return Path(p)
    except Exception: pass
    return Path(input(f"{title}\nEnter full file path: ").strip().strip('"'))


def choose_dir(title):
    try:
        import tkinter as tk
        from tkinter import filedialog
        root=tk.Tk(); root.withdraw(); root.attributes('-topmost', True)
        p=filedialog.askdirectory(title=title); root.destroy()
        if p: return Path(p)
    except Exception: pass
    return Path(input(f"{title}\nEnter output folder path: ").strip().strip('"'))


def read_numeric_table(path: Path):
    if path.suffix.lower()=='.csv':
        df=pd.read_csv(path, header=None)
    else:
        df=pd.read_excel(path, header=None)
    # Header/text cells become NaN; numeric rows survive.
    return df.apply(pd.to_numeric, errors='coerce')


def clean_curve(Tc, mass):
    Tc=np.asarray(Tc,float); mass=np.asarray(mass,float)
    good=np.isfinite(Tc)&np.isfinite(mass)
    Tc=Tc[good]; m=mass[good]
    removed = len(good) - int(good.sum())
    if removed: print(f'  QC: dropped {removed} nonnumeric/nonfinite paired rows (including headers).', flush=True)
    if len(Tc)==0: return Tc,m
    if np.any(Tc <= -273.15): raise ValueError('Temperature must exceed absolute zero.')
    if np.any(m < 0): raise ValueError('Mass percentages must be nonnegative.')
    if np.any(m > 100): warnings.warn('Mass above100%; check baseline, buoyancy and units.')
    order=np.argsort(Tc,kind='mergesort'); Tc=Tc[order]; m=m[order]
    # Combine repeated temperatures, preserving the original mass-vs-temperature data.
    unique,inv,counts=np.unique(Tc,return_inverse=True,return_counts=True)
    if len(unique)!=len(Tc):
        print(f'  QC: merged {len(Tc)-len(unique)} repeated temperature rows.',flush=True)
        m=np.bincount(inv,weights=m)/counts
        Tc=unique
    if len(Tc)>1 and np.any(np.diff(Tc)<=0):
        raise ValueError('Temperature must be strictly increasing after QC.')
    return Tc,m


def terminal_plateau(Tc,m,frac=0.10,min_points=8,slope_thr=0.02,span_thr=1.0):
    """Conservative terminal plateau test.
    slope_thr: max |dMass/dT| in %/degC; span_thr: max mass span in terminal window (% points).
    """
    if len(Tc)<min_points: return False,np.nan,np.nan,np.nan
    n=max(min_points,int(np.ceil(frac*len(Tc)))); tt=Tc[-n:]; mm=m[-n:]
    if np.ptp(tt)<10: return False,float(np.median(mm)),np.nan,float(np.ptp(mm))
    slope=float(np.polyfit(tt,mm,1)[0]); span=float(np.ptp(mm)); mf=float(np.median(mm))
    return (abs(slope)<=slope_thr and span<=span_thr),mf,slope,span


def mass_to_alpha(Tc,mass,mf):
    Tc,m=clean_curve(Tc,mass); T=Tc+273.15
    if len(T)==0: return T,np.array([])
    denom=m[0]-mf
    if not np.isfinite(denom) or denom<=0: raise ValueError('Final residual mass must be below initial mass.')
    a=(m[0]-m)/denom
    # Measured endpoint maps to1 by definition, even if conversion is physically incomplete.
    if np.any((a<0)|(a>1)):
        warnings.warn('Measured conversion outside[0,1] is clipped by the established normalization; inspect QC.')
    a=np.clip(a,0,1)
    return T,a


def normpdf(E,mu,sg): return np.exp(-0.5*((E-mu)/sg)**2)/(sg*np.sqrt(2*np.pi))


def gauss_legendre(a,b,n):
    x,w=roots_legendre(n); return (a*(1-x)+b*(1+x))/2, w*(b-a)/2

ENODES,EWEIGHTS=gauss_legendre(EMIN,EMAX,NE)


def parse_params(p,K):
    logA=p[0]; mus=[]; sigs=[]; j=1
    for _ in range(K):
        mus.append(p[j]); sigs.append(np.exp(p[j+1])); j+=2
    z=np.r_[p[j:],0.0]; pis=softmax(z)
    return logA,np.array(mus),np.array(sigs),pis


def energy_weights(p,K):
    _,mus,sigs,pis=parse_params(p,K)
    w=np.zeros_like(ENODES)
    for mu,sg,pi in zip(mus,sigs,pis): w += pi*normpdf(ENODES,mu*1e3,sg*1e3)
    normalizer=np.sum(w*EWEIGHTS)
    if not np.isfinite(normalizer) or normalizer<=0:
        raise ValueError('Energy PDF unresolved on quadrature grid.')
    return w/normalizer


def prepare_daem_kernel(T):
    """Gauss-Legendre integration of Arrhenius rate over each temperature interval.

    Subdivide long intervals to resolve fast reactions and avoid spurious early
    peaks caused by trapezoidal integration of strongly nonlinear rates.
    """
    T=np.asarray(T,float)
    if len(T)<2 or not np.all(np.isfinite(T)) or np.any(np.diff(T)<=0):
        raise ValueError('DAEM temperature grid must be finite and strictly increasing.')
    integ=np.exp(-ENODES[:,None]/(R*T[None,:]))
    q,qw=roots_legendre(QUAD_ORDER)
    J=np.zeros_like(integ)
    for j in range(1,len(T)):
        lo,hi=T[j-1],T[j]
        nseg=max(1,int(np.ceil((hi-lo)/MAX_QUAD_STEP_K)))
        edges=np.linspace(lo,hi,nseg+1)
        nodes=(edges[:-1,None]+edges[1:,None])/2 + (edges[1:,None]-edges[:-1,None])*q[None,:]/2
        weights=(edges[1:,None]-edges[:-1,None])*qw[None,:]/2
        step=np.exp(-ENODES[:,None]/(R*nodes.ravel()[None,:]))@weights.ravel()
        J[:,j]=J[:,j-1]+step
    return integ,J


def derivative_reference(T,alpha):
    """Noise-resistant experimental derivative; avoids edge artifacts.

    The measured alpha itself is never smoothed or changed for conversion fits.
    """
    T=np.asarray(T,float); alpha=np.asarray(alpha,float)
    n=len(T)
    if n<9:
        return np.maximum(np.gradient(alpha,T),0.0)
    uniform=np.linspace(T[0],T[-1],n)
    ai=PchipInterpolator(T,alpha)(uniform)
    win=min(51,n if n%2 else n-1)
    if win<7:
        deriv=np.gradient(ai,uniform)
    else:
        sm=savgol_filter(ai,win,3,mode='interp')
        deriv=np.gradient(sm,uniform)
    return np.maximum(np.interp(T,uniform,deriv),0.0)


def fit_residual(p,K,T,alpha,beta,kernel,reference):
    pred=model_alpha(p,K,T,beta,kernel)
    logA,_,_,_=parse_params(p,K)
    weights=energy_weights(p,K)*EWEIGHTS
    integ,J=kernel
    survive=np.exp(-(np.exp(logA)/beta)*J)
    derivative=(np.exp(logA)/beta)*(weights@(survive*integ))
    scale=max(float(np.quantile(reference,0.95)),1e-5)
    n=max(len(T),1)
    start_cap=max(3*float(np.max(reference[:min(12,n)])),0.025*scale,1e-6)
    return np.r_[(pred-alpha)/np.sqrt(n),
                 np.sqrt(DERIVATIVE_WEIGHT)*(derivative-reference)/scale/np.sqrt(n),
                 np.sqrt(INITIAL_RATE_PENALTY)*max(derivative[0]-start_cap,0)/scale]


def model_alpha(p,K,T,beta,kernel=None):
    logA,_,_,_=parse_params(p,K); A=np.exp(logA); w=energy_weights(p,K)
    if kernel is None:
        _,J=prepare_daem_kernel(T)
    else:
        _,J=kernel
    S=np.exp(-(A/beta)*J)
    a=1-(w*EWEIGHTS)@S
    return np.clip(a,0,1-1e-9)


def _initial_params(K, seed):
    rng=np.random.default_rng(seed)
    mu0=np.sort(rng.uniform(80,400,K)); ls0=np.log(rng.uniform(15,60,K))
    logA0=rng.uniform(np.log(1e9),np.log(1e13)); z0=rng.normal(0,.2,max(0,K-1))
    return np.r_[logA0, np.column_stack([mu0,ls0]).ravel(), z0]

def fit_one_k(K,T,alpha,beta,nstarts=NSTARTS):
    lbA,ubA=np.log(1e7),np.log(1e15); lbmu,ubmu=80,400; lbls,ubls=np.log(2),np.log(200)
    lb=np.r_[lbA, np.tile([lbmu,lbls],K), np.full(max(0,K-1),-np.inf)]
    ub=np.r_[ubA, np.tile([ubmu,ubls],K), np.full(max(0,K-1), np.inf)]
    kernel=prepare_daem_kernel(T)
    reference=derivative_reference(T,alpha)
    seeds=[RNG_SEED + 100000*K + j for j in range(nstarts)]
    def run(seed):
        p0=_initial_params(K,seed)
        try:
            res=least_squares(lambda p: fit_residual(p,K,T,alpha,beta,kernel,reference),p0,bounds=(lb,ub),
                              max_nfev=800,ftol=1e-8,xtol=1e-8,verbose=0)
            if not res.success:
                print(f'  WARNING: K={K}, seed={seed}: optimizer not converged: {res.message}',flush=True)
            rss=float(np.sum(res.fun**2)); _,_,sigs,pis=parse_params(res.x,K)
            if np.any(sigs<2) or np.any(pis<.005): return None
            return rss,res.x
        except Exception:
            traceback.print_exc()
            return None
    results=[]
    if MAX_WORKERS>1 and nstarts>1:
        with ThreadPoolExecutor(max_workers=min(MAX_WORKERS,nstarts)) as ex:
            futs=[ex.submit(run,seed) for seed in seeds]
            for f in as_completed(futs):
                x=f.result()
                if x is not None: results.append(x)
    else:
        results=[x for x in (run(seed) for seed in seeds) if x is not None]
    best=min(results,key=lambda x:x[0]) if results else None
    if best is None:
        mu0=np.linspace(120,280,K); p0=np.r_[np.log(1e12),np.column_stack([mu0,np.log(30)*np.ones(K)]).ravel(),np.zeros(max(0,K-1))]
        res=least_squares(lambda p: fit_residual(p,K,T,alpha,beta,kernel,reference),p0,bounds=(lb,ub),max_nfev=800,ftol=1e-8,xtol=1e-8)
        if not res.success: print(f'  WARNING: fallback K={K} not converged: {res.message}',flush=True)
        best=(float(np.sum(res.fun**2)),res.x)
    return best



def rmse(yhat,y):
    yhat=np.asarray(yhat); y=np.asarray(y)
    return float(np.sqrt(np.mean((y-yhat)**2)))


def fit_global_one_k(K, datasets, nstarts=NSTARTS):
    """Exact simultaneous fit, with cached kernels and parallel independent starts."""
    lbA,ubA=np.log(1e7),np.log(1e15); lbmu,ubmu=80,400; lbls,ubls=np.log(2),np.log(200)
    lb=np.r_[lbA, np.tile([lbmu,lbls],K), np.full(max(0,K-1),-np.inf)]
    ub=np.r_[ubA, np.tile([ubmu,ubls],K), np.full(max(0,K-1), np.inf)]
    cached=[(rate,T,a,prepare_daem_kernel(T),derivative_reference(T,a)) for rate,T,a in datasets]
    def residual(p):
        rr=[]
        for rate,T,a,kernel,reference in cached:
            rr.append(fit_residual(p,K,T,a,rate/60.0,kernel,reference))
        return np.concatenate(rr)
    seeds=[RNG_SEED + 200000*K + j for j in range(nstarts)]
    def run(seed):
        p0=_initial_params(K,seed)
        try:
            res=least_squares(residual,p0,bounds=(lb,ub),max_nfev=800,ftol=1e-8,xtol=1e-8)
            if not res.success:
                print(f'  WARNING: K={K}, seed={seed}: optimizer not converged: {res.message}',flush=True)
            rss=float(np.sum(res.fun**2)); _,_,sigs,pis=parse_params(res.x,K)
            if np.any(sigs<2) or np.any(pis<.005): return None
            return rss,res.x
        except Exception:
            traceback.print_exc()
            return None
    results=[]
    if MAX_WORKERS>1 and nstarts>1:
        with ThreadPoolExecutor(max_workers=min(MAX_WORKERS,nstarts)) as ex:
            futs=[ex.submit(run,seed) for seed in seeds]
            for f in as_completed(futs):
                x=f.result()
                if x is not None: results.append(x)
    else:
        results=[x for x in (run(seed) for seed in seeds) if x is not None]
    best=min(results,key=lambda x:x[0]) if results else None
    if best is None:
        mu0=np.linspace(120,280,K); p0=np.r_[np.log(1e12),np.column_stack([mu0,np.log(30)*np.ones(K)]).ravel(),np.zeros(max(0,K-1))]
        res=least_squares(residual,p0,bounds=(lb,ub),max_nfev=800,ftol=1e-8,xtol=1e-8)
        if not res.success: print(f'  WARNING: fallback K={K} not converged: {res.message}',flush=True)
        best=(float(np.sum(res.fun**2)),res.x)
    return best


def analyze_global(datasets,sample):
    best={'K':0,'p':None,'RSS':np.inf,'BIC':np.inf}
    n_total=sum(len(a) for _,_,a in datasets)
    for K in range(1,KMAX+1):
        print(f'  Global simultaneous fit {sample}: K={K}/{KMAX}')
        rss,p=checkpoint_fit(checkpoint_path("global",K=K),lambda:fit_global_one_k(K,datasets))
        # Classical alpha-only BIC is evaluated from unweighted alpha residuals;
        # joint fitting residuals are not incorrectly treated as Gaussian alpha RSS.
        alpha_rss=sum(float(np.sum((a-model_alpha(p,K,T,rate/60.0))**2))
                      for rate,T,a in datasets)
        bic=n_total*np.log(max(alpha_rss,np.finfo(float).eps)/max(n_total,1))+(3*K)*np.log(max(n_total,2))
        if bic<best['BIC']: best.update(K=K,p=p,RSS=rss,BIC=bic)
    logA,mus,sigs,pis=parse_params(best['p'],best['K'])
    best.update(A=float(np.exp(logA)),mus=mus,sigs=sigs,pis=pis,Ea_mean=float(np.sum(mus*pis)))
    if best['A'] >= A_UPPER_WARNING_FRACTION*1e15:
        print(f'  WARNING: {sample} GLOBAL A near upper bound 1e15 s^-1; investigate identifiability.',flush=True)
    return best

def r2(yhat,y):
    yhat=np.asarray(yhat); y=np.asarray(y); ss=np.sum((y-yhat)**2); den=np.sum((y-y.mean())**2); return 1-ss/max(den,np.finfo(float).eps)


def effective_energy(T,A,wE):
    integ=np.exp(-ENODES[:,None]/(R*T[None,:])); J=cumulative_trapezoid(integ,T,axis=1,initial=0)
    S=np.exp(-(A)*J)  # beta cancels in ratio only if S already rate-adjusted; caller uses explicit implementation below
    return S


def bin_and_smooth(alpha_core,f_core):
    if len(alpha_core)==0:
        warnings.warn('No identifiable f(alpha) core: legacy unit-shape fallback used; do not interpret it as measured kinetics.')
        ac=np.linspace(ALPHA_MIN,ALPHA_MAX,50); return ac,np.ones_like(ac)
    nb=min(NBINS,max(20,len(alpha_core)//2)) if len(alpha_core)<NBINS else NBINS
    edges=np.unique(np.quantile(alpha_core,np.linspace(0,1,nb+1)))
    if len(edges)<10: edges=np.linspace(ALPHA_MIN,ALPHA_MAX,max(40,nb))
    ac=.5*(edges[:-1]+edges[1:]); ids=np.digitize(alpha_core,edges)-1; fb=np.full(len(ac),np.nan)
    for k in range(len(ac)):
        vals=np.sort(f_core[ids==k])
        if len(vals)>=MIN_PER_BIN:
            t=max(1,round(TRIM_FRAC*len(vals))); vals=vals[t-1:len(vals)-t+1]
            if len(vals): fb[k]=np.exp(np.mean(np.log(np.maximum(vals,1e-300))))
    valid=np.isfinite(fb)&(fb>0)
    if valid.sum()<2:
        order=np.argsort(alpha_core); aa=alpha_core[order]; ff=f_core[order]
        win=max(5,round(.05*len(ff))); ff=pd.Series(ff).rolling(win,center=True,min_periods=1).median().to_numpy()
        lo,hi=np.quantile(ff,[.01,.99]); ff=np.clip(ff,lo,hi); fs=PchipInterpolator(aa,ff,extrapolate=True)(ac)
    else:
        lo,hi=np.quantile(fb[valid],[.01,.99]); vals=np.clip(fb[valid],lo,hi); fs=PchipInterpolator(ac[valid],vals,extrapolate=True)(ac)
    return ac,np.maximum(fs,EPSF)


def phys_scale_f(ac,fs,T,Eeff,A,beta,afit):
    ad=np.linspace(ALPHA_MIN,ALPHA_MAX,2000); gd=np.maximum(PchipInterpolator(ac,fs,extrapolate=True)(ad),EPSF)
    F=cumulative_trapezoid(1/gd,ad,initial=0); G=(A/beta)*cumulative_trapezoid(np.exp(-Eeff/(R*T)),T,initial=0)
    ao=np.clip(afit,ALPHA_MIN,ALPHA_MAX); Fo=PchipInterpolator(ad,F,extrapolate=True)(ao); mask=(ao>ALPHA_MIN+1e-3)&(ao<ALPHA_MAX-1e-3)
    if mask.sum():
        idx=np.flatnonzero(mask); dF=Fo[mask]-Fo[idx[0]]; dG=G[mask]-G[idx[0]]; ci=dF/np.maximum(dG,np.finfo(float).eps); ci=ci[np.isfinite(ci)&(ci>0)]
    else: ci=np.array([])
    c=np.median(ci) if len(ci) else (F[-1]-F[0])/max(G[-1]-G[0],np.finfo(float).eps)
    return np.maximum(c*fs,EPSF)


def analyze_rate(T,alpha,rate,sample):
    beta=rate/60.0; best=None
    for K in range(1,KMAX+1):
        t=time.time(); rss,p=checkpoint_fit(checkpoint_path("individual",rate,K),lambda:fit_one_k(K,T,alpha,beta))
        alpha_rss=float(np.sum((alpha-model_alpha(p,K,T,beta))**2))
        bic=len(T)*np.log(max(alpha_rss,np.finfo(float).eps)/len(T))+(3*K)*np.log(len(T))
        print(f"  {sample} | {rate:g} K/min | K={K}/{KMAX} | RSS={rss:.4g} | BIC={bic:.4g} | {time.time()-t:.1f}s")
        if best is None or bic<best['BIC']: best={'K':K,'p':p,'RSS':rss,'BIC':bic}
    best['alpha_fit']=model_alpha(best['p'],best['K'],T,beta); best['wE']=energy_weights(best['p'],best['K'])
    logA,mus,sigs,pis=parse_params(best['p'],best['K']); A=np.exp(logA); best.update(A=A,mus=mus,sigs=sigs,pis=pis,Ea_mean=float(np.sum(pis*mus)))
    if A >= A_UPPER_WARNING_FRACTION*1e15:
        print(f'  WARNING: {sample} {rate:g} K/min A near upper bound 1e15 s^-1; investigate identifiability.',flush=True)
    # Eeff exactly following MATLAB equations.
    integ,J=prepare_daem_kernel(T); S=np.exp(-(A/beta)*J)
    num=(best['wE']*EWEIGHTS) @ (S*integ); den=(best['wE']*EWEIGHTS) @ S; ratio=np.maximum(num/np.maximum(den,np.finfo(float).eps),1e-300)
    Eeff=-R*T*np.log(ratio); best['Eeff_kJ']=Eeff/1000
    dfit=np.gradient(best['alpha_fit'],T); dn=dfit/max(np.max(dfit+np.finfo(float).eps),np.finfo(float).eps)
    arr=A*np.exp(-Eeff/(R*T)); fraw=(beta/np.maximum(arr,1e-30))*dfit
    core=(best['alpha_fit']>=ALPHA_MIN)&(best['alpha_fit']<=ALPHA_MAX)&(dn>=DERIV_THR)&np.isfinite(fraw)&(fraw>0)
    if core.sum()<30: core=(best['alpha_fit']>=ALPHA_MIN)&(best['alpha_fit']<=ALPHA_MAX)&(dn>=max(DERIV_THR/5,5e-4))&np.isfinite(fraw)&(fraw>0)
    ac,fs=bin_and_smooth(best['alpha_fit'][core],fraw[core]); fphys=phys_scale_f(ac,fs,T,Eeff,A,beta,best['alpha_fit']); best['a_centers']=ac; best['f_alpha']=fphys
    return best


def save_plot(path,xys,xlabel,ylabel,title):
    path=Path(path)
    if path.parent.name not in PLOT_CATEGORIES or path.parent.parent.name != 'Plots':
        raise ValueError(f'Plot requires an explicit category directory: {path}')
    path.parent.mkdir(parents=True,exist_ok=True)
    fig,ax=plt.subplots(figsize=(7.2,5.0))
    try:
        for x,y,label,style in xys: ax.plot(x,y,style,label=label)
        ax.set(xlabel=xlabel,ylabel=ylabel,title=title)
        ax.grid(True,alpha=.25); ax.legend(); fig.tight_layout(); fig.savefig(path,dpi=300)
        print(f'  Plot: {path}',flush=True)
    finally:
        plt.close(fig)


def process_material(name,path,rates,base_out,residual_masses,reference_rate):
    mat_dir=base_out/name; excel_dir=mat_dir/'Excel'; plot_dir=mat_dir/'Plots'; excel_dir.mkdir(parents=True,exist_ok=True); plot_dir.mkdir(parents=True,exist_ok=True)
    folders={k:plot_dir/k for k in PLOT_CATEGORIES}
    for directory in folders.values(): directory.mkdir(parents=True,exist_ok=True)
    global CHECKPOINT_DIR,CHECKPOINT_TAG
    CHECKPOINT_DIR=mat_dir/'Checkpoints'; CHECKPOINT_DIR.mkdir(parents=True,exist_ok=True)
    CHECKPOINT_TAG=hashlib.sha256(repr((file_digest(path),file_digest(Path(__file__)),version('scipy'),np.__version__,FIT_VERSION,rates,reference_rate,residual_masses,NE,KMAX,NSTARTS,EMIN,EMAX,DERIVATIVE_WEIGHT,INITIAL_RATE_PENALTY,QUAD_ORDER,MAX_QUAD_STEP_K,RNG_SEED)).encode()).hexdigest()
    df=read_numeric_table(path); need=2*len(rates)
    if df.shape[1]<need: raise ValueError(f"{path.name}: expected at least {need} columns for {len(rates)} heating rates; found {df.shape[1]}.")

    raw=[]; qc_rows=[]
    for i,rate in enumerate(rates):
        Tc,m=clean_curve(df.iloc[:,2*i],df.iloc[:,2*i+1])
        ok,mf,slope,span=terminal_plateau(Tc,m)
        if len(Tc)<5: raise ValueError(f'{rate:g} K/min: fewer than5 valid rows.')
        print(f'QC {rate:g} K/min: N={len(Tc)}, T={Tc[0]}..{Tc[-1]} C, plateau={ok}, terminal median={mf}%, slope={slope}%/C, span={span}%',flush=True)
        raw.append((rate,Tc,m,ok,mf,slope,span))
        qc_rows.append([rate, Tc[0] if len(Tc) else np.nan, Tc[-1] if len(Tc) else np.nan, len(Tc), ok, mf, slope, span])

    tmaxs=[x[2][-1] if len(x[2]) else np.nan for x in raw]
    finite_tmax=[x[1][-1] for x in raw if len(x[1])]
    overlap_min=max(x[1][0] for x in raw if len(x[1])); overlap_max=min(x[1][-1] for x in raw if len(x[1]))
    if overlap_max<=overlap_min: raise ValueError('Datasets have no common temperature overlap.')
    if max(finite_tmax)-min(finite_tmax)>1:
        print(f"\n{name}: unequal temperature endpoints detected: " + ', '.join(f'{r:g} K/min -> {Tc[-1]:.1f} C' for r,Tc,*_ in raw if len(Tc)))
        print(f"Cross-rate comparisons are restricted to the common overlap: {overlap_min:.1f} to {overlap_max:.1f} C. Each rate is still fitted on its full measured range.")

    print('Normalization: each heating rate uses its own final measured mass as residue.')
    data=[]
    for rate,Tc,m,ok,mf,slope,span in raw:
        T,alpha=mass_to_alpha(Tc,m,residual_masses[rate])
        data.append((rate,T,alpha))

    save_plot(folders['01_QC']/f'{name}_QC_mass.png',[(Tc,m,f'{r:g} K/min','-') for r,Tc,m,*_ in raw],'Temperature (°C)','Mass (%)',f'{name} — Raw mass')
    save_plot(folders['01_QC']/f'{name}_QC_alpha.png',[(T-273.15,a,f'{r:g} K/min','-') for r,T,a in data],'Temperature (°C)','alpha',f'{name} — Conversion using rate-specific measured endpoint mass')
    # QC plots are saved for documentation; RUN is deliberately unattended.
    print(f"QC plots saved for {name}; continuing automatically (no interactive pause).")

    fits={}; summary=[]; pdf_params=[]
    for rate,T,a in data:
        if len(T)<5: raise ValueError(f'{name}, {rate:g}: fewer than5 valid rows.')
        print(f"\nFitting {name} at {rate:g} K/min ({len(T)} points; full range {T[0]-273.15:.1f}-{T[-1]-273.15:.1f} C)")
        fit=analyze_rate(T,a,rate,name); fits[rate]=(T,a,fit)
        _,dmodel,_,_=daem_kinetics(fit['p'],fit['K'],T,rate/60.)
        dref=derivative_reference(T,a)
        summary.append([name,rate,T[0]-273.15,T[-1]-273.15,residual_masses[rate],float(a[-1]),fit['A'],fit['Ea_mean'],fit['K'],fit['RSS'],fit['BIC'],r2(fit['alpha_fit'],a),
                        r2(dmodel,dref),rmse(dmodel,dref),float(T[np.argmax(dmodel)]-T[np.argmax(dref)]),
                        float(np.max(dmodel)/max(np.max(dref),1e-12)-1)])
        print(f'Individual selected {rate:g} K/min: A={fit["A"]} s^-1; K={fit["K"]}; mu={fit["mus"]}, sigma={fit["sigs"]} kJ/mol; weights={fit["pis"]}',flush=True)
        order=np.argsort(fit['mus'])
        for j in order: pdf_params.append([name,rate,j+1,fit['mus'][j],fit['sigs'][j],fit['pis'][j]])
        save_plot(folders['02_DAEM_Fitting']/f'{name}_alpha_exp_DAEM_{rate:g}Kmin.png',[(T-273.15,a,'Experimental','-'),(T-273.15,fit['alpha_fit'],f'DAEM (R2={r2(fit["alpha_fit"],a):.3f})','--')],'Temperature (°C)','alpha',f'{name} — alpha(T), {rate:g} K/min')
        save_plot(folders['05_Eeff']/f'{name}_Eeff_{rate:g}Kmin.png',[(T-273.15,fit['Eeff_kJ'],'Eeff','-')],'Temperature (°C)','Eeff (kJ/mol)',f'{name} — Effective activation energy, {rate:g} K/min')
        Eplot=np.linspace(EMIN/1000,EMAX/1000,1000); total=np.zeros_like(Eplot); curves=[]
        for j,(mu,sg,pi) in enumerate(zip(fit['mus'],fit['sigs'],fit['pis']),1):
            yy=pi*normpdf(Eplot,mu,sg); total+=yy; curves.append((Eplot,yy,f'Component {j}','--'))
        curves.append((Eplot,total,'Total PDF','-')); save_plot(folders['04_Energy_Distributions']/f'{name}_Ea_PDF_{rate:g}Kmin.png',curves,'Ea (kJ/mol)','Density',f'{name} — Energy PDF, {rate:g} K/min')

    # Reference-rate transfer validation: use the fitted parameter vector of one measured rate on all rates.
    if not fits or reference_rate not in fits: raise ValueError('Missing measured reference rate or empty fit set.')
    ref_key=reference_rate
    ref_fit=fits[ref_key][2]
    transfer_rows=[]; transfer_pred={}
    for rate,(T,a,fit) in fits.items():
        pred=model_alpha(ref_fit['p'],ref_fit['K'],T,rate/60.0)
        transfer_pred[rate]=pred
        transfer_rows.append([name,ref_key,rate,r2(pred,a),rmse(pred,a),float(np.sum((a-pred)**2))])

    # Global simultaneous fit: one common A and energy distribution must explain every heating rate.
    print(f'\nRunning GLOBAL simultaneous DAEM for {name} across {len(fits)} heating rates...')
    global_data=[(rate,T,a) for rate,(T,a,_) in fits.items()]
    gfit=analyze_global(global_data,name)
    global_rows=[]; global_pred={}
    for rate,(T,a,_) in fits.items():
        pred=model_alpha(gfit['p'],gfit['K'],T,rate/60.0); global_pred[rate]=pred
        _,dg,_,_=daem_kinetics(gfit['p'],gfit['K'],T,rate/60.)
        dref=derivative_reference(T,a)
        global_rows.append([name,rate,r2(pred,a),rmse(pred,a),float(np.sum((a-pred)**2)),
                            r2(dg,dref),rmse(dg,dref),float(T[np.argmax(dg)]-T[np.argmax(dref)]),
                            float(np.max(dg)/max(np.max(dref),1e-12)-1)])
        save_plot(folders['02_DAEM_Fitting']/f'{name}_comparison_{rate:g}Kmin.png',[
            (T-273.15,a,'Experimental','-'),
            (T-273.15,fits[rate][2]['alpha_fit'],f'Own-rate fit (R2={r2(fits[rate][2]["alpha_fit"],a):.3f})','--'),
            (T-273.15,transfer_pred[rate],f'{ref_key:g} K/min parameters (R2={r2(transfer_pred[rate],a):.3f})',':'),
            (T-273.15,pred,f'Global fit (R2={r2(pred,a):.3f})','-.')],
            'Temperature (°C)','alpha',f'{name} — DAEM comparison, {rate:g} K/min')

    # One overview plot with experimental points/curves and global predictions for all rates.
    overview=[]
    styles=['-','--',':','-.']
    for ii,(rate,(T,a,_)) in enumerate(fits.items()):
        overview.append((T-273.15,a,f'Exp {rate:g} K/min','-'))
        overview.append((T-273.15,global_pred[rate],f'Global {rate:g} K/min','--'))
    save_plot(folders['02_DAEM_Fitting']/f'{name}_GLOBAL_all_rates.png',overview,'Temperature (°C)','alpha',f'{name} — Global DAEM across all heating rates')

    glogA,gmus,gsigs,gpis=parse_params(gfit['p'],gfit['K'])
    alpha_rss_global=sum(row[4] for row in global_rows)
    global_params=[[name,gfit['A'],gfit['Ea_mean'],gfit['K'],gfit['RSS'],gfit['BIC'],alpha_rss_global]]
    print(f'GLOBAL selected: A={gfit["A"]:.17g} s^-1, K={gfit["K"]}, mean={gfit["Ea_mean"]:.17g} kJ/mol, objective={gfit["RSS"]:.17g}, BIC={gfit["BIC"]:.17g}',flush=True)
    print(f'GLOBAL components: mu={gfit["mus"]}, sigma={gfit["sigs"]} kJ/mol, pi={gfit["pis"]}',flush=True)
    global_pdf=[[name,j+1,gmus[j],gsigs[j],gpis[j]] for j in range(gfit['K'])]

    extra={}
    global_f_curves=[]
    for rate,(T,a,fit) in fits.items():
        beta=rate/60.
        psets={'individual':(fit['p'],fit['K']),
               'reference':(ref_fit['p'],ref_fit['K']),
               'global':(gfit['p'],gfit['K'])}
        kinetics={}
        for method,(p,K) in psets.items():
            am,dm,ee,ff=daem_kinetics(p,K,T,beta)
            AA=float(np.exp(parse_params(p,K)[0]))
            ar,dr=reconstruct_from_eeff(T,am,ee,AA,beta,ff)
            kinetics[method]={'alpha':am,'deriv':dm,'Eeff':ee,'f':ff,
                              'alpha_recon':ar,'deriv_recon':dr,'A':AA}
        dexp=np.gradient(a,T)  # Keep existing raw derivative output unchanged.
        plot_comparison(folders['02_DAEM_Fitting']/f'{name}_{rate:g}_alpha.png',T,a,
            kinetics['individual']['alpha'],kinetics['reference']['alpha'],kinetics['global']['alpha'],
            f'{name} {rate:g} K/min: direct DAEM alpha','alpha')
        plot_comparison(folders['02_DAEM_Fitting']/f'{name}_{rate:g}_dalpha_dT.png',T,dexp,
            kinetics['individual']['deriv'],kinetics['reference']['deriv'],kinetics['global']['deriv'],
            f'{name} {rate:g} K/min: direct DAEM derivative','dalpha/dT (1/K)')
        plot_comparison(folders['03_Eeff_A_Reconstruction']/f'{name}_{rate:g}_alpha.png',T,a,
            kinetics['individual']['alpha_recon'],kinetics['reference']['alpha_recon'],kinetics['global']['alpha_recon'],
            f'{name} {rate:g} K/min: Eeff/A/f reconstruction','alpha')
        plot_comparison(folders['03_Eeff_A_Reconstruction']/f'{name}_{rate:g}_dalpha_dT.png',T,dexp,
            kinetics['individual']['deriv_recon'],kinetics['reference']['deriv_recon'],kinetics['global']['deriv_recon'],
            f'{name} {rate:g} K/min: reconstructed derivative','dalpha/dT (1/K)')
        save_plot(folders['05_Eeff']/f'{name}_{rate:g}_Eeff_three_methods.png',
            [(T-273.15,kinetics[m]['Eeff'],m.title(),style) for m,style in [('individual','-'),('reference','--'),('global','-.')]],
            'Temperature (°C)','Eeff (kJ/mol)',f'{name} {rate:g} K/min: effective activation energy')
        # f(alpha) evaluated on each model's own alpha path, then interpolated to common alpha grid.
        grid=np.linspace(ALPHA_MIN,ALPHA_MAX,1001)
        f_table={'alpha':grid}; f_lines=[]
        for m,style in [('individual','-'),('reference','--'),('global','-.')]:
            km=kinetics[m]; al=km['alpha']; ff=km['f']
            # Exact DAEM kinetic identity f=1-alpha under the rate-dependent Eeff definition.
            f_grid=1-grid
            f_table[f'f_{m}']=f_grid
            f_lines.append((grid,f_grid,m.title(),style))
        save_plot(folders['06_f_alpha']/f'{name}_{rate:g}_f_alpha.png',f_lines,
            'alpha','f(alpha)',f'{name} {rate:g} K/min: three methods (exact DAEM identity)')
        global_f_curves.append((grid,1-grid,f'{rate:g} K/min','-'))
        table={'T_K':T,'T_C':T-273.15,'alpha_exp':a,'dalpha_dT_exp':dexp}
        for m,km in kinetics.items():
            for key in ['alpha','deriv','Eeff','f','alpha_recon','deriv_recon']:
                table[f'{key}_{m}']=km[key]
            table[f'R2_alpha_DAEM_{m}']=np.full(len(T),r2(km['alpha'],a))
            table[f'R2_deriv_DAEM_{m}']=np.full(len(T),r2(km['deriv'],dexp))
            table[f'R2_alpha_recon_{m}']=np.full(len(T),r2(km['alpha_recon'],a))
            table[f'R2_deriv_recon_{m}']=np.full(len(T),r2(km['deriv_recon'],dexp))
        extra[rate]={'table':table,'f_table':f_table}
    save_plot(folders['06_f_alpha']/f'{name}_global_f_all_rates.png',global_f_curves,
        'alpha','f_global(alpha)',f'{name}: global f(alpha) across heating rates')
    wb=excel_dir/f'{name}_DAEM_results.xlsx'
    def write_all_sheets(xw):
        pd.DataFrame(summary,columns=['Sample','HeatingRate_Kmin','Tmin_C','Tmax_C','EndpointResidualMass_pct','alpha_at_endpoint','A_DAEM_s_inv','Ea_mean_kJmol','K_best','RSS','BIC','R2_alpha','R2_derivative_smoothed','RMSE_derivative_smoothed','Peak_T_error_K','Peak_height_relative_error']).to_excel(xw,sheet_name='Summary',index=False)
        pd.DataFrame(qc_rows,columns=['HeatingRate_Kmin','Tmin_C','Tmax_C','N_points','TerminalPlateauDetected','TerminalMassMedian_pct','TerminalSlope_pct_per_C','TerminalMassSpan_pct']).to_excel(xw,sheet_name='Range_Plateau_QC',index=False)
        pd.DataFrame([{'CommonOverlap_Tmin_C':overlap_min,'CommonOverlap_Tmax_C':overlap_max,'EndpointResidualMass_pct':str(residual_masses),'Normalization':'Rate-specific final measured mass (last valid temperature point); endpoint alpha=1 by definition'}]).to_excel(xw,sheet_name='Method_Metadata',index=False)
        pd.DataFrame(pdf_params,columns=['Sample','HeatingRate_Kmin','Component','mu_kJmol','sigma_kJmol','weight_pi']).to_excel(xw,sheet_name='PDF_Parameters',index=False)
        pd.DataFrame(transfer_rows,columns=['Sample','ReferenceRate_Kmin','TargetRate_Kmin','R2_reference_transfer','RMSE_reference_transfer','RSS_reference_transfer']).to_excel(xw,sheet_name='Reference_Transfer',index=False)
        pd.DataFrame(global_params,columns=['Sample','A_global_s_inv','Ea_mean_global_kJmol','K_best_global','RSS_global_equal_rate','BIC_global','RSS_alpha_global_unweighted']).to_excel(xw,sheet_name='Global_Summary',index=False)
        pd.DataFrame(global_rows,columns=['Sample','HeatingRate_Kmin','R2_global','RMSE_global','RSS_global_rate','R2_derivative_smoothed','RMSE_derivative_smoothed','Peak_T_error_K','Peak_height_relative_error']).to_excel(xw,sheet_name='Global_Fit_Quality',index=False)
        pd.DataFrame(global_pdf,columns=['Sample','Component','mu_kJmol','sigma_kJmol','weight_pi']).to_excel(xw,sheet_name='Global_PDF_Parameters',index=False)
        for rate,(T,a,fit) in fits.items():
            in_overlap=((T-273.15)>=overlap_min)&((T-273.15)<=overlap_max)
            pd.DataFrame({'T_K':T,'T_C':T-273.15,'in_common_T_overlap':in_overlap,'alpha_exp':a,'alpha_DAEM_own':fit['alpha_fit'],'alpha_reference_transfer':transfer_pred[rate],'alpha_DAEM_global':global_pred[rate],'dalpha_dT_exp':np.gradient(a,T),'dalpha_dT_DAEM_own':np.gradient(fit['alpha_fit'],T),'dalpha_dT_reference_transfer':np.gradient(transfer_pred[rate],T),'dalpha_dT_global':np.gradient(global_pred[rate],T),'Eeff_kJmol_own':fit['Eeff_kJ']}).to_excel(xw,sheet_name=f'Fit_{rate:g}Kmin'[:31],index=False)
            grid=np.linspace(ALPHA_MIN,ALPHA_MAX,1001)
            pd.DataFrame({'alpha':grid,'f_DAEM':PchipInterpolator(fit['a_centers'],fit['f_alpha'],extrapolate=True)(grid)}).to_excel(xw,sheet_name=f'f_alpha_{rate:g}Kmin'[:31],index=False)
        for rate,(T,a,fit) in fits.items():
            kinetic=extra[rate]
            pd.DataFrame(kinetic['table']).to_excel(xw,sheet_name=f'Kinetics_{rate:g}Kmin'[:31],index=False)
            pd.DataFrame(kinetic['f_table']).to_excel(xw,sheet_name=f'f_all_{rate:g}Kmin'[:31],index=False)
        pd.DataFrame([{'Sample':name,'ReferenceRate_Kmin':ref_key,
            'Eeff_definition':'-R*T*ln(weighted surviving Arrhenius factor / weighted survival)',
            'f_alpha_exact':'1-alpha_DAEM for Eeff defined above (DAEM identity; not assumed reaction order)',
            'Reconstruction':'Independent ODE integration with Eeff(T), A and corresponding f(alpha)',
            'Global_fit_objective':GLOBAL_OBJECTIVE,
            'Legacy_RSS_label':'RSS_global_equal_rate stores the FULL joint objective, not alpha-only RSS',
            'Model_selection':'BIC uses unweighted alpha RSS and3K parameters; descriptive heuristic',
            'Derivative_conventions':'Fit/global quality uses smoothed nonnegative derivative; Fit/Kinetics reconstruction plots use raw numpy.gradient',
            'PDF_support_kJmol':f'{EMIN/1000:g} to {EMAX/1000:g}', 'Quadrature_nodes':NE,
            'R2_derivative':'Against numerical gradient of measured conversion',
            'Checkpoint_key':CHECKPOINT_TAG}]).to_excel(xw,sheet_name='Scientific_Definitions',index=False)
    safe_excel_export(wb,write_all_sheets)
    print(f"Saved {name}:\n  Excel: {excel_dir}\n  Plots: {plot_dir}")


def setup_material(name, path, rates):
    """Resolve every decision that could otherwise stop the batch run."""
    validate_rates(rates)
    print(f'Input: {path.resolve()} | SHA256={file_digest(path)}',flush=True)
    print(f'Heating rates={rates} K/min; internal beta=rate/60 K/s',flush=True)
    df=read_numeric_table(path); need=2*len(rates)
    if df.shape[1] < need:
        raise ValueError(f"{path.name}: expected at least {need} columns for {len(rates)} heating rates; found {df.shape[1]}.")
    raw=[]
    for i,rate in enumerate(rates):
        Tc,m=clean_curve(df.iloc[:,2*i],df.iloc[:,2*i+1])
        if len(Tc)<5:
            raise ValueError(f"{name}, {rate:g} K/min: fewer than 5 valid Temperature/Mass rows.")
        ok,mf,slope,span=terminal_plateau(Tc,m)
        raw.append((rate,Tc,m,ok,mf,slope,span))
    print(f"\n{name} preliminary QC:")
    for rate,Tc,m,ok,mf,slope,span in raw:
        state='PASS' if ok else 'NO'
        print(f"  {rate:g} K/min: {Tc[0]:.1f}-{Tc[-1]:.1f} C | N={len(Tc)} | terminal plateau={state} | terminal mass={mf:.4g}% | slope={slope:.4g} %/C")
    tmins=[x[1][0] for x in raw]; tmaxs=[x[1][-1] for x in raw]
    overlap_min=max(tmins); overlap_max=min(tmaxs)
    if overlap_max <= overlap_min:
        raise ValueError(f"{name}: heating-rate datasets have no common temperature overlap.")
    if max(tmaxs)-min(tmaxs)>1:
        print('  Unequal Tmax detected. Own-rate fits will use full ranges; cross-rate interpretation uses common overlap '
              f'{overlap_min:.1f}-{overlap_max:.1f} C.')
    residual_masses={rate:float(m[-1]) for rate,Tc,m,*_ in raw}
    print('  Normalization uses the last measured mass of EACH heating rate as its own residue:')
    for rate in rates:
        print(f'    {rate:g} K/min: final residue = {residual_masses[rate]:.5g}%')
    print('  Note: alpha=1 at each measured endpoint by definition, even if decomposition may continue.')
    default_ref=10.0 if any(abs(r-10.0)<1e-9 for r in rates) else rates[0]
    while True:
        txt=input(f"  Reference heating rate for transfer validation [default {default_ref:g} K/min]: ").strip()
        try: ref=float(txt) if txt else default_ref
        except ValueError:
            print('  Enter one of the measured heating rates.'); continue
        matches=[r for r in rates if abs(r-ref)<1e-9]
        if len(matches)==1:
            ref=matches[0]
            break
        print('  Reference must be one of: '+', '.join(f'{r:g}' for r in rates))
    return {'name':name,'path':path,'rates':rates,'residual_masses':residual_masses,'reference_rate':ref,
            'overlap_min':overlap_min,'overlap_max':overlap_max}


def main():
    print('\n=== DAEM FINAL: robust ranges + individual + reference transfer + global simultaneous fit ===')
    print(f'Exact final model settings: NE={NE}, K=1..{KMAX}, NSTARTS={NSTARTS}; parallel workers={MAX_WORKERS}.')
    print('All questions are collected in SETUP. After final confirmation, RUN contains no input prompts.')
    nmat=ask_int('\nHow many materials/samples will be processed (FS1 ... FSN)? ')
    base=choose_dir('Choose the parent folder where all results will be saved')
    base.mkdir(parents=True,exist_ok=True)
    jobs=[]; names=set()
    for i in range(1,nmat+1):
        print(f'\n--- SETUP material {i}/{nmat} ---')
        default=f'FS{i}'
        name=input(f'Name for material {i} [default {default}]: ').strip() or default
        validate_material_name(name)
        if name.casefold() in names: raise ValueError('Duplicate material directory name in this batch.')
        names.add(name.casefold())
        nr=ask_int(f'How many heating rates exist for {name}? ')
        rates=ask_rates(nr)
        f=choose_file(f'Select Excel/CSV input for {name}')
        input_hash=reserve_material_output(base,name,f,rates)
        with material_log(base,name,'SETUP'):
            job=setup_material(name,f,rates)
            job['input_sha256']=input_hash
            jobs.append(job)

    print('\n================ FINAL BATCH SUMMARY ================')
    print(f'Output parent: {base}')
    for j in jobs:
        print(f"\n{j['name']}")
        print(f"  Input: {j['path']}")
        print('  Heating rates: '+', '.join(f'{r:g}' for r in j['rates'])+' K/min')
        print(f"  Reference transfer rate: {j['reference_rate']:g} K/min")
        print(f"  Endpoint residual masses by rate: {j['residual_masses']}%")
        print(f"  Common temperature overlap: {j['overlap_min']:.2f}-{j['overlap_max']:.2f} C")
    print('\nDuring RUN: no questions, no QC pause, no residual-mass prompt, no reference-rate prompt.')
    ans=input('\nStart complete unattended DAEM batch? (y/n): ').strip().lower()
    if not ans.startswith('y'):
        print('Cancelled before RUN.'); return

    print('\nRunning full output preflight BEFORE any fitting...',flush=True)
    failures=[]
    for idx,j in enumerate(jobs,1):
        print(f"\n================ RUN {idx}/{len(jobs)}: {j['name']} ================")
        try:
            prepare_material_output(base,j)
            with material_log(base,j['name'],'RUN'):
                print(f'Input: {j["path"].resolve()} | SHA256={file_digest(j["path"])}')
                print(f'Heating rates K/min: {j["rates"]}; reference={j["reference_rate"]} K/min')
                print(f'Endpoint residual normalization (%): {j["residual_masses"]}; alpha=1 does not prove complete conversion.')
                print(f'Settings: {FIT_VERSION}; NE={NE}; KMAX={KMAX}; NSTARTS={NSTARTS}; seeds={RNG_SEED}; A bounds1e7..1e15 s^-1; mu80..400 kJ/mol; sigma2..200 kJ/mol; weights via softmax; max_nfev800; ftol=xtol=1e-8; default SciPy gtol.')
                print(f'Runtime: Python={sys.version}; numpy={np.__version__}; scipy={version("scipy")}; pandas={pd.__version__}; matplotlib={version("matplotlib")}; openpyxl={version("openpyxl")}')
                print(f'Objective: {GLOBAL_OBJECTIVE}; output={base/j["name"]}; checkpoint identity={run_identity(j)}')
                preflight_output(base,[j])
                process_material(j['name'],j['path'],j['rates'],base,j['residual_masses'],j['reference_rate'])
        except Exception as e:
            # Do not stop the remaining overnight batch because one material failed.
            failures.append((j['name'],repr(e)))
            print(f"ERROR in {j['name']}: {e}")
            traceback.print_exc()
            print('Continuing automatically with the next material...')
    print('\n================ BATCH FINISHED ================')
    if failures:
        print(f'{len(failures)} material(s) failed:')
        for name,msg in failures: print(f'  {name}: {msg}')
    else:
        print('All materials completed successfully.')

if __name__=='__main__':
    main()
