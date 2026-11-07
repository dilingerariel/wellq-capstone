"""Real reporting HTTP and guarded Mongo evidence; explicit synthetic storage/identity."""
import base64
import json

SIGNER = """
import json,sys
from integration.guard import database
p=json.load(sys.stdin);db=database();controls=db['__integration_control']
if p['mode']=='inspect':
 old=controls.find_one({'_id':'faults'}) or {}
 assert old.get('signer_unavailable') in (None,False)
 print(json.dumps({'existed':'signer_unavailable' in old,'value':old.get('signer_unavailable')}))
elif p['mode']=='enable':
 controls.update_one({'_id':'faults'},{'$set':{'signer_unavailable':True}},upsert=True)
 print(json.dumps({'enabled':True}))
else:
 update={'$set':{'signer_unavailable':p['value']}} if p['existed'] else {'$unset':{'signer_unavailable':''}}
 controls.update_one({'_id':'faults'},update)
 print(json.dumps({'restored':True}))
"""

VERIFY = """
import hashlib,io,json,sys
from integration.guard import database
from integration.adapters import object_path,sign
from pypdf import PdfReader
p=json.load(sys.stdin);db=database();tenant={'client_id':p['tenant'],'patient_id':p['patient']}
rows=list(db.lab_report_exports.find(tenant));assert len(rows)==1
r=rows[0];data=object_path(r['object_key']).read_bytes()
assert data.startswith(b'%PDF-') and len(data)==r['size_bytes']
assert hashlib.sha256(data).hexdigest()==r['sha256']
assert len(PdfReader(io.BytesIO(data)).pages)>0
assert db.audit_events.count_documents({**tenant,'event':'lab_report_export'})==1
print(json.dumps({'server_pdf_verified':True,'single_export_and_audit':True,'expired_test_url':sign(r['object_key'],'GET',-1)}))
"""

def check_records(forward, session, fixture, api, container_python, exports, downloads):
    base='/api/v1/patients/'+fixture['patient']
    own=session('clinician',permissions=['clinical:read','reports:export'],capabilities=['report_export'])
    checks=[]
    def call(path, who, expected, method='GET', body=None, key=None):
        headers={'Content-Type':'application/json'}
        if who:headers['Authorization']='Bearer '+who['accessToken']
        if key:headers['Idempotency-Key']=key
        response=forward(path,headers,method,json.dumps(body).encode() if body is not None else None)
        checks.append({'path_kind':path.split('/')[-1].split('?')[0],'status':response['status'],'expected':expected})
        if who is own:
            assert response['status']==expected,'Authorized reporting status mismatch: '+json.dumps(checks[-1])
        return json.loads(base64.b64decode(response['body']))
    for suffix,expected in [('/markers?marker_codes=glucose',200),('/lab-score?history=true',200),('/lab-report?include_series=true&include_snapshot=true',200)]:
        result=call(base+suffix,own,expected)
        if suffix.startswith('/lab-score'):assert result['current_snapshot']['catalog_clinically_approved'] is False
        if suffix.startswith('/lab-report'):
            assert result['header']['patient_id']==fixture['patient'] and result['score'] is not None
            assert 'SYNTHETIC PRIVATE REVIEW' not in json.dumps(result) and 'SYNTHETIC CLINICAL NOTE' not in json.dumps(result)
        for identity,denied in [(None,401),(session(permissions=['clinical:read']),403),(session('clinician',permissions=[]),403),(session('clinician',resource='synthetic-unrelated'),403),(session('clinician',tenant='synthetic-other-tenant'),403)]:
            call(base+suffix,identity,denied)
    for identity,denied in [(session('clinician'),403),(session('clinician',permissions=['reports:export']),403),(session(permissions=['reports:export'],capabilities=['report_export']),403),(session('clinician',resource='synthetic-unrelated',permissions=['reports:export'],capabilities=['report_export']),403),(session('clinician',tenant='synthetic-other-tenant',permissions=['reports:export'],capabilities=['report_export']),403)]:
        call(base+'/lab-report/export',identity,denied,'POST',{'window_months':12,'include_series':True},'synthetic-denied-export')
    mismatches=[c for c in checks if c['status']!=c['expected']]
    assert not mismatches,'Reporting status mismatches: '+json.dumps(mismatches)
    assert len(exports)==2 and exports[0]==exports[1] and downloads['count']==1 and not downloads['authorization_seen']
    path,headers,body=exports[0]
    def replay():
        r=forward(path,headers,'POST',body);assert r['status']==200
        return json.loads(base64.b64decode(r['body']))
    assert replay()['replayed'] is True
    prior=container_python(api,SIGNER,{'mode':'inspect'})
    try:
        assert container_python(api,SIGNER,{'mode':'enable'})['enabled']
        pending=replay();assert pending['status']=='download_pending' and pending['download_url'] is None and pending['expires_at'] is None
    finally:assert container_python(api,SIGNER,{'mode':'restore',**prior})['restored']
    assert replay()['status']=='ready'
    proof=container_python(api,VERIFY,fixture)
    from urllib.parse import urlsplit
    expired=urlsplit(proof.pop('expired_test_url'))
    assert forward(expired.path+'?'+expired.query,{},storage=True)['status']==403
    return {'checks':checks,'mongo':proof,'unapproved_test_snapshot_verified':True,'signer_outage_and_recovery_verified':True,'expired_storage_signature_denied':True,'pdf_download_without_bearer':True}


def check_stale_export(forward, exports):
    path,headers,body=exports[0]
    response=forward(path,headers,'POST',body)
    assert response['status']==409
    assert json.loads(base64.b64decode(response['body']))['detail']['code']=='EXPORT_SOURCE_CHANGED'
    return True
