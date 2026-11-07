"""Synthetic ABA source proof using the existing export API and owned test DB."""
import base64
import json
import uuid

METADATA = """
import json,sys
from bson import json_util
from integration.guard import database
p=json.load(sys.stdin);db=database()
assert p['tenant'].startswith('synthetic-http-') and p['patient'].startswith('synthetic-patient-')
if p['mode']=='inspect':
 r=db.clinical_test_extractions.find_one({'client_id':p['tenant'],'clinical_test_id':p['clinical_test_id']},sort=[('created_at',-1),('_id',-1)])
 assert r and r['extraction_id']
 print(json.dumps({'extraction_id':r['extraction_id'],'metadata':json_util.dumps(r.get('extraction_meta',{}))}))
else:
 query={'client_id':p['tenant'],'clinical_test_id':p['clinical_test_id'],'extraction_id':p['extraction_id']}
 result=db.clinical_test_extractions.update_one(query,{'$set':{'extraction_meta':json_util.loads(p['metadata'])}})
 assert result.matched_count==1
 print(json.dumps({'updated':True}))
"""


def check_export_concurrency(forward, session, fixture, api, container_python):
    own = session('clinician', permissions=['clinical:read', 'reports:export'], capabilities=['report_export'])
    headers = {'Authorization': 'Bearer ' + own['accessToken'], 'Content-Type': 'application/json'}
    base = '/api/v1/patients/' + fixture['patient'] + '/lab-report'
    def report():
        response = forward(base + '?include_series=true&include_snapshot=true', headers)
        assert response['status'] == 200
        value = json.loads(base64.b64decode(response['body']))
        value.pop('generated_at')
        return value
    original = report()
    exam = original['header']['exams'][0]['clinical_test_id']
    args = {**fixture, 'clinical_test_id': exam}
    prior = container_python(api, METADATA, {**args, 'mode': 'inspect'})
    changed = json.dumps({**json.loads(prior['metadata']), 'synthetic_export_probe': 'SYNTHETIC INTERVENING SOURCE'})
    key = 'synthetic-aba-' + uuid.uuid4().hex
    export_headers = {**headers, 'Idempotency-Key': key}
    body = json.dumps({'window_months': 12, 'include_series': True}).encode()
    try:
        assert container_python(api, METADATA, {**args, **prior, 'mode': 'change', 'metadata': changed})['updated']
        assert report() != original
        created = forward(base + '/export', export_headers, 'POST', body)
        assert created['status'] == 200
        assert json.loads(base64.b64decode(created['body']))['replayed'] is False
    finally:
        assert container_python(api, METADATA, {**args, **prior, 'mode': 'restore'})['updated']
    assert report() == original, 'Synthetic export source was not restored exactly'
    replay = forward(base + '/export', export_headers, 'POST', body)
    assert replay['status'] == 409
    assert json.loads(base64.b64decode(replay['body']))['detail']['code'] == 'EXPORT_SOURCE_CHANGED'
    return {'source_a_restored_exactly': True, 'intervening_pdf_b_created': True,
            'full_source_replay_denied_409': True, 'same_key_used': True,
            'scope': 'owned synthetic tenant only; no production data or API contract changes'}
