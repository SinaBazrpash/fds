"""Fast static checks only: no imports of eae.py, compilers, fits or simulations."""
from pathlib import Path
import hashlib,json,re,subprocess
root=Path(__file__).resolve().parents[1]
report=json.loads((root/'docs/EAE_REFACTOR_STATIC.json').read_text())
inventory=sorted(p.name for p in (root/'Source').glob('*.f90'))
assert inventory==report['native_fortran_inventory']
assert not any(p.name.startswith('eae') for p in (root/'Source').glob('*.f90'))
for name in ['Build/makefile','CMakeLists.txt']:
    baseline=subprocess.check_output(['git','show',report['native_parent']+':'+name],cwd=root)
    assert (root/name).read_bytes()==baseline,name
    assert not re.search(r'eae\.(?:f90|o|obj)',(root/name).read_text(),re.I)
original=subprocess.check_output(['git','show',report['original_master']+':Source/eae.f90'],cwd=root,text=True)
functions=(root/'Source/func.f90').read_text()
for name in report['moved_routines']:
    pattern=r'^SUBROUTINE '+name+r'\(.*?^END SUBROUTINE'
    old=re.search(pattern,original,re.M|re.S)[0]
    new=re.search(pattern,functions,re.M|re.S)[0]
    assert re.sub(r'\bRG\b','EAE_RG',old)==new,name
assert 'TYPE EAE_CONFIG' in (root/'Source/type.f90').read_text()
assert 'TYPE EAE_STATE' in (root/'Source/type.f90').read_text()
assert 'EAE_STATE_VERSION=1' in (root/'Source/cons.f90').read_text()
# Ordinary numerical/heat/CFD paths and MIN_LAYER_MASS are untouched by this refactor.
for name in ['init','main','mass','divg','pres','velo','fire','radi','chem','data']:
    assert (root/f'Source/{name}.f90').read_bytes()==subprocess.check_output(
        ['git','show',report['original_master']+f':Source/{name}.f90'],cwd=root),name
modules={};uses={}
for p in (root/'Source').glob('*.f90'):
    text=p.read_text()
    assert not re.search(r'^(<<<<<<< |=======\s*$|>>>>>>> )',text,re.M),p.name
    assert not re.search(r'^\s*USE\s+EAE_DAEM\b',text,re.I|re.M),p.name
    for name in re.findall(r'^\s*MODULE\s+(?!PROCEDURE\b)(\w+)',text,re.M|re.I):
        assert name.upper() not in modules,name
        modules[name.upper()]=p.name
    uses[p.name]=[m.upper() for m in re.findall(r'^\s*USE\s+(\w+)',text,re.M|re.I)]
graph={p:{modules[m] for m in names if m in modules and modules[m]!=p} for p,names in uses.items()}
done=set()
def visit(p,stack):
    assert p not in stack,('module cycle',p,stack)
    if p in done:return
    for dep in graph[p]:visit(dep,stack|{p})
    done.add(p)
for p in graph:visit(p,set())
source=(root/'eae.py').read_text();compile(source,str(root/'eae.py'),'exec')
assert 'save_plot(plot_dir/' not in source
assert source.count('fig.savefig(')==1 and 'finally:\n        plt.close(fig)' in source
for folder in ['01_QC','02_DAEM_Fitting','03_Eeff_A_Reconstruction','04_Energy_Distributions','05_Eeff','06_f_alpha']:
    assert folder in source,folder
print(json.dumps(dict(status='PASS',fortran_units=len(inventory),added_eae_units=0,
    native_build_files_exact=True,kinetic_body_text_equivalence=True,acyclic_module_file_graph=True,
    python_compile_only=True,builds_simulations_imports_fits_executed=False),indent=2))
