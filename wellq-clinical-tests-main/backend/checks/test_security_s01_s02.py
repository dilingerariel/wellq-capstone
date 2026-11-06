"""Focused security regressions; fixtures prevent network and real data access."""
import hashlib
import unicodedata
from datetime import date
from dataclasses import replace
import pytest
from app.services.storage import storage_service


def metadata(**changes):
    body={'client_upload_id':'security-test-upload','file_name':'synthetic.pdf','mime_type':'application/pdf',
          'size_bytes':10,'sha256':hashlib.sha256(b'synthetic!').hexdigest(),'test_type':'blood_test',
          'title':'SYNTHETIC SECURITY TEST','test_date':date.today().isoformat()}
    body.update(changes);return body


def initiate(env,body,key='security-idempotency-01'):
    return env['client'].post('/api/v1/clinical-tests/uploads/initiate',json=body,
        headers={'Authorization':'Bearer '+env['token'](),'Idempotency-Key':key})


def test_original_s01_unverified_association_must_not_be_authorized(env,fake_storage):
    response=initiate(env,metadata(case_id='synthetic-case-with-no-verifier'))
    assert response.status_code==503
    assert response.json()['detail']['code']=='ASSOCIATION_VERIFIER_UNAVAILABLE'
    assert env['db'].clinical_tests.count_documents({})==0


def test_original_s02_incoherent_extension_must_not_be_authorized(env,fake_storage):
    response=initiate(env,metadata(file_name='synthetic.exe'))
    assert response.status_code==422
    assert env['db'].clinical_tests.count_documents({})==0


@pytest.fixture
def signed(env,fake_storage):
    calls=[];original=storage_service.generate_upload_url
    def sign(*args,**kwargs):
        calls.append((args,kwargs));return original(*args,**kwargs)
    env['monkeypatch'].setattr(storage_service,'generate_upload_url',sign)
    return calls


def verifier(env,outcome='valid'):
    from app.services import associations
    calls=[]
    class SyntheticVerifier:
        def verify(self,kind,resource_id,scope):
            calls.append((kind,resource_id,scope))
            if outcome=='unavailable':raise TimeoutError('Synthetic outage; never reflected')
            if outcome=='malformed':return True
            decision=associations.AssociationDecision(kind,resource_id,scope.client_id,scope.patient_id,
                exists=True,authorized=True,active=True,care_relationship_valid=True)
            changes={'patient':{'patient_id':'another-patient'},'tenant':{'client_id':'another-tenant'},
                'missing':{'exists':False},'unauthorized':{'authorized':False},'inactive':{'active':False},
                'relationship':{'care_relationship_valid':False},'kind':{'kind':'wrong-kind'},'resource':{'resource_id':'wrong-resource'}}
            return replace(decision,**changes.get(outcome,{}))
    env['monkeypatch'].setattr(associations,'association_verifier',SyntheticVerifier());return calls


@pytest.mark.parametrize('field',['case_id','appointment_id'])
@pytest.mark.parametrize('outcome,status',[
    ('valid',201),('patient',403),('tenant',403),('missing',403),('unauthorized',403),
    ('inactive',403),('relationship',403),('kind',403),('resource',403),('unavailable',503),('malformed',503)])
def test_association_is_verified_before_persisting_or_signing(env,signed,field,outcome,status):
    calls=verifier(env,outcome)
    response=initiate(env,metadata(**{field:'synthetic-association'}))
    assert response.status_code==status
    scope=calls[0][2];assert scope.client_id=='tenant-a' and scope.patient_id=='patient-test'
    assert scope.actor_id=='account:patient-test' and scope.actor_role=='patient'
    assert len(signed)==(1 if status==201 else 0)
    assert env['db'].clinical_tests.count_documents({})==(1 if status==201 else 0)
    if status!=201:assert 'signed_url' not in response.text


def test_optional_associations_do_not_require_platform_verifier(env,signed):
    assert initiate(env,metadata()).status_code==201
    assert len(signed)==1


def test_both_associations_are_checked_and_replay_is_idempotent(env,signed):
    calls=verifier(env)
    body=metadata(case_id='case-test',appointment_id='appointment-test')
    first=initiate(env,body);replay=initiate(env,body)
    assert first.status_code==replay.status_code==201 and first.json()==replay.json()
    assert [x[0] for x in calls]==['case','appointment','case','appointment']
    assert len(signed)==1 and env['db'].clinical_tests.count_documents({})==1


def test_replay_rechecks_revoked_or_unavailable_association(env,signed):
    verifier(env);body=metadata(case_id='case-test');assert initiate(env,body).status_code==201
    verifier(env,'unavailable');assert initiate(env,body).status_code==503
    verifier(env,'unauthorized');assert initiate(env,body).status_code==403
    assert len(signed)==1 and env['db'].clinical_tests.count_documents({})==1


@pytest.mark.parametrize('field',['case_id','appointment_id'])
@pytest.mark.parametrize('outcome,status',[('valid',200),('patient',403),('tenant',403),('missing',403),('unavailable',503)])
def test_metadata_patch_cannot_bypass_association_verification(env,signed,field,outcome,status):
    init=initiate(env,metadata()).json();verifier(env,outcome)
    response=env['client'].patch('/api/v1/clinical-tests/'+init['clinical_test_id'],json={field:'association-new'},
        headers={'Authorization':'Bearer '+env['token']()})
    assert response.status_code==status
    saved=env['db'].clinical_tests.find_one({})
    assert saved[field]==('association-new' if status==200 else None)
    assert len(signed)==1


def test_clearing_association_requires_no_fabricated_platform_approval(env,signed):
    verifier(env);init=initiate(env,metadata(case_id='case-test')).json()
    from app.services import associations
    env['monkeypatch'].setattr(associations,'association_verifier',None)
    response=env['client'].patch('/api/v1/clinical-tests/'+init['clinical_test_id'],json={'case_id':None},
        headers={'Authorization':'Bearer '+env['token']()})
    assert response.status_code==200 and env['db'].clinical_tests.find_one({})['case_id'] is None


@pytest.mark.parametrize('name,mime',[
    ('valid.pdf','application/pdf'),('photo.jpg','image/jpeg'),('photo.jpeg','image/jpeg'),
    ('photo.png','image/png'),('photo.heic','image/heic'),('VALID.PDF','application/pdf'),
    ('PHOTO.JPEG','IMAGE/JPEG'),('analítica.2026.pdf','application/pdf'),
    ('検査結果.pdf','application/pdf'),('examen..version2.pdf','application/pdf')])
def test_supported_extensions_case_unicode_and_safe_dots(env,signed,name,mime):
    assert initiate(env,metadata(file_name=name,mime_type=mime)).status_code==201
    assert len(signed)==1
    assert env['db'].clinical_tests.find_one({})['file']['mime_type']==mime.lower()


def test_unicode_normalization_preserves_legitimate_filename_and_replay(env,signed):
    name='análisis.pdf';body=metadata(file_name=unicodedata.normalize('NFD',name))
    first=initiate(env,body);second=initiate(env,{**body,'file_name':name})
    assert first.status_code==second.status_code==201 and first.json()==second.json()
    assert env['db'].clinical_tests.find_one({})['file']['original_name']==name and len(signed)==1


@pytest.mark.parametrize('name,mime',[
    ('report.exe','application/pdf'),('report.pdf','image/png'),('report.png','application/pdf'),
    ('report.exe.pdf','application/pdf'),('report.PDF.EXE','application/pdf'),('report.pdf','application/zip'),
    ('../report.pdf','application/pdf'),(r'C:\reports\report.pdf','application/pdf'),
    ('folder/report.pdf','application/pdf'),('report.pdf:stream','application/pdf'),
    ('report\x00.pdf','application/pdf'),('report\n.pdf','application/pdf'),
    ('report\u202eexe.pdf','application/pdf'),('report.pdf.','application/pdf'),
    ('report.pdf ','application/pdf'),('.pdf','application/pdf')])
def test_unsafe_or_incoherent_metadata_never_gets_a_signature(env,signed,name,mime):
    response=initiate(env,metadata(file_name=name,mime_type=mime))
    assert response.status_code==422
    assert not signed and env['db'].clinical_tests.count_documents({})==0
    assert 'signed_url' not in response.text


@pytest.mark.parametrize('changes,status',[
    ({'size_bytes':0},422),({'size_bytes':20*1024*1024+1},413),({'sha256':'z'*64},422)])
def test_size_and_sha_remain_enforced_before_signing(env,signed,changes,status):
    assert initiate(env,metadata(**changes)).status_code==status
    assert not signed and env['db'].clinical_tests.count_documents({})==0


def test_changed_metadata_on_retry_is_not_a_new_authorization(env,signed):
    body=metadata();assert initiate(env,body).status_code==201
    assert initiate(env,{**body,'file_name':'another.pdf'}).status_code==409
    assert initiate(env,{**body,'file_name':'another.exe'}).status_code==422
    assert len(signed)==1 and env['db'].clinical_tests.count_documents({})==1


def test_refresh_revalidates_existing_association_before_signing(env,signed):
    verifier(env); body=metadata(case_id='case-test'); init=initiate(env,body).json()
    verifier(env,'unavailable')
    response=env['client'].post('/api/v1/clinical-tests/uploads/'+init['upload_id']+'/refresh-url',
        json={'client_upload_id':body['client_upload_id'],'sha256':body['sha256']},
        headers={'Authorization':'Bearer '+env['token'](),'Idempotency-Key':'refresh-security-01'})
    assert response.status_code==503 and len(signed)==1
