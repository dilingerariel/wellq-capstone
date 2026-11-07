"""HTTP demonstration. PDF bytes MUST come from the real export endpoint."""
import base64
import hashlib
import io
import json
import time
import uuid
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from pypdf import PdfReader
from reportlab.pdfgen import canvas
from integration.guard import database, environment
from integration.examples import redact
from integration.tests.conftest import Context, output

ROOT=Path('/demo-output')


def synthetic_pdf(payload):
    data=io.BytesIO(); c=canvas.Canvas(data)
    c.setTitle('DEMOSTRACION SINTETICA - SIN DATOS REALES')
    c.setFont('Helvetica-Bold',14);c.drawString(36,800,'LABORATORIO FICTICIO WELLQ - DEMOSTRACION')
    c.setFont('Helvetica',10);c.drawString(36,780,'No es un documento clinico real. Valores de pruebas de software.')
    c.drawString(36,760,'Fecha de muestra: '+payload['collection_date'])
    y=730
    for panel in payload['panels']:
        c.setFont('Helvetica-Bold',10);c.drawString(36,y,panel['panel_code']);y-=18
        c.setFont('Helvetica',10)
        for m in panel['markers']:
            c.drawString(48,y,f"{m['raw_name']}: {m['value_raw']} {m['unit_raw']} (referencia de prueba)");y-=18
    # Same document content, machine annotation for the explicit content adapter.
    t=c.beginText(36,18);t.setFont('Helvetica',0.05);t.setTextRenderMode(3)
    t.textLine('WQINT:'+base64.b64encode(json.dumps(payload).encode()).decode());c.drawText(t)
    c.save();return data.getvalue()


class DemoContext(Context):
    def __init__(self,raw,folder):
        super().__init__(raw);self.folder=folder;folder.mkdir(parents=True,exist_ok=True);self.events=[]

    def req(self,method,path,**kwargs):
        response=super().req(method,path,**kwargs)
        self.events.append({'method':method,'path':path,'status':response.status_code,'response':redact(response.json())})
        return response

    def upload(self,payload,number):
        data=synthetic_pdf(payload);(self.folder/f'entrada-{number:02d}.pdf').write_bytes(data)
        body={'client_upload_id':uuid.uuid4().hex,'file_name':'documento-sintetico.pdf','mime_type':'application/pdf',
            'size_bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'test_type':'blood_test',
            'title':'DEMOSTRACION SINTETICA - NO USO CLINICO','test_date':payload['collection_date'],'ai_consent':True}
        r=self.req('POST','/clinical-tests/uploads/initiate',json=body);assert r.status_code==201
        init=r.json();r=self.client.put(init['upload']['signed_url'],content=data,headers=init['upload']['required_headers'])
        assert r.status_code==200;self.events.append({'method':'PUT','target':'authorized synthetic gateway (URL redacted)','status':200,'sha256':body['sha256'],'size_bytes':len(data)})
        r=self.req('POST','/clinical-tests/uploads/'+init['upload_id']+'/complete',json={k:body[k] for k in ('client_upload_id','sha256','size_bytes')})
        assert r.status_code==200
        for _ in range(180):
            r=self.req('GET','/clinical-tests/uploads/'+init['upload_id']+'/status');assert r.status_code==200
            if r.json()['local_file_can_be_deleted']:break
            assert r.json()['status'] not in ('rejected','failed');time.sleep(.2)
        assert r.json()['local_file_can_be_deleted'] is True
        ext=self.wait_ext(init)
        expected={m['marker_code']:float(m['value_raw']) for p in payload['panels'] for m in p['markers']}
        actual={m['marker_code']:m['value_canonical'] for p in ext['panels'] for m in p['markers']}
        assert expected==actual
        assert ext['extraction_meta']['model_id']=='integration-content-fixture'
        assert all(m['validation']['passed'] for p in ext['panels'] for m in p['markers'])
        return init,ext


def scenario(raw,name,incomplete=False):
    folder=ROOT/name;ctx=DemoContext(raw,folder)
    try:
        total=1 if incomplete else 4
        for n in range(total):
            day=(date.today()-timedelta(days=30*(total-n-1))).isoformat();payload=output(day=day)
            for panel in payload['panels']:
                for m in panel['markers']:
                    m['raw_name']='Sintetico '+m['marker_code']
                    if incomplete:m['reference']={'source':'document'}
                    if m['marker_code']=='glucose':m['value_raw']=str(90+n)
                    if not incomplete and m['marker_code']=='cholesterol_total':m['value_raw']=str(212+n)
                    if not incomplete and m['marker_code']=='ldl_cholesterol':m['value_raw']='138'
                    if not incomplete and m['marker_code']=='vitamin_d':m['value_raw']='22'
            init,ext=ctx.upload(payload,n+1)
            r=ctx.confirm(init,ext);assert r.status_code==200
            if n==total-1:
                correction={'marker_code':'glucose','value_raw':'94','unit_raw':'mg/dL','reason':'synthetic_demo_correction'}
                r=ctx.validate(init,validation_status='validated',marker_corrections=[correction],clinical_note='NOTA PRIVADA FICTICIA - NO EXPORTAR');assert r.status_code==200
                latest=ctx.req('GET','/clinical-tests/'+init['clinical_test_id']+'/extraction');assert latest.status_code==200
                assert latest.json()['status']=='clinically_validated'
                review=ctx.req('PATCH','/clinical-tests/'+init['clinical_test_id']+'/review',role='clinician',
                               json={'expected_version':ctx.req('GET','/clinical-tests/'+init['clinical_test_id'],role='clinician').json()['clinical_version'],'review_status':'reviewed','review_note':'NOTA DE REVISION PRIVADA FICTICIA'})
                assert review.status_code==200
                public=ctx.req('GET','/clinical-tests/'+init['clinical_test_id']);assert public.status_code==200
                assert 'NOTA DE REVISION PRIVADA' not in public.text
        series=ctx.req('GET',ctx.patient_url('markers?marker_codes=glucose'),role='clinician');assert series.status_code==200
        assert len(series.json()['series'][0]['points'])==total
        path=ctx.patient_url('lab-report');r=ctx.req('GET',path+'?include_series=true&include_snapshot=true',role='clinician');assert r.status_code==200
        (folder/'reporte-http.json').write_bytes(r.content);report=r.json()
        assert report['header']['patient_id']==ctx.patient
        if incomplete:
            assert report['score'] is None or report['score']['lab_index'] is None
            assert all(row['subscore'] is None for p in report['results']['panels'] for row in p['rows'])
        else:assert report['score']['lab_index'] is not None and len(report['score']['pillars'])==4
        assert report['header']['exams'][0]['review_status']=='reviewed'
        assert ctx.req('GET',path).status_code==403
        export_path=ctx.patient_url('lab-report/export');headers=ctx.headers('clinician',key='demo-export-'+uuid.uuid4().hex)
        assert ctx.req('POST',export_path,json={}).status_code==403
        for _ in range(3):
            r=ctx.req('POST',export_path,headers=headers,json={});assert r.status_code==200
            rec=r.json()
            if rec['status']=='ready':break
            time.sleep(1)
        assert rec['status']=='ready' and rec['download_url'] and rec['expires_at']
        downloaded=ctx.client.get(rec['download_url']);assert downloaded.status_code==200
        data=downloaded.content;assert data.startswith(b'%PDF-') and len(data)==rec['size_bytes']
        assert hashlib.sha256(data).hexdigest()==rec['sha256']
        pdf=PdfReader(io.BytesIO(data),strict=True);assert len(pdf.pages)>0 and not pdf.is_encrypted
        text='\n'.join(page.extract_text() for page in pdf.pages)
        assert ctx.patient in text and 'NOTA PRIVADA FICTICIA' not in text and 'NOTA DE REVISION PRIVADA' not in text
        url=urlsplit(rec['download_url']);assert ctx.client.get(url._replace(query='').geturl()).status_code==403
        replay=ctx.req('POST',export_path,headers=headers,json={});assert replay.status_code==200
        assert replay.json()['export_id']==rec['export_id'] and replay.json()['replayed']
        assert ctx.raw.lab_report_exports.count_documents({'client_id':ctx.tenant})==1
        events=list(raw.audit_events.find({'client_id':ctx.tenant},{'_id':0,'event':1,'resource':1,'actor_role':1,'occurred_at':1}))
        assert sum(e['event']=='lab_report_export' for e in events)==1
        (folder/'wellq-reporte-clinico-demo.pdf').write_bytes(data)
        (folder/'http-redactado.json').write_text(json.dumps(ctx.events,ensure_ascii=False,indent=2),encoding='utf-8')
        (folder/'auditoria-redactada.json').write_text(json.dumps(events,default=str,indent=2),encoding='utf-8')
        result={'scenario':name,'synthetic_only':True,'patient_id':ctx.patient,'clinician_id':ctx.doctor,'tenant':ctx.tenant,
            'pdf_pages':len(pdf.pages),'sha256':rec['sha256'],'size_bytes':len(data),'export_id':rec['export_id'],
            'http_export':True,'private_unsigned_get':403,'patient_export':403,'idempotent_replay':True,'measurements':total,
            'catalog_clinically_approved':False,'environment':'test','external_dependencies':'objects, AI and main scanner are explicit doubles',
            'incomplete_scenario_limit':'test exception remains enabled; null subscores caused by absent ranges, not E2E production gate' if incomplete else None}
        (folder/'resultado.json').write_text(json.dumps(result,indent=2),encoding='utf-8');return result
    finally:ctx.client.close()


def main():
    environment();ROOT.mkdir(parents=True,exist_ok=True);raw=database()
    assert not raw['__integration_control'].find_one({'_id':'faults'}),'Another integration fault test is active'
    results=[scenario(raw,'suficiente'),scenario(raw,'incompleto',True)]
    for name in ('wellq-reporte-clinico-demo.pdf','reporte-http.json'):(ROOT/name).write_bytes((ROOT/'suficiente'/name).read_bytes())
    (ROOT/'resultados-demo.json').write_text(json.dumps({'http_flow_passed':True,'visual_inspection':'pending human/agent image review','scenarios':results},indent=2),encoding='utf-8')
    print(json.dumps({'http_flow_passed':True,'scenarios':[{k:r[k] for k in ('scenario','pdf_pages','size_bytes')} for r in results]}))
