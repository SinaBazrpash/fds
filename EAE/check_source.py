"""Static publication checks only; never invokes a compiler, make or FDS."""
from pathlib import Path
import re,json
r=Path(__file__).resolve().parents[1]
checks={
 'Source/eae.f90':['MODULE EAE_DAEM','SUBROUTINE EAE_GL','SUBROUTINE EAE_TRIAL','SUBROUTINE EAE_DIAGNOSTICS','T_END','EAE_STATE_VERSION'],
 'Source/type.f90':['USE EAE_DAEM','TYPE(EAE_CONFIG)','TYPE(EAE_STATE)'],
 'Source/read.f90':['EAE_A','EAE_K','EAE_MU','EAE_SIGMA','EAE_PI','EAE_NODES','EAE_SETUP','EAE_TGA_PRESCRIBED','EAE TGA: upstream dedicated TGA loop'],
 'Source/func.f90':['EAE','REFERENCE','MASS'],
 'Source/dump.f90':['FDSEAE01','EAE_CHECK_RESTART','EAE_DIAGNOSTICS','CASE(102:104)'],
 'Source/data.f90':['EAE_CONVERSION','EAE_REMAINING_MASS','EAE_EEFF'],
 'Source/cons.f90':['TGA_ANALYSIS_REQUESTED','EAE_TGA_LINEAR'],
 'Source/wall.f90':['pending bin depletion differs from accepted FDS mass consumption','Forced removal does not override','SUBROUTINE TGA_EAE_ANALYSIS','Total_Solid_Mass_Normalized','EAE_SOURCE_ENERGY','EAE_T_BEGIN','REFERENCE','M_DOT_LAYER_PP','STEPS=CEILING(END_TIME/TGA_DT-1.E-9_EB)'],
 'CMakeLists.txt':['Source/eae.f90','OUTPUT_NAME fdseae'],
 'Build/makefile':['obj_mpi = prec.o eae.o','eae.o : prec.o','eae.obj : prec.obj','type.o : prec.o cons.o imkl.o eae.o','type.obj : prec.obj cons.obj imkl.obj eae.obj']}
for path,tokens in checks.items():
 text=(r/path).read_text()
 for token in tokens:assert token in text,(path,token)
 assert not re.search(r'^(<<<<<<< |=======\s*$|>>>>>>> )',text,re.M),path
# Assert the Fortran module graph resolves each internal USE and has no cycles.
modules={};uses={}
for p in (r/'Source').glob('*.f90'):
 text=p.read_text()
 for name in re.findall(r'^\s*MODULE\s+(?!PROCEDURE\b)(\w+)',text,re.M|re.I):modules[name.upper()]=p.name
 uses[p.name]=[m.upper() for m in re.findall(r'^\s*USE\s+(\w+)',text,re.M|re.I)]
graph={p:{modules[m] for m in names if m in modules and modules[m]!=p} for p,names in uses.items()}
done=set()
def visit(p,stack):
 assert p not in stack,('module cycle',p,stack)
 if p in done:return
 for dep in graph[p]:visit(dep,stack|{p})
 done.add(p)
for p in graph:visit(p,set())
print(json.dumps({'status':'PASS','checks':'source tokens, conflict markers, internal module dependency graph','files':len(checks),'modules':len(modules),'builds_or_simulations_executed':False},indent=2))
