"""Focused actual HTTP/Mongo checks; platform ownership remains an explicit test double."""
import hashlib
import json
import uuid
from datetime import date
from pathlib import Path

from integration.examples import redact
from integration.guard import database
from integration.tests.conftest import Context


def metadata(**changes):
    body={'client_upload_id':uuid.uuid4().hex,'file_name':'synthetic.pdf','mime_type':'application/pdf',
          'size_bytes':10,'sha256':hashlib.sha256(b'synthetic!').hexdigest(),'test_type':'blood_test',
          'title':'SYNTHETIC SECURITY TEST','test_date':date.today().isoformat()}
    body.update(changes);return body


def reproduce_before():
    raw=database();results=[]
    for finding,changes in [('S01',{'case_id':'synthetic-unverified-case'}),('S02',{'file_name':'synthetic.exe'})]:
        ctx=Context(raw)
        try:
            response=ctx.req('POST','/clinical-tests/uploads/initiate',json=metadata(**changes))
            assert response.status_code==201,'Original issue no longer reproduced; inspect before editing'
            results.append({'finding':finding,'status':response.status_code,'response':redact(response.json()),
                'persisted_records':raw.clinical_tests.count_documents({'client_id':ctx.tenant})})
        finally:ctx.client.close()
    Path('/evidence/http-before.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print('Both original gaps reproduced over real HTTP/Mongo: 201 with persisted authorization; URLs redacted')

import time

import pytest

HTTP_EVIDENCE=[]

@pytest.fixture(scope='session',autouse=True)
def evidence():
    yield
    Path('/evidence/http-after.json').write_text(json.dumps(HTTP_EVIDENCE,indent=2),encoding='utf-8')

def record(label,response,ctx):
    HTTP_EVIDENCE.append({'case':label,'status':response.status_code,'response':redact(response.json()),
        'persisted_records':ctx.raw.clinical_tests.count_documents({'client_id':ctx.tenant})})

def association(ctx,resource,**changes):
    row={'_id':'association:'+resource,'client_id':ctx.tenant,'patient_id':ctx.patient,
         'authorized':True,'active':True,'care_relationship_valid':True}
    row.update(changes);ctx.raw['__integration_control'].insert_one(row)

@pytest.mark.parametrize('field',['case_id','appointment_id'])
@pytest.mark.parametrize('outcome,status',[('valid',201),('patient',403),('tenant',403),('missing',403),
    ('unauthorized',403),('inactive',403),('relationship',403),('unavailable',503)])
def test_associations_http_mongo(ctx,field,outcome,status):
    resource=uuid.uuid4().hex
    changes={'patient':{'patient_id':'other'},'tenant':{'client_id':'other'},
        'unauthorized':{'authorized':False},'inactive':{'active':False},'relationship':{'care_relationship_valid':False}}
    if outcome!='missing':association(ctx,resource,**changes.get(outcome,{}))
    if outcome=='unavailable':ctx.raw['__integration_control'].update_one({'_id':'faults'},{'$set':{'association_unavailable':True}},upsert=True)
    body=metadata(**{field:resource});headers=ctx.headers()
    response=ctx.req('POST','/clinical-tests/uploads/initiate',headers=headers,json=body)
    record(field+':'+outcome,response,ctx);assert response.status_code==status
    assert ctx.raw.clinical_tests.count_documents({'client_id':ctx.tenant})==(1 if status==201 else 0)
    if status!=201:assert 'signed_url' not in response.text
    else:
        replay=ctx.req('POST','/clinical-tests/uploads/initiate',headers=headers,json=body)
        assert replay.status_code==201 and replay.json()==response.json()
        ctx.raw['__integration_control'].update_one({'_id':'association:'+resource},{'$set':{'authorized':False}})
        assert ctx.req('POST','/clinical-tests/uploads/initiate',headers=headers,json=body).status_code==403
        patch=ctx.req('PATCH','/clinical-tests/'+response.json()['clinical_test_id'],json={field:resource})
        assert patch.status_code==403

@pytest.mark.parametrize('name,mime,status',[
 ('valid.pdf','application/pdf',201),('valid.jpeg','image/jpeg',201),('valid.jpg','image/jpeg',201),
 ('valid.png','image/png',201),('valid.heic','image/heic',201),('VALID.PDF','APPLICATION/PDF',201),
 ('análisis.2026.pdf','application/pdf',201),('report.exe','application/pdf',422),
 ('report.exe.pdf','application/pdf',422),('../report.pdf','application/pdf',422),
 ('report.png','application/pdf',422),('report.pdf','image/png',422)])
def test_metadata_http_mongo(ctx,name,mime,status):
    body=metadata(file_name=name,mime_type=mime);headers=ctx.headers()
    response=ctx.req('POST','/clinical-tests/uploads/initiate',json=body,headers=headers)
    record(name,response,ctx);assert response.status_code==status
    assert ctx.raw.clinical_tests.count_documents({'client_id':ctx.tenant})==(1 if status==201 else 0)
    if status==422:assert 'signed_url' not in response.text
    else:
        changed=ctx.req('POST','/clinical-tests/uploads/initiate',json={**body,'file_name':'different.'+name.rsplit('.',1)[-1]},headers=headers)
        assert changed.status_code==409

def test_actual_bytes_still_rejected(ctx):
    body=metadata();response=ctx.req('POST','/clinical-tests/uploads/initiate',json=body)
    assert response.status_code==201;init=response.json()
    assert ctx.client.put(init['upload']['signed_url'],content=b'synthetic!',headers=init['upload']['required_headers']).status_code==200
    complete=ctx.req('POST','/clinical-tests/uploads/'+init['upload_id']+'/complete',json={k:body[k] for k in ('client_upload_id','sha256','size_bytes')})
    assert complete.status_code==200 and not complete.json()['local_file_can_be_deleted']
    for _ in range(150):
        response=ctx.req('GET','/clinical-tests/uploads/'+init['upload_id']+'/status')
        if response.json()['status']=='rejected':break
        time.sleep(.2)
    record('declared-pdf-with-invalid-bytes',response,ctx)
    assert response.json()['status']=='rejected' and not response.json()['local_file_can_be_deleted']
    saved=ctx.raw.clinical_tests.find_one({'clinical_test_id':init['clinical_test_id']})
    assert saved['file']['gcs_object_key'].startswith('quarantine/')


def test_patch_and_refresh_associations(ctx):
    resource=uuid.uuid4().hex;association(ctx,resource)
    body=metadata();init=ctx.req('POST','/clinical-tests/uploads/initiate',json=body).json()
    patch=ctx.req('PATCH','/clinical-tests/'+init['clinical_test_id'],json={'case_id':resource})
    record('patch-verified-association',patch,ctx);assert patch.status_code==200
    ctx.raw['__integration_control'].update_one({'_id':'faults'},{'$set':{'association_unavailable':True}},upsert=True)
    refreshed=ctx.req('POST','/clinical-tests/uploads/'+init['upload_id']+'/refresh-url',
        json={k:body[k] for k in ('client_upload_id','sha256')})
    record('refresh-verifier-unavailable',refreshed,ctx);assert refreshed.status_code==503
    assert 'signed_url' not in refreshed.text
    cleared=ctx.req('PATCH','/clinical-tests/'+init['clinical_test_id'],json={'case_id':None})
    assert cleared.status_code==200 and cleared.json()['case_id'] is None
