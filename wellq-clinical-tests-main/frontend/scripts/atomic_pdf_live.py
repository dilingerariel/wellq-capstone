"""Real HTTP/replica-set races, isolated synthetic tenant, explicit storage double.

Runs a second loopback-only ASGI process in the owned test container. Barriers
wrap external effects and CAS boundaries only in this probe process. A different
uvicorn process performs real authenticated clinical writes while it is paused.
No hooks are installed in the application, image or production infrastructure.
"""
import uuid

PROBE = r'''
import copy,hashlib,json,sys,threading,time,uuid,urllib.request,urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta
from bson import json_util
from integration.bootstrap import configure
from integration.guard import database
from integration.adapters import object_path
configure()
from app.main import app
from app.database import mongodb
from app.tenancy import TenantDatabase
from app.routes import clinical_tests as routes
from app.services import report_export
import uvicorn
p=json.load(sys.stdin);raw=database();mongodb.db=raw;mongodb.client=raw.client
assert p['source_tenant'].startswith('synthetic-http-')
assert p['tenant'].startswith('synthetic-atomic-')
db=TenantDatabase(raw,p['tenant']);scope={'client_id':p['tenant']}
assert not raw.clinical_tests.count_documents(scope)
source=raw.clinical_tests.find_one({'client_id':p['source_tenant'],'title':'SYNTHETIC BROWSER UPLOAD'})
assert source and source['extraction']['extraction_id']
cid=str(uuid.uuid4());eid=str(uuid.uuid4())
doc=copy.deepcopy(source);doc.pop('_id');doc.update(client_id=p['tenant'],patient_id=p['patient'],clinical_test_id=cid,
    title='SYNTHETIC ATOMIC SOURCE',review={'status':'not_reviewed'},case_id=None,appointment_id=None)
for key in ('upload_id','client_upload_id','idempotency_key'):doc['upload'][key]=str(uuid.uuid4())
ext=copy.deepcopy(raw.clinical_test_extractions.find_one({'client_id':p['source_tenant'],'extraction_id':source['extraction']['extraction_id']}))
ext.pop('_id');ext.update(client_id=p['tenant'],patient_id=p['patient'],clinical_test_id=cid,extraction_id=eid)
doc['extraction']['extraction_id']=eid
db.clinical_tests.insert_one(doc);db.clinical_test_extractions.insert_one(ext)
for m in raw.clinical_markers.find({'client_id':p['source_tenant'],'clinical_test_id':source['clinical_test_id'],'invalidated_at':None}):
    m.pop('_id');m.update(client_id=p['tenant'],patient_id=p['patient'],clinical_test_id=cid,extraction_id=eid)
    db.clinical_markers.insert_one(m)
db.patient_access.insert_one({'patient_id':p['patient'],'authorised_clinicians':[p['clinician']]})
snapshots=list(raw.score_snapshots.find({'client_id':p['source_tenant'],'patient_id':source['patient_id']}))
assert snapshots,'Real historical snapshots required'
for s in snapshots:
    s.pop('_id');s.update(client_id=p['tenant'],patient_id=p['patient'],snapshot_id=str(uuid.uuid4()))
    db.score_snapshots.insert_one(s)
def snapshot_hash():
    return hashlib.sha256(json_util.dumps(list(raw.score_snapshots.find(scope).sort('_id',1)),sort_keys=True).encode()).hexdigest()
historical=snapshot_hash()
entered=threading.Event();release=threading.Event();mode='';calls=0;uploads=0;builds=0
oldbuild=routes._build_lab_report_pdf;oldstore=routes._store_export_pdf;oldsign=routes._export_response;oldfence=report_export.fence
def gate(phase):
    if mode==phase:
        entered.set()
        assert release.wait(12),'Controlled race did not release'
def build(*args):
    global builds
    builds+=1;gate('build')
    return oldbuild(*args)
def store(*args):
    global uploads
    if mode=='storage_failure':raise RuntimeError('Explicit synthetic storage failure')
    result=oldstore(*args);uploads+=1;gate('stored')
    return result
def sign(*args):
    if mode=='signer_failure':
        result=oldsign(*args);result.update(status='download_pending',download_url=None,expires_at=None,error_code='DOWNLOAD_URL_UNAVAILABLE')
        return result
    result=oldsign(*args);gate('signed')
    return result
def fence(*args):
    global calls
    calls+=1
    if calls==1:gate('reserve_fence')
    if calls==3:gate('publish_fence')
    return oldfence(*args)
routes._build_lab_report_pdf=build;routes._store_export_pdf=store;routes._export_response=sign;report_export.fence=fence
server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8001,lifespan='off',access_log=False,log_level='critical'))
thread=threading.Thread(target=server.run,daemon=True);thread.start()
for _ in range(100):
    if server.started:break
    time.sleep(.03)
assert server.started
base='/api/v1/patients/'+p['patient']+'/lab-report';checks=[];stage='start';diagnostic={}
def call(path,body=None,key=None,actor='clinician',port=8001,timeout=15):
    headers={'Authorization':'Bearer '+p['tokens'][actor],'Content-Type':'application/json'}
    if key:headers['Idempotency-Key']=key
    method='PATCH' if port==8000 else 'POST' if body is not None else 'GET'
    req=urllib.request.Request('http://127.0.0.1:'+str(port)+path,headers=headers,
        data=json.dumps(body).encode() if body is not None else None,method=method)
    try:r=urllib.request.urlopen(req,timeout=timeout)
    except urllib.error.HTTPError as error:r=error
    with r:return r.status,json.loads(r.read()),r.headers
def read():
    status,body,_=call(base+'?include_series=true&include_snapshot=true');assert status==200
    return body
def request():
    return {'window_months':12,'include_series':True,'expected_source_version':read()['source_version']}
def export(body,key,**kwargs):return call(base+'/export',body,key,**kwargs)
def record(key):return db.lab_report_exports.find_one({'idempotency_key':key})
def freshkey():return 'synthetic-atomic-'+uuid.uuid4().hex
def write(title=None):
    status,body,_=call('/api/v1/clinical-tests/'+cid,{'title':title or 'SYNTHETIC '+uuid.uuid4().hex},actor='patient',port=8000)
    assert status==200,'Real clinical writer failed'
def arm(phase):
    global mode,calls
    mode=phase;calls=0;entered.clear();release.clear()
def failed(result,key,codes=('EXPORT_SOURCE_CHANGED','RETRYABLE_CONFLICT')):
    global diagnostic
    status,body,_=result;diagnostic={'status':status,'code':body.get('detail',{}).get('code')}
    assert status==409 and diagnostic['code'] in codes
    assert 'download_url' not in body
    rec=record(key)
    assert rec is None or rec['state'] in ('stale','failed')
    assert db.audit_events.count_documents({'event':'lab_report_export_failed','export_id':rec['export_id'] if rec else None})>0
try:
    stage='normal and immutable same-key replay';body=request();key=freshkey();u=uploads
    first=export(body,key);assert first[0]==200 and first[1]['status']=='ready'
    assert first[1]['source_version']==body['expected_source_version'] and first[1]['verified_at']
    rec=record(key);data=object_path(rec['object_key']).read_bytes()
    assert data.startswith(b'%PDF-') and hashlib.sha256(data).hexdigest()==first[1]['sha256'] and len(data)==first[1]['size_bytes']
    replay=export(body,key);assert replay[0]==200 and replay[1]['replayed']
    for field in ('export_id','source_version','sha256','size_bytes','generated_at'):assert replay[1][field]==first[1][field]
    assert uploads==u+1 and db.lab_report_exports.count_documents({'idempotency_key':key})==1
    assert db.audit_events.count_documents({'event':'lab_report_export','export_id':rec['export_id']})==1
    checks+=['normal PDF SHA/size','same-key single object and success audit']
    stage='missing malformed and obsolete preconditions'
    assert export({},freshkey())[0]==428
    assert export({'expected_source_version':'invalid'},freshkey())[0]==422
    old=body;write();failed(export(old,freshkey()),'no-record')
    failed(export(old,key),key);checks+=['428 missing','422 malformed','409 obsolete and old PDF denied']
    stage='simultaneous same-key exports';arm('build');body=request();key=freshkey();u=uploads
    with ThreadPoolExecutor(2) as pool:
        owner=pool.submit(export,body,key)
        assert entered.wait(6)
        second=export(body,key)
        assert second[0]==409 and second[1]['detail']['code']=='EXPORT_IN_PROGRESS' and second[2]['Retry-After']=='1'
        release.set();winner=owner.result();assert winner[0]==200
    mode='';assert export(body,key)[1]['export_id']==winner[1]['export_id'] and uploads==u+1
    checks+=['concurrent same-key 200/409 then immutable replay']
    # Last pair pauses AFTER source read but BEFORE the actual conditional write.
    # The writer runs in a separate real ASGI process, so Mongo must reject a
    # stale snapshot even though the probe's event loop is blocked at the CAS.
    for phase in ('build','stored','signed','reserve_fence','publish_fence'):
        stage='clinical write at '+phase;arm(phase);body=request();key=freshkey()
        with ThreadPoolExecutor(2) as pool:
            future=pool.submit(export,body,key)
            assert entered.wait(6),'Barrier not reached'
            write();release.set();result=future.result()
        mode='';failed(result,key)
        if phase in ('stored','signed','publish_fence'):
            assert object_path(record(key)['object_key']).is_file()  # retained private orphan, no deletion
        checks.append('real clinical write rejected at '+phase)
    stage='monotonic ABA'
    original=read();body=request();key=freshkey();assert export(body,key)[0]==200
    write('SYNTHETIC B');write(original['header']['exams'][0]['title'])
    restored=read();assert restored['header']==original['header']
    assert restored['source_version']!=body['expected_source_version'];failed(export(body,key),key)
    checks.append('monotonic ABA blocks historical PDF')
    stage='storage failure terminal';arm('storage_failure');body=request();key=freshkey();u=uploads
    assert export(body,key)[0]==502 and record(key)['state']=='failed'
    mode='';failed(export(body,key),key,('EXPORT_ATTEMPT_FAILED',));assert uploads==u
    checks.append('storage failure audited; no automatic upload retry')
    stage='signer unavailable';arm('signer_failure');body=request();key=freshkey();u=uploads
    pending=export(body,key);assert pending[0]==200 and pending[1]['download_url'] is None and pending[1]['status']=='download_pending'
    mode='';assert export(body,key)[1]['export_id']==pending[1]['export_id'] and uploads==u+1
    checks.append('signer recovery reuses committed PDF')
    stage='HTTP timeout explicit reconnect';arm('build');body=request();key=freshkey();u=uploads
    with ThreadPoolExecutor(2) as pool:
        future=pool.submit(export,body,key,timeout=.2)
        assert entered.wait(6);time.sleep(.3)
        try:future.result();raise AssertionError('Expected transport timeout')
        except TimeoutError:pass
        release.set()
    mode=''
    for _ in range(100):
        if record(key)['state']=='committed':break
        time.sleep(.02)
    assert export(body,key)[0]==200 and uploads==u+1
    checks.append('HTTP timeout and explicit same-key reconnect')
    stage='pending lease expired';arm('build');body=request();key=freshkey()
    with ThreadPoolExecutor(2) as pool:
        future=pool.submit(export,body,key);assert entered.wait(6)
        db.lab_report_exports.update_one({'idempotency_key':key},{'$set':{'lease_until':datetime.utcnow()-timedelta(seconds=1)}})
        expired=export(body,key);failed(expired,key,('EXPORT_ATTEMPT_EXPIRED',))
        release.set();failed(future.result(),key)
    mode='';checks.append('expired lease cannot commit a late owner')
    stage='identity and expired session'
    for actor,status in (('unrelated',403),('other_patient',403),('expired',401)):
        assert export(request(),freshkey(),actor=actor)[0]==status
    # Retain frozen verified identity internally while explicitly model time
    # advancing beyond its expiry during CPU work; do not forge/re-sign JWTs.
    stage='expiry during generation';arm('build');body=request();key=freshkey()
    from types import SimpleNamespace
    real_clock=report_export.time
    with ThreadPoolExecutor(2) as pool:
        future=pool.submit(export,body,key);assert entered.wait(6)
        report_export.time=SimpleNamespace(time=lambda:real_clock.time()+901)
        release.set()
        assert future.result()[0]==401 and record(key)['state']=='failed'
    report_export.time=real_clock;mode=''
    checks+=['unrelated identity and patient denied','expired JWT denied','expiry boundary denies late publication (clock double)']
    stage='relationship revoked before URL';arm('signed');body=request();key=freshkey()
    with ThreadPoolExecutor(2) as pool:
        future=pool.submit(export,body,key);assert entered.wait(6)
        db.patient_access.update_one({'patient_id':p['patient']},{'$set':{'authorised_clinicians':[]}})
        release.set();denied=future.result();assert denied[0]==403 and 'download_url' not in denied[1]
    mode='';db.patient_access.update_one({'patient_id':p['patient']},{'$set':{'authorised_clinicians':[p['clinician']]}})
    assert snapshot_hash()==historical
    checks+=['revoked clinical relationship cannot publish link','all historical snapshots unchanged']
    print(json.dumps({'passed':True,'checks':checks,'database':'real authenticated owned Mongo replica set',
        'transport':'real loopback HTTP; separate ASGI clinical writer',
        'storage':'explicit signed filesystem double; real ReportLab PDF bytes',
        'snapshots_preserved':len(snapshots),'private_orphans_retained':True,'production_enabled':False}))
except Exception as error:
    print(json.dumps({'passed':False,'failed_check':stage,'exception':type(error).__name__,'diagnostic':diagnostic}))
finally:
    release.set();server.should_exit=True;thread.join(5)
'''


def check_atomic_pdf(session, fixture, api, container_python):
    tenant = 'synthetic-atomic-' + uuid.uuid4().hex
    patient = 'synthetic-atomic-patient-' + uuid.uuid4().hex
    clinician = 'synthetic-atomic-clinician-' + uuid.uuid4().hex
    def identity(role='clinician', resource=None, expired=False):
        return session(role, resource=resource or (clinician if role == 'clinician' else patient),
                       tenant=tenant, expired=expired,
                       permissions=['clinical:read', 'clinical:write', 'reports:export'],
                       capabilities=['report_export'])['accessToken']
    proof = container_python(api, PROBE, {
        'tenant': tenant, 'patient': patient, 'clinician': clinician, 'source_tenant': fixture['tenant'],
        'tokens': {'clinician': identity(), 'patient': identity('patient'), 'expired': identity(expired=True),
                   'unrelated': identity(resource='synthetic-unrelated'),
                   'other_patient': identity('patient', resource='synthetic-other-patient')},
    }, timeout=180)
    assert proof['passed'], 'Atomic PDF live proof failed: ' + str(proof)
    return proof
