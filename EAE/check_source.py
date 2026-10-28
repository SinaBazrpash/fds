"""Static exact-source provenance check; no compiler or simulations."""
from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1]
m=json.loads((root/'docs/EAE_3D_SOURCE_PROVENANCE.json').read_text())
for name,expected in m['source_sha256'].items():
    assert hashlib.sha256((root/'Source'/name).read_bytes()).hexdigest()==expected,name
for name,expected in m['build_file_sha256'].items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==expected,name
print('PASS: exact installed41-source and build-file hashes; no runtime qualification')
