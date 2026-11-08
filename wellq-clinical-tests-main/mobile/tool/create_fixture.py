"""Reviewed, deterministic, human-readable synthetic PDF for the local extractor."""
import base64
import hashlib
import json
from pathlib import Path
from reportlab.pdfgen import canvas

root = Path(__file__).resolve().parents[1]
payload = {
    'schema_version': '1.0', 'document_type': 'blood_panel', 'language': 'es',
    'page_count': 1, 'collection_date': '2026-11-08',
    'panels': [{'panel_code': 'metabolic', 'panel_name_raw': 'SYNTHETIC', 'specimen': 'blood',
                'markers': [{'marker_code': 'glucose', 'raw_name': 'SYNTHETIC glucose',
                             'value_raw': '90', 'unit_raw': 'mg/dL',
                             'confidence': dict.fromkeys(['value', 'unit', 'reference', 'name'], .99),
                             'page': 1, 'evidence': 'SYNTHETIC MOBILE SAMPLE'}]}],
}
pdf = root / 'assets/synthetic.pdf'
c = canvas.Canvas(str(pdf), pageCompression=0, invariant=1)
c.setTitle('SYNTHETIC WellQ mobile fixture')
c.setFont('Helvetica-Bold', 18)
c.drawString(28, 760, 'SYNTHETIC MOBILE SAMPLE')
c.setFont('Helvetica', 12)
c.drawString(28, 730, 'NO PATIENT DATA - NOT FOR CLINICAL USE')
c.drawString(28, 690, 'Collection date: 2026-11-08')
c.drawString(28, 660, 'Glucose (synthetic): 90 mg/dL')
c.drawString(28, 620, 'No clinical interpretation or reference range is asserted.')
c.setFont('Helvetica', 4)
c.drawString(10, 560, 'WQINT:' + base64.b64encode(json.dumps(payload).encode()).decode())
c.save()
digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
(root / 'lib/domain/sample_policy.dart').write_text(
    '// Only this reviewed fixture may be persisted in phase 1.\n'
    'const syntheticPdfSha256 = ' + repr(digest) + ';\n', encoding='utf-8')
print('Reviewed synthetic PDF and matching hash policy generated')
