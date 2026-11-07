"""30 mapped historical cases: 28 real-Mongo/HTTP ports with declared doubles,
and two original pure functions previously misclassified as integration.
Security fixture in backend/tests is NOT disabled or imported.
"""
import copy
import hashlib
import importlib.util
import io
import time
import uuid
from datetime import date, timedelta
from pypdf import PdfReader
from app.tenancy import TenantDatabase
from app.services.scoring import scoring_engine
from conftest import output


def marker(body, code='hemoglobin'):
    return next(m for p in body['panels'] for m in p['markers'] if m['marker_code']==code)


def series(ctx, code='hemoglobin'):
    r=ctx.req('GET',ctx.patient_url('markers?marker_codes='+code),role='clinician')
    assert r.status_code==200
    return r.json()['series'][0]['points']


def score(ctx):
    r=ctx.req('GET',ctx.patient_url('lab-score?history=true'),role='clinician')
    assert r.status_code==200
    return r.json()


def rows(report):
    return [row for p in report['results']['panels'] for row in p['rows']]


def test_clinician_without_relationship_gets_403_everywhere_and_is_audited(ctx):
    init,_=ctx.ready();ct=init['clinical_test_id']; stranger='unrelated-'+uuid.uuid4().hex
    paths=[('GET',ctx.patient_url('lab-score')),('GET',ctx.patient_url('markers?marker_codes=hemoglobin')),
           ('GET',ctx.patient_url('lab-report')),('POST',ctx.patient_url('lab-report/export')),
           ('GET',ctx.patient_url('clinical-tests')),('GET','/clinical-tests/'+ct),('GET','/clinical-tests/'+ct+'/extraction')]
    for method,path in paths:
        r=ctx.req(method,path,headers=ctx.headers('clinician',identity=stranger),**({'json':{}} if method=='POST' else {}))
        assert r.status_code==403 and r.json()['detail']['code']=='NO_PATIENT_ACCESS'
    denied=list(ctx.raw.audit_events.find({'client_id':ctx.tenant,'event':'access_denied','patient_id':ctx.patient,'actor_id':stranger}))
    assert {'lab-score','markers','lab-report'}<={e['resource'] for e in denied}


def test_clinicians_with_relationship_have_access(ctx):
    ctx.ready();care='care-'+uuid.uuid4().hex
    ctx.raw.patient_access.update_one({'client_id':ctx.tenant,'patient_id':ctx.patient},{'$set':{'care_clinician_id':care}})
    for ident in (ctx.doctor,care):
        for resource in ('lab-score','lab-report','markers?marker_codes=hemoglobin'):
            assert ctx.req('GET',ctx.patient_url(resource),headers=ctx.headers('clinician',identity=ident)).status_code==200


def test_clinician_correction_reaches_series_and_report(ctx):
    init,_=ctx.ready()
    assert ctx.validate(init,marker_corrections=[{'marker_code':'hemoglobin','value_raw':'13','unit_raw':'g/dL'}]).status_code==200
    assert series(ctx)[0]['value']==13
    report=ctx.req('GET',ctx.patient_url('lab-report'),role='clinician').json()
    assert next(r for r in rows(report) if r['marker_code']=='hemoglobin')['value']==13


def test_invalid_corrections_are_rejected_and_nothing_changes(ctx):
    init,_=ctx.ready(output(codes=['hemoglobin']));before=series(ctx)[0]['value']
    good={'marker_code':'hemoglobin','value_raw':'13','unit_raw':'g/dL'}
    attempts=[([good,{'marker_code':'cholesterol_total','value_raw':'165','unit_raw':'mg/dL'}],'MARKER_NOT_IN_EXAM'),
              ([{'marker_code':'not_in_catalog','value_raw':'1','unit_raw':'mg/dL'}],'MARKER_NOT_IN_EXAM'),
              ([{**good,'unit_raw':'banana'}],'UNIT_NOT_SUPPORTED'),([good,good],'DUPLICATE_CORRECTION')]
    for corrections,code in attempts:
        r=ctx.validate(init,marker_corrections=corrections)
        assert r.status_code==422 and r.json()['detail']['code']=='INVALID_MARKER_CORRECTIONS'
        assert r.json()['detail']['errors'][0]['code']==code
        assert series(ctx)[0]['value']==before
    invalid=ctx.validate(init,validation_status='maybe')
    assert invalid.status_code==422 and invalid.json()['detail']['code']=='INVALID_INPUT' # Deliberate typed-request contract.
    assert ctx.validate(init,marker_corrections=[good]).status_code==200


def test_correction_is_reflected_in_extraction_panels(ctx):
    init,_=ctx.ready();before=series(ctx)[0]['value']
    r=ctx.validate(init,marker_corrections=[{'marker_code':'hemoglobin','value_raw':'13','unit_raw':'g/dL'}])
    assert r.status_code==200
    m=marker(r.json());assert m['value_canonical']==13 and m['edited_by']=='clinician' and m['edited_at'] and m['edited']
    assert m['original_value_canonical']==before
    patient=ctx.req('GET','/clinical-tests/'+init['clinical_test_id']+'/extraction')
    assert marker(patient.json())['value_canonical']==13
    assert len(series(ctx))==1 and series(ctx)[0]['value']==13


def test_clinical_rejection_does_not_fail_and_invalidates_markers(ctx):
    init,_=ctx.ready();assert len(series(ctx))==1
    r=ctx.validate(init,validation_status='rejected',marker_corrections=[])
    assert r.status_code==200 and r.json()['status']=='rejected' and series(ctx)==[]
    assert ctx.validate(init,marker_corrections=[]).status_code==409


def test_validation_without_corrections_does_not_recompute_score(ctx):
    init,_=ctx.ready();before=score(ctx)['current_snapshot']
    assert before['trigger']=='extraction_confirmed'
    assert ctx.validate(init,marker_corrections=[]).status_code==200
    after=score(ctx)
    assert after['current_snapshot']['snapshot_id']==before['snapshot_id'] and not after['history']


def test_complete_extraction_and_confirmation_flow(ctx):
    init=ctx.start();ext=ctx.wait_ext(init)
    assert ext['status']=='awaiting_confirmation' and ext['panels']
    r=ctx.confirm(init,ext);assert r.status_code==200 and r.json()['status']=='confirmed'
    assert len(series(ctx))==1 and score(ctx)['current_snapshot']['snapshot_id']


def test_proposal_block_is_immutable(ctx):
    init,ext=ctx.ready(confirmed=False);ident={'client_id':ctx.tenant,'clinical_test_id':init['clinical_test_id']}
    before=ctx.raw.clinical_test_extractions.find_one(ident)['proposal']
    r=ctx.confirm(init,ext,edits=[{'op':'update','marker_code':'hemoglobin','value_raw':'13','unit_raw':'g/dL'}])
    assert r.status_code==200
    after=ctx.raw.clinical_test_extractions.find_one(ident)
    assert after['proposal']==before and marker(after)['value_canonical']==13


def test_reprocess_creates_a_new_proposal_and_keeps_the_old_one(ctx):
    init,ext=ctx.ready(confirmed=False);ident={'client_id':ctx.tenant,'extraction_id':ext['extraction_id']}
    original=ctx.raw.clinical_test_extractions.find_one(ident)['proposal']
    assert ctx.confirm(init,ext,action='discard').status_code==200
    r=ctx.req('POST','/clinical-tests/'+init['clinical_test_id']+'/extraction/reprocess',json={})
    assert r.status_code==200 and r.json()['status']=='queued'
    new=ctx.wait_ext(init,previous=ext['extraction_id'])
    assert new['extraction_id']!=ext['extraction_id']
    old=ctx.raw.clinical_test_extractions.find_one(ident)
    assert old['proposal']==original and old['superseded_at'] is not None


def test_clinical_letter_is_not_applicable_but_downloadable(ctx):
    init=ctx.start(output(codes=[],kind='other'),title='Title intentionally ignored by provider')
    ext=ctx.wait_ext(init)
    assert ext['status']=='not_applicable' and not ext['panels']
    r=ctx.req('POST','/clinical-tests/'+init['clinical_test_id']+'/download-url')
    assert r.status_code==200 and ctx.client.get(r.json()['url']).content.startswith(b'%PDF')


def test_get_extraction_rules(ctx):
    # Initiated has no job yet, so the GET cannot race a fast worker.
    from conftest import pdf
    data=pdf(output());body={'client_upload_id':uuid.uuid4().hex,'file_name':'synthetic.pdf','mime_type':'application/pdf',
        'size_bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'test_type':'blood_test','title':'SYNTHETIC','test_date':date.today().isoformat()}
    started=ctx.req('POST','/clinical-tests/uploads/initiate',json=body).json()
    r=ctx.req('GET','/clinical-tests/'+started['clinical_test_id']+'/extraction')
    assert r.status_code==409 and r.json()['detail']['code']=='EXTRACTION_NOT_READY'
    init,ext=ctx.ready(confirmed=False);path='/clinical-tests/'+init['clinical_test_id']+'/extraction'
    assert ctx.req('GET',path,role='clinician').status_code==409
    assert ctx.confirm(init,ext,edits=[{'op':'update','marker_code':'hemoglobin','value_raw':'13.5','unit_raw':'g/dL'}]).status_code==200
    m=marker(ctx.req('GET',path,role='clinician').json());assert m['edited'] and m['edited_by']=='patient'


def test_confirm_rules_state_idempotency_and_summary(ctx):
    init,ext=ctx.ready(confirmed=False);key=uuid.uuid4().hex
    edits=[{'op':'update','marker_code':'hemoglobin','value_raw':'13.5','unit_raw':'g/dL'}]
    first=ctx.confirm(init,ext,key=key,edits=edits);assert first.status_code==200
    conf=first.json()['confirmation'];assert conf['edits_applied']==[{'op':'update','marker_code':'hemoglobin'}]
    assert conf['score_snapshot_id'] and 'idempotency_key' not in conf
    replay=ctx.confirm(init,ext,key=key,edits=edits)
    assert replay.status_code==200 and replay.json()['confirmation']['score_snapshot_id']==conf['score_snapshot_id']
    assert ctx.confirm(init,ext,edits=edits).status_code==409
    assert not score(ctx)['history']


def test_value_implausible_is_rejected(ctx):
    init,ext=ctx.ready(confirmed=False)
    r=ctx.confirm(init,ext,edits=[{'op':'update','marker_code':'hemoglobin','value_raw':'9999','unit_raw':'g/dL'}])
    assert r.status_code==422 and r.json()['detail']['code']=='VALUE_IMPLAUSIBLE'


def test_reprocess_rules(ctx):
    init,ext=ctx.ready(confirmed=False);path='/clinical-tests/'+init['clinical_test_id']+'/extraction/reprocess'
    assert ctx.req('POST',path,json={}).json()['detail']['code']=='REPROCESS_NOT_ALLOWED'
    assert ctx.confirm(init,ext,action='discard').status_code==200
    key=uuid.uuid4().hex;r=ctx.req('POST',path,headers=ctx.headers(key=key),json={})
    assert r.status_code==200 and r.json()['status']=='queued'
    assert ctx.req('POST',path,headers=ctx.headers(key=key),json={}).status_code==200
    new=ctx.wait_ext(init,previous=ext['extraction_id']);assert ctx.confirm(init,new).status_code==200
    assert ctx.req('POST',path,json={}).json()['detail']['code']=='CONFIRMATION_REQUIRED'
    assert ctx.req('POST',path,json={'confirm_reprocess_confirmed':True}).status_code==200
    assert series(ctx)==[]


def test_reprocess_limit_per_exam(ctx):
    init,ext=ctx.ready(confirmed=False);path='/clinical-tests/'+init['clinical_test_id']+'/extraction/reprocess'
    for _ in range(5):
        assert ctx.confirm(init,ext,action='discard').status_code==200
        assert ctx.req('POST',path,json={}).status_code==200
        ext=ctx.wait_ext(init,previous=ext['extraction_id'])
    assert ctx.confirm(init,ext,action='discard').status_code==200
    r=ctx.req('POST',path,json={})
    assert r.status_code==429 and r.json()['detail']['code']=='RATE_LIMITED'


def test_endpoints_5_to_11_lifecycle(ctx):
    init,_=ctx.ready();path='/clinical-tests/'+init['clinical_test_id']
    assert any(x['clinical_test_id']==init['clinical_test_id'] for x in ctx.req('GET','/clinical-tests').json()['items'])
    assert ctx.req('GET',path).json()['patient_id']==ctx.patient
    edit=ctx.req('PATCH',path,json={'title':'SYNTHETIC EDIT','notes':'synthetic note'})
    assert edit.status_code==200 and edit.json()['title']=='SYNTHETIC EDIT' and edit.json()['notes']=='synthetic note'
    down=ctx.req('POST',path+'/download-url');assert down.status_code==200
    assert down.json()['file_name']=='synthetic.pdf'
    assert ctx.req('GET',ctx.patient_url('clinical-tests'),role='clinician').status_code==200
    review=ctx.req('PATCH',path+'/review',role='clinician',json={'review_status':'reviewed','review_note':'SYNTHETIC PRIVATE','expected_version':ctx.req('GET',path,role='clinician').json()['clinical_version']})
    assert review.status_code==200 and review.json()['review']['reviewed_by']==ctx.doctor
    assert 'SYNTHETIC PRIVATE' not in ctx.req('GET',path).text
    locked=ctx.req('PATCH',path,json={'title':'forbidden'})
    assert locked.status_code==409 and locked.json()['detail']['code']=='ALREADY_REVIEWED'
    assert ctx.req('DELETE',path).json()['status']=='deleted'
    assert ctx.req('GET',path).status_code==404


def test_lab_report_endpoint_19(ctx):
    first,_=ctx.ready(day=(date.today()-timedelta(days=15)).isoformat());second,_=ctx.ready()
    rep=ctx.req('GET',ctx.patient_url('lab-report?clinical_test_id='+second['clinical_test_id']),role='clinician').json()
    assert rep['header']['mode']=='exam' and rep['score']['lab_index']>0
    rr=rows(rep);assert rr and rr[0]['reference']['source']
    delta=next(r['delta'] for r in rr if r['delta'])
    assert delta['previous_clinical_test_id']==first['clinical_test_id']
    assert all(k in delta for k in ['absolute','percent','previous_value','previous_measured_on','previous_clinical_test_id'])
    assert set(rep['score']['pillars'])=={'cardio','bone','muscle','joint'}
    assert 'contributions' not in rep['score']['pillars']['cardio'] and rep['longitudinal'] is None
    agg=ctx.req('GET',ctx.patient_url('lab-report?include_snapshot=true&include_series=true'),role='clinician').json()
    assert agg['header']['mode']=='aggregate'
    codes=[r['marker_code'] for r in rows(agg)];assert len(codes)==len(set(codes))
    assert agg['score']['pillars']['cardio']['contributions'] and len(agg['longitudinal']['pillar_series'])>=2
    assert all(len(s['points'])>=2 for s in agg['longitudinal']['marker_series'])
    assert ctx.req('GET',ctx.patient_url('lab-report')).status_code==403


def test_lab_report_validation_and_empty(ctx):
    assert ctx.req('GET',ctx.patient_url('lab-report?clinical_test_id=missing'),role='clinician').status_code==404
    assert ctx.req('GET',ctx.patient_url('lab-report?window_months=0'),role='clinician').status_code==422
    rep=ctx.req('GET',ctx.patient_url('lab-report'),role='clinician').json()
    assert rep['score'] is None and rep['flags']==[] and rep['results']['panels']==[]


def test_export_lab_report_endpoint_20(ctx):
    ctx.ready();path=ctx.patient_url('lab-report/export');headers=ctx.headers('clinician',key=uuid.uuid4().hex)
    first=ctx.req('POST',path,headers=headers,json={});assert first.status_code==200
    exp=first.json();assert exp['status']=='ready' and not exp['replayed'] and exp['size_bytes']>0 and len(exp['sha256'])==64
    data=ctx.client.get(exp['download_url']).content
    assert data.startswith(b'%PDF') and len(data)==exp['size_bytes'] and hashlib.sha256(data).hexdigest()==exp['sha256']
    text='\n'.join(p.extract_text() for p in PdfReader(io.BytesIO(data)).pages)
    assert ctx.patient in text and ctx.doctor in text and 'no constituye un diagnóstico' in text
    replay=ctx.req('POST',path,headers=headers,json={}).json();assert replay['export_id']==exp['export_id'] and replay['replayed']
    assert ctx.req('POST',path,headers=headers,json={'window_months':6}).status_code==409
    assert ctx.req('POST',path,role='clinician',json={}).json()['export_id']!=exp['export_id']
    assert ctx.req('POST',path,json={}).status_code==403


def test_export_lab_report_validation(ctx):
    path=ctx.patient_url('lab-report/export');h=ctx.headers('clinician');h.pop('Idempotency-Key')
    assert ctx.req('POST',path,headers=h,json={}).status_code==422
    assert ctx.req('POST',path,role='clinician',json={'clinical_test_id':'missing'}).status_code==404
    assert ctx.req('POST',path,role='clinician',json={'window_months':0}).status_code==422


def test_marker_series_endpoint_17(ctx):
    init,_=ctx.ready()
    result=ctx.req('GET',ctx.patient_url('markers?marker_codes=hemoglobin,unknown'),role='clinician').json()
    assert result['patient_id']==ctx.patient and result['only_confirmed']
    assert [s['marker_code'] for s in result['series']]==['hemoglobin','unknown']
    assert result['series'][1]['points']==[]
    point=result['series'][0]['points'][0]
    assert point['clinical_test_id']==init['clinical_test_id']
    assert all(k in point for k in ['measured_on','value','unit','reference','status','subscore','clinical_test_id'])
    assert ctx.req('GET',ctx.patient_url('markers?marker_codes=hemoglobin&from=2999-01-01'),role='clinician').json()['series'][0]['points']==[]
    assert ctx.req('GET',ctx.patient_url('markers?marker_codes=hemoglobin')).status_code==403


def test_marker_series_validation(ctx):
    for params in ['marker_codes='+','.join('m'+str(i) for i in range(21)), 'marker_codes=hemoglobin&from=yesterday', '']:
        assert ctx.req('GET',ctx.patient_url('markers?'+params),role='clinician').status_code==422


def test_bulk_recompute_dry_run_vs_apply(ctx):
    from scripts.recompute_scoring import run_bulk_recompute
    ctx.ready();db=TenantDatabase(ctx.raw,ctx.tenant)
    count=db.score_snapshots.count_documents({'patient_id':ctx.patient})
    run_bulk_recompute(db,apply=False,target_patient_id=ctx.patient)
    assert db.score_snapshots.count_documents({'patient_id':ctx.patient})==count
    run_bulk_recompute(db,apply=True,target_patient_id=ctx.patient)
    assert db.score_snapshots.count_documents({'patient_id':ctx.patient})==count+1
    after=score(ctx);assert after['current_snapshot']['trigger']=='recompute' and len(after['history'])==count


def test_full_scoring_flow_and_endpoint_18(ctx):
    init,_=ctx.ready();before=score(ctx)['current_snapshot']
    assert before['lab_index'] is not None and len(before['pillars'])==4
    assert ctx.validate(init,marker_corrections=[{'marker_code':'hemoglobin','value_raw':'13','unit_raw':'g/dL'}]).status_code==200
    after=score(ctx);assert after['current_snapshot']['trigger']=='clinician_correction' and after['history']
    assert ctx.req('GET',ctx.patient_url('lab-score')).status_code==403


def test_lab_score_no_score_available(ctx):
    result=ctx.req('GET',ctx.patient_url('lab-score'),role='clinician')
    assert result.status_code==404 and result.json()['detail']['code']=='NO_SCORE_AVAILABLE'


def original_pure(name):
    spec=importlib.util.spec_from_file_location('original_reference','/historical-reference.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    getattr(mod,name)()


def test_same_input_gives_same_output():
    original_pure('test_same_input_gives_same_output')


def test_subscore_is_always_between_0_and_100():
    original_pure('test_subscore_is_always_between_0_and_100')


def test_recomputing_with_the_same_inputs_gives_the_same_score(ctx):
    init,_=ctx.ready();before=score(ctx)['current_snapshot']
    assert ctx.validate(init,marker_corrections=[{'marker_code':'hemoglobin','value_raw':'14.2','unit_raw':'g/dL'}]).status_code==200
    after=score(ctx);current=after['current_snapshot'];previous=after['history'][0]
    assert current['snapshot_id']!=previous['snapshot_id'] and current['trigger']=='clinician_correction'
    for field in ['lab_index','base_score','penalty_applied','scoring_version','catalog_version']:
        assert current[field]==previous[field]
    for name,pillar in current['pillars'].items():
        for field in ['score','coverage','confidence','status','contributions']:
            assert pillar[field]==previous['pillars'][name][field]


def test_full_upload_flow(ctx):
    init=ctx.start(ai=False)
    for _ in range(100):
        result=ctx.req('GET','/clinical-tests/uploads/'+init['upload_id']+'/status')
        if result.json()['local_file_can_be_deleted']:break
        time.sleep(.2)
    assert result.json()['status']=='ready_for_review' and result.json()['local_file_can_be_deleted']
    doc=ctx.raw.clinical_tests.find_one({'client_id':ctx.tenant,'clinical_test_id':init['clinical_test_id']})
    assert doc['file']['verified_at'] and doc['file']['generation'] and doc['extraction']['status']=='not_applicable'
