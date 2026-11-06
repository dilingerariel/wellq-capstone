"""Observe documentary gaps over HTTP. Findings are NOT successful tests."""
import hashlib
import json
import uuid
from datetime import date
from pathlib import Path
from integration.guard import database
from integration.tests.conftest import Context, pdf, output


def main():
    raw=database();ctx=Context(raw);data=pdf(output());key='probe-'+uuid.uuid4().hex
    body={'client_upload_id':uuid.uuid4().hex,'file_name':'synthetic.exe','mime_type':'application/pdf',
        'size_bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'test_type':'blood_test',
        'title':'SYNTHETIC DOCUMENTARY PROBE','test_date':date.today().isoformat(),
        'notes':'synthetic note','case_id':'synthetic-case-without-verified-owner'}
    findings=[]
    def observe(code,requirement,response,**details):
        findings.append({'id':code,'requirement':requirement,'http_status':response.status_code,**details})
    try:
        response=ctx.req('POST','/clinical-tests/uploads/initiate',headers=ctx.headers(key=key),json=body)
        observe('G01','Verify case ownership before accepting association',response,
                accepted_unknown_case=response.status_code==201)
        observe('G02','Reject extension/MIME mismatch before signing upload',response,
                accepted_exe_filename_with_pdf_mime=response.status_code==201)
        assert response.status_code==201,'Probe setup changed; inspect observations without assuming acceptance'
        ct=response.json()['clinical_test_id'];path='/clinical-tests/'+ct
        before=raw.audit_events.count_documents({'client_id':ctx.tenant})
        changed=ctx.req('PATCH',path,json={'title':'SYNTHETIC CHANGED METADATA'})
        null=ctx.req('PATCH',path,json={'notes':None})
        observe('G03','PATCH null clears note; empty PATCH is invalid',null,
                note_after=null.json().get('notes'),empty_patch_http=ctx.req('PATCH',path,json={}).status_code)
        after=raw.audit_events.count_documents({'client_id':ctx.tenant})
        observe('G04','Metadata changes emit audit event',changed,audit_events_added=after-before,
                changed_title=changed.json().get('title'))
        first=ctx.req('PATCH',path+'/review',role='clinician',json={'review_status':'reviewed'})
        observe('G05','Only ready_for_review can be reviewed',first,upload_state='initiated')
        second_doctor='synthetic-second-'+uuid.uuid4().hex
        raw.patient_access.update_one({'client_id':ctx.tenant,'patient_id':ctx.patient},
            {'$addToSet':{'authorised_clinicians':second_doctor}})
        second=ctx.req('PATCH',path+'/review',headers=ctx.headers('clinician',identity=second_doctor),json={'review_status':'reviewed'})
        observe('G06','Another reviewer receives 409; reviewer and time are immutable',second,
                reviewer_replaced=second.json().get('review',{}).get('reviewed_by')==second_doctor,
                review_audit_events_added=raw.audit_events.count_documents({'client_id':ctx.tenant})-after)
        Path('/demo-output/sondas-brechas-http.json').write_text(json.dumps({'synthetic_only':True,
            'purpose':'Documentary gap observations, not passing tests','findings':findings},indent=2),encoding='utf-8')
        print('Documentary probes executed: 6 gaps observed; see local sondas-brechas-http.json. These are not approvals.')
    finally:ctx.client.close()
