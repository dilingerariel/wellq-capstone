"""Real HTTP/Mongo regressions; synthetic objects/identity/scanner only."""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from integration.security_s01_s02 import metadata

CAPTURES=[]

@pytest.fixture(scope='session',autouse=True)
def save_evidence():
    yield
    Path('/evidence/review-http-mongo.json').write_text(json.dumps(CAPTURES,indent=2,default=str),encoding='utf-8')

def capture(label,response,ctx,cid):
    body=response.json()
    # Store statuses/review metadata only; no clinical response body or URLs.
    CAPTURES.append({'case':label,'http_status':response.status_code,'error':body.get('detail'),
        'review':body.get('review'),'resource_id':cid,'tenant':ctx.tenant,
        'audit_events':[{k:v for k,v in row.items() if k!='_id'} for row in ctx.raw.audit_events.find(
            {'client_id':ctx.tenant,'resource_id':cid,'event':{'$in':['clinical_test_metadata_updated','clinical_test_reviewed']}})]})

def create(ctx,ready=False):
    if ready:
        init=ctx.start(ai=False)
        for _ in range(150):
            status=ctx.req('GET','/clinical-tests/uploads/'+init['upload_id']+'/status').json()
            if status['status']=='ready_for_review':break
            time.sleep(.2)
        assert status['status']=='ready_for_review' and status['local_file_can_be_deleted']
    else:
        response=ctx.req('POST','/clinical-tests/uploads/initiate',json=metadata(notes='SYNTHETIC PATIENT NOTE'))
        assert response.status_code==201;init=response.json()
    return init['clinical_test_id']

def review(ctx,cid,doctor=None,note='SYNTHETIC PRIVATE NOTE'):
    return ctx.req('PATCH','/clinical-tests/'+cid+'/review',headers=ctx.headers('clinician',identity=doctor or ctx.doctor),
        json={'review_status':'reviewed','review_note':note,'expected_version':ctx.req('GET','/clinical-tests/'+cid,role='clinician').json().get('clinical_version')})

def events(ctx,cid):
    return ctx.raw.audit_events.count_documents({'client_id':ctx.tenant,'resource_id':cid,
        'event':{'$in':['clinical_test_metadata_updated','clinical_test_reviewed']}})

def test_null_omitted_noop_replay_empty_and_private_audit(ctx):
    cid=create(ctx);path='/clinical-tests/'+cid
    response=ctx.req('PATCH',path,json={'title':'SYNTHETIC EDIT'})
    assert response.status_code==200 and response.json()['notes']=='SYNTHETIC PATIENT NOTE'
    cleared=ctx.req('PATCH',path,json={'notes':None});assert cleared.status_code==200 and cleared.json()['notes'] is None
    saved=ctx.raw.clinical_tests.find_one({'clinical_test_id':cid})
    assert ctx.req('PATCH',path,json={'notes':None}).json()==cleared.json()
    assert ctx.raw.clinical_tests.find_one({'clinical_test_id':cid})==saved and events(ctx,cid)==2
    capture('metadata-cleared-idempotent',cleared,ctx,cid)
    for body in ({},{'unknown':True},{'title':None},{'file_name':'bad.pdf'}):
        response=ctx.req('PATCH',path,json=body);assert response.status_code==422
        capture('invalid-patch',response,ctx,cid)
    assert events(ctx,cid)==2
    log=json.dumps(list(ctx.raw.audit_events.find({'resource_id':cid})),default=str)
    assert 'SYNTHETIC PATIENT NOTE' not in log and 'SYNTHETIC EDIT' not in log

@pytest.mark.parametrize('state',['initiated','object_uploaded','processing','rejected','failed','deleted','reviewed'])
def test_unready_upload_states(ctx,state):
    cid=create(ctx)
    ctx.raw.clinical_tests.update_one({'clinical_test_id':cid,'client_id':ctx.tenant},{'$set':{'upload.status':state}})
    response=review(ctx,cid);capture(state,response,ctx,cid)
    assert response.status_code==409 and response.json()['detail']['code']=='DOCUMENT_NOT_READY'
    assert events(ctx,cid)==0


def test_valid_review_replay_different_note_reviewer_and_extraction(ctx):
    cid=create(ctx,True);path='/clinical-tests/'+cid
    ctx.raw.clinical_tests.update_one({'clinical_test_id':cid},{'$set':{'extraction':{'status':'confirmed','extraction_id':'synthetic-extraction'}}})
    first=review(ctx,cid);assert first.status_code==200
    saved=ctx.raw.clinical_tests.find_one({'clinical_test_id':cid})
    replay=review(ctx,cid);assert replay.status_code==200 and replay.json()==first.json()
    assert ctx.raw.clinical_tests.find_one({'clinical_test_id':cid})==saved and events(ctx,cid)==1
    capture('first-and-replay',replay,ctx,cid)
    assert review(ctx,cid,note='CHANGED NOTE').status_code==409
    assert ctx.req('PATCH',path,json={'notes':None}).status_code==409
    patient=ctx.req('GET',path);assert patient.status_code==200 and 'SYNTHETIC PRIVATE NOTE' not in patient.text
    assert saved['extraction']['status']=='confirmed'
    assert 'SYNTHETIC PRIVATE NOTE' not in json.dumps(list(ctx.raw.audit_events.find({'resource_id':cid})),default=str)


def test_two_clinicians_concurrent_only_one_wins(ctx):
    from threading import Barrier
    cid=create(ctx,True);other='synthetic-second-doctor'
    ctx.raw.patient_access.update_one({'client_id':ctx.tenant,'patient_id':ctx.patient},{'$addToSet':{'authorised_clinicians':other}})
    barrier=Barrier(2)
    def call(doctor):
        barrier.wait();return doctor,review(ctx,cid,doctor)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(call,[ctx.doctor,other]))
    assert sorted(r.status_code for _,r in results)==[200,409]
    winner=next(d for d,r in results if r.status_code==200)
    saved=ctx.raw.clinical_tests.find_one({'clinical_test_id':cid})
    assert saved['review']['reviewed_by']==winner and events(ctx,cid)==1
    for doctor,response in results:capture('concurrent:'+doctor,response,ctx,cid)
    assert review(ctx,cid,winner).status_code==200 and events(ctx,cid)==1

@pytest.mark.parametrize('operation',['patch','review'])
@pytest.mark.parametrize('when',['before','after'])
def test_mongo_transaction_audit_failure_is_atomic(ctx,operation,when):
    cid=create(ctx,True);saved=ctx.raw.clinical_tests.find_one({'clinical_test_id':cid})
    ctx.raw['__integration_control'].update_one({'_id':'faults'},{'$set':{'review_audit_failure':{'resource_id':cid,'when':when}}},upsert=True)
    # Observe the deliberate failure once; Context.req retries dependency errors
    # and intentionally raises after its budget, which would hide this response.
    response=ctx.client.patch('/clinical-tests/'+cid+('/review' if operation=='review' else ''),
        headers=ctx.headers('patient' if operation=='patch' else 'clinician'),
        json={'title':'SYNTHETIC ROLLBACK'} if operation=='patch' else {'review_status':'reviewed','review_note':'SYNTHETIC PRIVATE NOTE'})
    capture('rollback:'+operation+':'+when,response,ctx,cid)
    assert response.status_code==503 and ctx.raw.clinical_tests.find_one({'clinical_test_id':cid})==saved
    assert events(ctx,cid)==0
    ctx.raw['__integration_control'].update_one({'_id':'faults'},{'$unset':{'review_audit_failure':''}})
    response=ctx.req('PATCH','/clinical-tests/'+cid,json={'title':'SYNTHETIC ROLLBACK'}) if operation=='patch' else review(ctx,cid)
    assert response.status_code==200 and events(ctx,cid)==1

@pytest.mark.parametrize('operation',['patch','review'])
@pytest.mark.parametrize('actor',['missing','wrong-tenant','unrelated','wrong-role'])
def test_access_denials_are_not_success_events(ctx,operation,actor):
    cid=create(ctx,True);saved=ctx.raw.clinical_tests.find_one({'clinical_test_id':cid})
    role='patient' if operation=='patch' else 'clinician'
    claims={};headers=None
    if actor=='missing':headers={'Idempotency-Key':'synthetic-missing-auth'};status=401
    elif actor=='wrong-tenant':claims={'tenant':'synthetic-other-tenant'};status=404
    elif actor=='unrelated':claims={'identity':'synthetic-unrelated'};status=404 if operation=='patch' else 403
    else:role='clinician' if operation=='patch' else 'patient';status=403
    response=ctx.req('PATCH','/clinical-tests/'+cid+('/review' if operation=='review' else ''),
        headers=headers or ctx.headers(role,**claims),json={'title':'DENIED'} if operation=='patch' else {'review_status':'reviewed'})
    capture('denied:'+operation+':'+actor,response,ctx,cid)
    assert response.status_code==status and events(ctx,cid)==0
    assert ctx.raw.clinical_tests.find_one({'clinical_test_id':cid})==saved
