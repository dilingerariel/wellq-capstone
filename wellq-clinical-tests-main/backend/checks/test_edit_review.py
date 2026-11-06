"""Focused synthetic regressions for metadata edit and clinical review."""
import pytest
from datetime import datetime
from checks.test_security_s01_s02 import metadata


def create(env,ready=False):
    response=env['client'].post('/api/v1/clinical-tests/uploads/initiate',json=metadata(notes='SYNTHETIC PATIENT NOTE'),
        headers={'Authorization':'Bearer '+env['token'](),'Idempotency-Key':'phase-two-create'})
    assert response.status_code==201
    cid=response.json()['clinical_test_id']
    if ready:
        env['db'].clinical_tests.update_one({'clinical_test_id':cid},{'$set':{
            'upload.status':'ready_for_review','file.verified_at':datetime.utcnow(),'file.generation':1,
            'upload.processing_status':{'malware_scan':'passed','mime_validation':'passed'}}})
    env['db'].patient_access.insert_one({'patient_id':'patient-test','authorised_clinicians':['doctor-1','doctor-2']})
    return cid


def patch(env,cid,body,role='patient',identity='patient-test',tenant='tenant-a'):
    return env['client'].patch('/api/v1/clinical-tests/'+cid,json=body,
        headers={'Authorization':'Bearer '+env['token'](role,identity,tenant)})


def review(env,cid,doctor='doctor-1',body=None):
    return patch(env,cid+'/review',body if body is not None else {'review_status':'reviewed','review_note':'SYNTHETIC PRIVATE NOTE'},'clinician',doctor)


def test_original_g03_null_and_empty_patch(env,fake_storage):
    cid=create(env)
    assert patch(env,cid,{'notes':None}).json()['notes'] is None
    assert patch(env,cid,{}).status_code==422


def test_original_g04_successful_edit_must_emit_audit(env,fake_storage):
    cid=create(env)
    assert patch(env,cid,{'title':'SYNTHETIC NEW TITLE'}).status_code==200
    assert env['db'].audit_events.count_documents({'event':'clinical_test_metadata_updated','resource_id':cid})==1


def test_original_g05_initiated_cannot_be_reviewed(env,fake_storage):
    cid=create(env)
    assert review(env,cid).status_code==409


def test_original_g06_another_reviewer_cannot_replace_first(env,fake_storage):
    cid=create(env,True)
    assert review(env,cid).status_code==200
    assert review(env,cid,'doctor-2').status_code==409
    assert env['db'].clinical_tests.find_one({'clinical_test_id':cid})['review']['reviewed_by']=='doctor-1'

@pytest.mark.parametrize('body,status',[
 ({},422),({'unknown':'value'},422),({'file_name':'new.pdf'},422),({'reviewed_by':'doctor-2'},422),
 ({'title':None},422),({'test_type':None},422),({'test_date':None},422),({'title':''},422),
 ({'notes':None},200),({'notes':''},200),({'title':'NEW SYNTHETIC'},200),({'notes':'NEW SYNTHETIC NOTE'},200)])
def test_patch_field_presence_and_validation(env,fake_storage,body,status):
    cid=create(env);old=env['db'].clinical_tests.find_one({})
    response=patch(env,cid,body);assert response.status_code==status
    saved=env['db'].clinical_tests.find_one({})
    if status==422:
        assert saved==old and env['db'].audit_events.count_documents({'event':'clinical_test_metadata_updated'})==0
    elif 'notes' in body:assert saved['patient_notes']==body['notes']
    else:assert saved['patient_notes']==old['patient_notes']


def test_patch_replay_has_no_extra_write_or_event_and_audit_is_minimized(env,fake_storage):
    import json
    cid=create(env);body={'notes':None,'title':'NEW SYNTHETIC TITLE'}
    first=patch(env,cid,body);saved=env['db'].clinical_tests.find_one({})
    second=patch(env,cid,body)
    assert first.status_code==second.status_code==200 and first.json()==second.json()
    assert env['db'].clinical_tests.find_one({})==saved
    events=list(env['db'].audit_events.find({'event':'clinical_test_metadata_updated'}));assert len(events)==1
    event=events[0]
    assert event['actor_id']=='account:patient-test' and event['actor_role']=='patient'
    assert event['client_id']=='tenant-a' and event['result']=='success' and event['resource_id']==cid
    assert event['metadata_changes']==[
        {'field':'notes','before_present':True,'after_present':False},
        {'field':'title','before_present':True,'after_present':True}]
    text=json.dumps(event,default=str)
    for forbidden in ('SYNTHETIC PATIENT NOTE','NEW SYNTHETIC TITLE','signed_url','Bearer ','sha256'):
        assert forbidden not in text


@pytest.mark.parametrize('role,identity,tenant,status',[
 ('patient','other-patient','tenant-a',404),('patient','patient-test','tenant-b',404),
 ('clinician','doctor-1','tenant-a',403)])
def test_patch_ownership_and_role(env,fake_storage,role,identity,tenant,status):
    cid=create(env);old=env['db'].clinical_tests.find_one({})
    assert patch(env,cid,{'title':'DENIED'},role,identity,tenant).status_code==status
    assert env['db'].clinical_tests.find_one({})==old
    assert env['db'].audit_events.count_documents({'event':'clinical_test_metadata_updated'})==0


@pytest.mark.parametrize('upload_status,status',[(s,200 if s=='ready_for_review' else 409) for s in
    ['initiated','object_uploaded','processing','ready_for_review','rejected','failed','deleted','reviewed']])
def test_review_state_machine(env,fake_storage,upload_status,status):
    cid=create(env,True)
    env['db'].clinical_tests.update_one({'clinical_test_id':cid},{'$set':{'upload.status':upload_status}})
    assert review(env,cid).status_code==status
    assert env['db'].audit_events.count_documents({'event':'clinical_test_reviewed'})==(1 if status==200 else 0)


@pytest.mark.parametrize('changes',[
 {'file.verified_at':None},{'file.generation':None},{'upload.processing_status.malware_scan':'pending'},
 {'upload.processing_status.mime_validation':'failed'},{'deleted_at':datetime(2026,1,1)},
 {'review.status':'unexpected'}])
def test_review_requires_verified_file_and_valid_domain_state(env,fake_storage,changes):
    cid=create(env,True);env['db'].clinical_tests.update_one({'clinical_test_id':cid},{'$set':changes})
    old=env['db'].clinical_tests.find_one({})
    assert review(env,cid).status_code==409
    assert env['db'].clinical_tests.find_one({})==old
    assert env['db'].audit_events.count_documents({'event':'clinical_test_reviewed'})==0


def test_review_idempotency_identity_note_and_extraction_are_preserved(env,fake_storage):
    import json
    cid=create(env,True)
    env['db'].clinical_tests.update_one({'clinical_test_id':cid},{'$set':{'extraction':{'status':'confirmed','extraction_id':'synthetic-ext'}}})
    first=review(env,cid);assert first.status_code==200
    saved=env['db'].clinical_tests.find_one({})
    assert review(env,cid).json()==first.json()
    assert review(env,cid,body={'review_status':'reviewed','review_note':'CHANGED PRIVATE NOTE'}).status_code==409
    assert review(env,cid,'doctor-2').status_code==409
    assert patch(env,cid,{'notes':None}).status_code==409
    assert env['db'].clinical_tests.find_one({})==saved
    assert saved['extraction']['status']=='confirmed'
    events=list(env['db'].audit_events.find({'event':'clinical_test_reviewed'}));assert len(events)==1
    assert events[0]['actor_id']=='account:doctor-1' and events[0]['actor_role']=='clinician'
    assert 'SYNTHETIC PRIVATE NOTE' not in json.dumps(events,default=str)
    for role,identity in [('patient','patient-test'),('clinician','doctor-1')]:
        response=env['client'].get('/api/v1/clinical-tests/'+cid,headers={'Authorization':'Bearer '+env['token'](role,identity)})
        assert response.status_code==200 and 'SYNTHETIC PRIVATE NOTE' not in response.text


@pytest.mark.parametrize('role,identity,tenant,status',[
 ('patient','patient-test','tenant-a',403),('clinician','unrelated-doctor','tenant-a',403),
 ('clinician','doctor-1','tenant-b',404)])
def test_review_role_relationship_and_tenant(env,fake_storage,role,identity,tenant,status):
    cid=create(env,True);old=env['db'].clinical_tests.find_one({})
    response=patch(env,cid+'/review',{'review_status':'reviewed'},role,identity,tenant)
    assert response.status_code==status and env['db'].clinical_tests.find_one({})==old
    assert env['db'].audit_events.count_documents({'event':'clinical_test_reviewed'})==0


@pytest.mark.parametrize('body',[{'reviewed_by':'doctor-2'},{'reviewed_at':'2026-01-01'},
    {'review_status':'not_reviewed'},{'review_status':None},{'review_note':'x'*2001}])
def test_review_does_not_accept_client_authority_or_invalid_note(env,fake_storage,body):
    cid=create(env,True)
    assert review(env,cid,body=body).status_code==422
    assert env['db'].clinical_tests.find_one({})['review']['status']=='not_reviewed'


@pytest.mark.parametrize('operation',['patch','review'])
@pytest.mark.parametrize('when',['before','after'])
def test_audit_failure_rolls_back_domain_and_event(env,fake_storage,operation,when):
    from app.tenancy import TenantCollection
    from pymongo.errors import OperationFailure
    cid=create(env,True);old=env['db'].clinical_tests.find_one({});original=TenantCollection.insert_one
    def broken(self,document,**kwargs):
        if document.get('event') not in ('clinical_test_metadata_updated','clinical_test_reviewed'):
            return original(self,document,**kwargs)
        if when=='after':original(self,document,**kwargs)
        raise OperationFailure('Synthetic audit persistence failure')
    env['monkeypatch'].setattr(TenantCollection,'insert_one',broken)
    response=patch(env,cid,{'notes':None}) if operation=='patch' else review(env,cid)
    assert response.status_code==503
    assert env['db'].clinical_tests.find_one({})==old
    assert env['db'].audit_events.count_documents({'event':{'$in':['clinical_test_metadata_updated','clinical_test_reviewed']}})==0


def test_missing_auth_does_not_write(env,fake_storage):
    cid=create(env,True)
    for suffix in ('','/review'):
        assert env['client'].patch('/api/v1/clinical-tests/'+cid+suffix,json={'notes':None} if not suffix else {'review_status':'reviewed'}).status_code==401
    assert env['db'].audit_events.count_documents({'event':{'$in':['clinical_test_metadata_updated','clinical_test_reviewed']}})==0
