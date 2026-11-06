import copy
import hashlib
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

import jwt
import pytest
from pymongo.errors import DuplicateKeyError, OperationFailure, WriteError
from app.database import INDEXES
from app.tenancy import TenantDatabase
from app.services.scoring import scoring_engine
from app.config import settings
from integration.guard import database
from conftest import output, pdf


def test_00_runtime_startup_and_contract(ctx):
    import sys, importlib.metadata
    assert sys.version_info[:2] == (3, 11)
    assert ctx.client.get("http://api-int:8000/health").json()["status"] == "ok"
    assert ctx.client.get("http://api-int:8000/ready").status_code == 200
    schema = ctx.client.get("http://api-int:8000/openapi.json").json()
    ops = [v for p, item in schema["paths"].items() if p.startswith('/api/v1') for m,v in item.items() if m in ('get','post','patch','delete')]
    assert len(ops) == 20
    assert all(op['responses']['422']['content']['application/json']['schema']['$ref'].endswith('/ErrorResponse') for op in ops)
    for path in ["/dashboard", "/static/index.html", "/exports/synthetic.pdf"]:
        assert ctx.client.get("http://api-int:8000" + path).status_code == 404
    Path('/evidence/runtime.json').write_text(json.dumps({'python':sys.version,'mongodb':ctx.raw.client.server_info()['version'],
        'dependencies':{d.metadata['Name']:d.version for d in importlib.metadata.distributions()},'gcs':'explicit filesystem/gateway double','ai':'annotated-PDF test double','scanner':'explicit test double in main suite'},indent=2))


def test_mongo_authenticated_replica_indices_validators(raw):
    assert raw.client.admin.command('hello')['setName']=='wellqIntRs'
    for collection, entries in INDEXES.items():
        indices=raw[collection].index_information()
        for name,keys in entries:
            assert indices[name]['unique'] and indices[name]['key']==keys
    with pytest.raises(WriteError) as error:
        raw.clinical_markers.insert_one({'patient_id':'synthetic-no-tenant'})
    assert error.value.code==121
    opts=raw.command('listCollections',filter={'name':'clinical_markers'})['cursor']['firstBatch'][0]['options']
    assert opts['validator']['$jsonSchema']['required']==['client_id']


def test_real_tenant_unique_and_immutable_facade(ctx):
    one=TenantDatabase(ctx.raw,ctx.tenant);two=TenantDatabase(ctx.raw,ctx.tenant+'-other')
    one.clinical_markers.insert_one({'marker_code':'synthetic','patient_id':ctx.patient})
    assert two.clinical_markers.count_documents({})==0
    with pytest.raises(ValueError):one.clinical_markers.update_many({}, {'$set':{'client_id':'other'}})
    one.patient_access.insert_one({'patient_id':'unique-synthetic'})
    with pytest.raises(DuplicateKeyError):one.patient_access.insert_one({'patient_id':'unique-synthetic'})
    two.patient_access.insert_one({'patient_id':'unique-synthetic'})


def test_real_transaction_commit_rollback_two_collections(ctx):
    db=TenantDatabase(ctx.raw,ctx.tenant)
    with db.atomic():
        db.clinical_markers.insert_one({'patient_id':ctx.patient,'marker_code':'commit'})
        db.audit_events.insert_one({'event':'synthetic-commit'})
    assert db.clinical_markers.count_documents({'marker_code':'commit'})==1
    with pytest.raises(RuntimeError):
        with db.atomic():
            db.clinical_markers.insert_one({'patient_id':ctx.patient,'marker_code':'rollback'})
            db.audit_events.insert_one({'event':'synthetic-rollback'})
            raise RuntimeError('test rollback')
    assert db.clinical_markers.count_documents({'marker_code':'rollback'})==0
    assert db.audit_events.count_documents({'event':'synthetic-rollback'})==0


def test_write_conflict_between_independent_mongo_clients(ctx):
    second=database(); doc={'client_id':ctx.tenant,'patient_id':ctx.patient,'marker_code':'conflict','value':0}
    inserted=ctx.raw.clinical_markers.insert_one(doc).inserted_id
    with ctx.raw.client.start_session() as a,second.client.start_session() as b:
        a.start_transaction();b.start_transaction()
        try:
            ctx.raw.clinical_markers.update_one({'_id':inserted},{'$inc':{'value':1}},session=a)
            with pytest.raises(OperationFailure) as failure:
                second.clinical_markers.update_one({'_id':inserted},{'$inc':{'value':1}},session=b)
            assert failure.value.code==112 or failure.value.has_error_label('TransientTransactionError')
        finally:
            a.abort_transaction();b.abort_transaction()
    assert ctx.raw.clinical_markers.find_one({'_id':inserted})['value']==0


def test_http_idempotence_under_two_concurrent_clients(ctx):
    data=pdf(output());body={'client_upload_id':uuid.uuid4().hex,'file_name':'synthetic.pdf','mime_type':'application/pdf',
        'size_bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'test_type':'blood_test','title':'SYNTHETIC','test_date':datetime.utcnow().date().isoformat()}
    headers=ctx.headers(key=uuid.uuid4().hex)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:ctx.req('POST','/clinical-tests/uploads/initiate',headers=headers,json=body),range(2)))
    assert [r.status_code for r in results]==[201,201]
    assert results[0].json()['clinical_test_id']==results[1].json()['clinical_test_id']
    assert ctx.raw.clinical_tests.count_documents({'client_id':ctx.tenant,'patient_id':ctx.patient})==1


@pytest.mark.parametrize('kind',['anonymous','hmac','foreign-tenant','wrong-audience','missing-permission'])
def test_authentication_and_grants_real_http(ctx,kind):
    if kind=='anonymous':headers={};expected=401
    elif kind=='hmac':headers={'Authorization':'Bearer '+jwt.encode({'sub':'synthetic'},'synthetic-key-not-trusted',algorithm='HS256')};expected=401
    elif kind=='wrong-audience':headers=ctx.headers(aud='wrong');expected=401
    elif kind=='missing-permission':headers=ctx.headers(permissions=[]);expected=403
    else:
        init,_=ctx.ready();headers=ctx.headers(tenant=ctx.tenant+'other');expected=404
        assert ctx.client.get('/clinical-tests/'+init['clinical_test_id'],headers=headers).status_code==expected
        return
    assert ctx.client.get('/clinical-tests',headers=headers).status_code==expected


def test_controlled_422_and_503_roll_back_initiation(ctx):
    invalid=ctx.req('POST','/clinical-tests/uploads/initiate',json={})
    assert invalid.status_code==422 and isinstance(invalid.json()['detail'],dict)
    data=pdf(output());body={'client_upload_id':uuid.uuid4().hex,'file_name':'synthetic.pdf','mime_type':'application/pdf','size_bytes':len(data),
        'sha256':hashlib.sha256(data).hexdigest(),'test_type':'blood_test','title':'SYNTHETIC','test_date':datetime.utcnow().date().isoformat()}
    ctx.raw['__integration_control'].replace_one({'_id':'faults'},{'_id':'faults','upload_signer_unavailable':True},upsert=True)
    result=ctx.req('POST','/clinical-tests/uploads/initiate',json=body)
    assert result.status_code==503 and result.json()['detail']['code']=='STORAGE_UNAVAILABLE'
    assert ctx.raw.clinical_tests.count_documents({'client_id':ctx.tenant})==0


def test_export_capability_denied_server_side(ctx):
    assert ctx.req('POST',ctx.patient_url('lab-report/export'),headers=ctx.headers('clinician',capabilities=[]),json={}).status_code==403


def test_worker_persistent_retries_and_backoff(ctx):
    ctx.raw['__integration_control'].replace_one({'_id':'faults'},{'_id':'faults','provider_unavailable':True},upsert=True)
    init=ctx.start();ident={'client_id':ctx.tenant,'clinical_test_id':init['clinical_test_id']}
    for _ in range(100):
        doc=ctx.raw.clinical_tests.find_one(ident);job=doc.get('extraction_job',{})
        if job.get('status')=='pending' and job.get('attempts',0)>=1:break
        time.sleep(.1)
    assert job['attempts']>=1 and job['error_code']=='DEPENDENCY_UNAVAILABLE'
    assert job['available_at']>datetime.utcnow()-timedelta(seconds=1)
    ctx.raw['__integration_control'].delete_one({'_id':'faults'})
    ext=ctx.wait_ext(init)
    assert ext['status']=='awaiting_confirmation'
    assert ctx.raw.clinical_test_extractions.count_documents(ident)==1


def test_worker_expired_lease_and_exhaustion(ctx):
    key='synthetic-'+uuid.uuid4().hex
    ctx.raw.clinical_tests.insert_one({'client_id':ctx.tenant,'clinical_test_id':key,'patient_id':ctx.patient,'deleted_at':None,
        'upload':{'status':'processing','upload_id':key,'client_upload_id':key,'idempotency_key':key,
        'job':{'status':'running','attempts':3,'lease_until':datetime.utcnow()-timedelta(seconds=1)}}})
    for _ in range(50):
        doc=ctx.raw.clinical_tests.find_one({'client_id':ctx.tenant,'clinical_test_id':key})
        if doc['upload']['job']['status']=='failed':break
        time.sleep(.2)
    assert doc['upload']['status']=='failed' and doc['upload']['job']['error_code']=='RETRY_EXHAUSTED'


def test_worker_fences_slow_provider_and_recovers(ctx):
    ctx.raw['__integration_control'].replace_one({'_id':'faults'},{'_id':'faults','provider_delay_seconds':10},upsert=True)
    init=ctx.start();ident={'client_id':ctx.tenant,'clinical_test_id':init['clinical_test_id']}
    for _ in range(100):
        doc=ctx.raw.clinical_tests.find_one(ident)
        if doc.get('extraction_job',{}).get('status')=='running':break
        time.sleep(.1)
    assert doc['extraction_job']['status']=='running'
    # Steal the lease while the first worker has read the source in a real tx.
    time.sleep(.5)
    ctx.raw.clinical_tests.update_one(ident,{'$set':{'extraction_job.lease_token':'synthetic-new-owner',
        'extraction_job.lease_until':datetime.utcnow()+timedelta(seconds=30)}})
    ctx.raw['__integration_control'].delete_one({'_id':'faults'})
    time.sleep(11)
    assert ctx.raw.clinical_test_extractions.count_documents(ident)==0
    ctx.raw.clinical_tests.update_one(ident,{'$set':{'extraction_job.lease_until':datetime.utcnow()-timedelta(seconds=1)}})
    ext=ctx.wait_ext(init)
    assert ext['status']=='awaiting_confirmation'
    assert ctx.raw.clinical_test_extractions.count_documents(ident)==1


def test_f01_publication_gate_against_real_persisted_data(ctx,monkeypatch):
    init,_=ctx.ready(); db=TenantDatabase(ctx.raw,ctx.tenant)
    marker=db.clinical_markers.find_one({'patient_id':ctx.patient})
    assert marker['subscore'] is not None
    monkeypatch.setattr(settings,'ENVIRONMENT','development')
    monkeypatch.setattr(settings,'CATALOG_CLINICALLY_APPROVED',False)
    assert scoring_engine.published_subscore(marker) is None
    assert scoring_engine.compute_patient_score(ctx.patient,db) is None
