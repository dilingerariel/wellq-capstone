"""Capture actual synthetic HTTP responses, redact local signed URLs."""
import json
import uuid
from pathlib import Path
from integration.guard import database
from integration.tests.conftest import Context


def redact(value):
    if isinstance(value,dict):
        return {k:('<redacted signed TEST gateway URL; not GCS>' if k in ('url','download_url','signed_url') and v else redact(v)) for k,v in value.items()}
    if isinstance(value,list):
        return [redact(v) for v in value]
    return value


def main():
    ctx=Context(database());init,ext=ctx.ready();samples=[]
    def capture(label,response):
        assert response.status_code in (200,403,422)
        samples.append({'label':label,'status':response.status_code,'response':redact(response.json())})
    capture('patient_document',ctx.req('GET','/clinical-tests/'+init['clinical_test_id']))
    capture('patient_extraction',ctx.req('GET','/clinical-tests/'+init['clinical_test_id']+'/extraction'))
    capture('clinician_marker_series',ctx.req('GET',ctx.patient_url('markers?marker_codes=glucose'),role='clinician'))
    capture('clinician_report',ctx.req('GET',ctx.patient_url('lab-report?include_series=true&include_snapshot=true'),role='clinician'))
    capture('patient_report_denied',ctx.req('GET',ctx.patient_url('lab-report')))
    capture('validation_error',ctx.req('POST','/clinical-tests/uploads/initiate',json={}))
    control=ctx.raw['__integration_control'];h=ctx.headers('clinician',key=uuid.uuid4().hex);path=ctx.patient_url('lab-report/export')
    try:
        control.replace_one({'_id':'faults'},{'_id':'faults','signer_unavailable':True},upsert=True)
        capture('download_pending',ctx.req('POST',path,headers=h,json={}))
        control.delete_one({'_id':'faults'})
        capture('download_ready_replay',ctx.req('POST',path,headers=h,json={}))
    finally:
        control.delete_one({'_id':'faults'})
    Path('/evidence/frontend-examples.json').write_text(json.dumps({'synthetic_only':True,
        'storage_and_ai':'explicit doubles, not GCS or external model','samples':samples},ensure_ascii=False,indent=2))
    print('8 real HTTP synthetic examples captured; no tokens or signed URLs saved')
