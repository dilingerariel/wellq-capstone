"""Generate/check the patient's actual OpenAPI projection, never invent routes."""
import argparse
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = root.parent / 'backend/docs/openapi.json'
spec = json.loads(source.read_text(encoding='utf-8'))
paths = {p: v for p, v in spec['paths'].items() if p.startswith('/api/v1/clinical-tests') and
         not p.endswith(('/review', '/download-url', '/validate', '/reprocess'))}
names = set()
def refs(value):
    if isinstance(value, dict):
        if '$ref' in value:
            name = value['$ref'].rsplit('/', 1)[1]
            if name not in names:
                names.add(name)
                refs(spec['components']['schemas'][name])
        for child in value.values():
            refs(child)
    elif isinstance(value, list):
        for child in value:
            refs(child)
refs(paths)
result = {'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
          'paths': paths, 'schemas': {name: spec['components']['schemas'][name] for name in sorted(names)}}
encoded = json.dumps(result, indent=2, ensure_ascii=True) + '\n'
target = root / 'contracts.patient.json'
parser = argparse.ArgumentParser()
parser.add_argument('--check', action='store_true')
args = parser.parse_args()
if args.check:
    assert target.read_text(encoding='utf-8') == encoded, 'OpenAPI changed: review DTOs and regenerate the patient projection'
    print('Patient OpenAPI projection matches current backend')
else:
    target.write_text(encoded, encoding='utf-8')
