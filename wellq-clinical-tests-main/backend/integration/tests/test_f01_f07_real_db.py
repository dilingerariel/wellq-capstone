"""HTTP and state transitions use real API/Mongo; documents/AI/scanner are explicit doubles."""
import hashlib
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import pytest
from app.config import settings
from app.services.scoring import scoring_engine
from app.tenancy import TenantDatabase
from conftest import output, pdf


def test_f01_approved_test_exception_does_not_approve_history(ctx,monkeypatch):
    init,_=ctx.ready()
    marker=ctx.raw.clinical_markers.find_one({'client_id':ctx.tenant})
    assert marker['subscore_clinically_approved'] is False
    monkeypatch.setattr(settings,'ENVIRONMENT','production')
    monkeypatch.setattr(settings,'CATALOG_CLINICALLY_APPROVED',True)
    assert scoring_engine.published_subscore(marker) is None
    snap=ctx.raw.score_snapshots.find_one({'client_id':ctx.tenant})
    assert scoring_engine.snapshot_publishable(snap) is False


def test_f02_null_range_confirmed_without_invented_score(ctx):
    init,ext=ctx.ready(confirmed=False)
    r=ctx.confirm(init,ext,edits=[{'op':'update','marker_code':'glucose','value_raw':'90','unit_raw':'mg/dL','reference':{'high':100}}])
    assert r.status_code==200
    m=ctx.raw.clinical_markers.find_one({'client_id':ctx.tenant,'marker_code':'glucose'})
    assert m['value_canonical']==90 and m['subscore'] is None
    assert m['subscore_exclusion_reason']=='INCOMPLETE_REFERENCE_RANGE'
    snap=ctx.raw.score_snapshots.find_one({'client_id':ctx.tenant})
    assert {'marker_code':'glucose','reason':'INCOMPLETE_REFERENCE_RANGE'} in snap['excluded_markers']


def test_f03_invalid_effective_confidence_and_no_score(ctx):
    data=output(codes=['glucose']);data['panels'][0]['markers'][0]['unit_raw']='unknown-unit'
    init,ext=ctx.ready(data,confirmed=False)
    m=ext['panels'][0]['markers'][0]
    assert m['provider_confidence']['value']==.99 and m['confidence']['value']==0 and not m['validation']['passed']
    assert ctx.confirm(init,ext,acknowledged_marker_codes=['glucose']).status_code==200
    assert ctx.raw.clinical_markers.count_documents({'client_id':ctx.tenant})==0


def test_f04_document_reference_state_consistent_through_series(ctx):
    data=output(codes=['glucose']);data['panels'][0]['markers'][0]['reference']={'low':100,'high':150,'unit':'mg/dL'}
    init,ext=ctx.ready(data)
    assert ext['panels'][0]['markers'][0]['status']=='low'
    rep=ctx.req('GET',ctx.patient_url('markers?marker_codes=glucose'),role='clinician').json()
    point=rep['series'][0]['points'][0]
    assert point['reference']['low']==100 and point['status']=='low'


def test_f05_provider_future_date_failure_does_not_block_local_delete(ctx):
    data=output();data['collection_date']='2999-01-01'
    init=ctx.start(data)
    for _ in range(100):
        doc=ctx.raw.clinical_tests.find_one({'client_id':ctx.tenant,'clinical_test_id':init['clinical_test_id']})
        if doc.get('extraction',{}).get('status')=='extraction_failed':break
        time.sleep(.2)
    assert doc['extraction_job']['error_code']=='INVALID_CLINICAL_DATE'
    assert ctx.req('GET','/clinical-tests/'+init['clinical_test_id']+'/extraction').json()['detail']['code']=='INVALID_CLINICAL_DATE'
    assert ctx.req('GET','/clinical-tests/uploads/'+init['upload_id']+'/status').json()['local_file_can_be_deleted']


def test_f06_pending_download_persists_and_replays_once(ctx):
    ctx.ready();control=ctx.raw['__integration_control'];path=ctx.patient_url('lab-report/export');headers=ctx.headers('clinician')
    control.replace_one({'_id':'faults'},{'_id':'faults','signer_unavailable':True},upsert=True)
    first=ctx.req('POST',path,headers=headers,json={})
    assert first.status_code==200 and first.json()['status']=='download_pending' and first.json()['download_url'] is None
    control.delete_one({'_id':'faults'})
    replay=ctx.req('POST',path,headers=headers,json={})
    assert replay.status_code==200 and replay.json()['status']=='ready'
    assert replay.json()['export_id']==first.json()['export_id'] and replay.json()['replayed']
    assert ctx.raw.lab_report_exports.count_documents({'client_id':ctx.tenant})==1
    assert ctx.raw.audit_events.count_documents({'client_id':ctx.tenant,'event':'lab_report_export'})==1


def test_f07_discard_two_http_clients_one_domain_event(ctx):
    init,ext=ctx.ready(confirmed=False);key=uuid.uuid4().hex
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:ctx.confirm(init,ext,action='discard',key=key),range(2)))
    assert [r.status_code for r in results]==[200,200]
    assert results[0].json()==results[1].json()
    assert ctx.raw.audit_events.count_documents({'client_id':ctx.tenant,'event':'extraction_discarded'})==1
    conflict=ctx.confirm(init,ext,action='confirm',key=key)
    assert conflict.status_code==409


@pytest.mark.parametrize('fault',['checksum','mime','corrupt','size','magic'])
def test_document_verification_failure_never_authorizes_delete(ctx,fault):
    data=pdf(output()) if fault!='corrupt' else b'%PDF-invalid-synthetic-document'
    if fault=='magic':data=b'SYNTHETIC UNKNOWN DOCUMENT FORMAT'
    body={'client_upload_id':uuid.uuid4().hex,'file_name':'synthetic.pdf','mime_type':'application/pdf','size_bytes':len(data),
        'sha256':hashlib.sha256(data).hexdigest() if fault!='checksum' else '0'*64,'test_type':'blood_test','title':'SYNTHETIC','test_date':date.today().isoformat()}
    if fault=='size':body['size_bytes']+=1
    init=ctx.req('POST','/clinical-tests/uploads/initiate',json=body).json()
    required=init['upload']['required_headers']
    if fault=='mime':required['Content-Type']='image/png'
    assert ctx.client.put(init['upload']['signed_url'],content=data,headers=required).status_code==200
    done=ctx.req('POST','/clinical-tests/uploads/'+init['upload_id']+'/complete',json={k:body[k] for k in ['client_upload_id','sha256','size_bytes']})
    assert done.status_code==200
    for _ in range(100):
        status=ctx.req('GET','/clinical-tests/uploads/'+init['upload_id']+'/status').json()
        if status['status']=='rejected':break
        time.sleep(.2)
    assert status['status']=='rejected' and not status['local_file_can_be_deleted']
