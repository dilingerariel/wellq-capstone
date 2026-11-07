"""Synthetic clinician fixtures and HTTP assertions. Never used by application code."""
import base64
import json

CLONE = """
import copy,json,sys,uuid
from integration.guard import database
p=json.load(sys.stdin);db=database()
source=db.clinical_tests.find_one({'client_id':p['tenant'],'title':'SYNTHETIC BROWSER UPLOAD'})
assert source and source['extraction']['status']=='confirmed'
ext=db.clinical_test_extractions.find_one({'client_id':p['tenant'],'extraction_id':source['extraction']['extraction_id']})
assert ext['status']=='confirmed'
for name,title in [('reject','SYNTHETIC CLINICAL REJECTION'),('race','SYNTHETIC CLINICAL CONCURRENCY')]:
 d=copy.deepcopy(source);d.pop('_id');d['clinical_test_id']=p[name];d['title']=title
 for k in ['upload_id','client_upload_id','idempotency_key']:d['upload'][k]=str(uuid.uuid4())
 e=copy.deepcopy(ext);e.pop('_id');e['clinical_test_id']=p[name];e['extraction_id']=str(uuid.uuid4());d['extraction']['extraction_id']=e['extraction_id']
 db.clinical_tests.insert_one(d);db.clinical_test_extractions.insert_one(e)
 for marker in db.clinical_markers.find({'client_id':p['tenant'],'clinical_test_id':source['clinical_test_id'],'invalidated_at':None}):
  marker.pop('_id');marker['clinical_test_id']=p[name];marker['extraction_id']=e['extraction_id'];db.clinical_markers.insert_one(marker)
db.patient_access.update_one({'client_id':p['tenant'],'patient_id':p['patient']},{'$addToSet':{'authorised_clinicians':p['second_clinician']}})
print(json.dumps({'synthetic_clones':2}))
"""

RACE = """
import copy,json,sys,uuid,urllib.request,urllib.error
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from integration.guard import database
p=json.load(sys.stdin);db=database();tenant={'client_id':p['tenant']}
def call(cid,path,body=None,actor=0):
 req=urllib.request.Request('http://127.0.0.1:8000/api/v1/clinical-tests/'+cid+path,data=json.dumps(body).encode() if body is not None else None,headers={'Authorization':'Bearer '+p['tokens'][actor],'Content-Type':'application/json'},method=('PATCH' if path=='/review' else 'POST') if body is not None else 'GET')
 try:r=urllib.request.urlopen(req,timeout=20)
 except urllib.error.HTTPError as e:r=e
 with r:return r.status,json.loads(r.read())
def version(cid):
 status,doc=call(cid,'');assert status==200
 status,ext=call(cid,'/extraction');assert status==200 and ext['clinical_version']==doc['clinical_version']
 return doc['clinical_version']
def clone():
 d=copy.deepcopy(db.clinical_tests.find_one({**tenant,'clinical_test_id':p['race']}));d.pop('_id');cid=str(uuid.uuid4());d['clinical_test_id']=cid
 for k in ['upload_id','client_upload_id','idempotency_key']:d['upload'][k]=str(uuid.uuid4())
 e=copy.deepcopy(db.clinical_test_extractions.find_one({**tenant,'extraction_id':d['extraction']['extraction_id']}));e.pop('_id');e['extraction_id']=str(uuid.uuid4());e['clinical_test_id']=cid
 d['extraction']['extraction_id']=e['extraction_id'];db.clinical_tests.insert_one(d);db.clinical_test_extractions.insert_one(e)
 for m in db.clinical_markers.find({**tenant,'clinical_test_id':p['race']}):
  m.pop('_id');m['clinical_test_id']=cid;m['extraction_id']=e['extraction_id'];db.clinical_markers.insert_one(m)
 return cid
def fingerprint(cid):
 d=db.clinical_tests.find_one({**tenant,'clinical_test_id':cid});eid=d['extraction']['extraction_id']
 return (d,db.clinical_test_extractions.find_one({**tenant,'extraction_id':eid}),list(db.clinical_markers.find({**tenant,'clinical_test_id':cid})),list(db.clinical_result_history.find({**tenant,'clinical_test_id':cid})),list(db.audit_events.find({**tenant,'resource_id':{'$in':[cid,eid]}})),list(db.score_snapshots.find(tenant)))
def race(cid,operations):
 gate=Barrier(2);v=version(cid)
 def run(args):
  actor,(path,body)=args;gate.wait();return call(cid,path,{**body,'expected_version':v},actor)[0]
 with ThreadPoolExecutor(max_workers=2) as pool:result=sorted(pool.map(run,enumerate(operations)))
 assert result==[200,409], 'Concurrent operations must have one winner'
 return result
validate=lambda value:{'validation_status':'validated','marker_corrections':[{'marker_code':'glucose','value_raw':str(value),'unit_raw':'mg/dL'}]}
cross=clone();mixed=clone();stale=clone();legacy=clone();invalid=clone();superseded=clone()
review=race(p['race'],[('/review',{'review_note':'SYNTHETIC RACE A'}),('/review',{'review_note':'SYNTHETIC RACE B'})])
validation=race(p['race'],[('/extraction/validate',validate(97)),('/extraction/validate',validate(98))])
cross_result=race(cross,[('/review',{'review_note':'SYNTHETIC CROSS REVIEW'}),('/extraction/validate',validate(99))])
mixed_result=race(mixed,[('/extraction/validate',validate(100)),('/extraction/validate',{'validation_status':'rejected'})])
# Each race has exactly the successful operation's audit/history, never loser's writes.
for cid,expected_events in [(p['race'],2),(cross,1),(mixed,1)]:
 d,e,markers,history,audits,_=fingerprint(cid)
 events=[a['event'] for a in audits if a['event'] in ('clinical_test_reviewed','clinical_validation','clinical_rejection')]
 assert len(events)==expected_events
 for event in audits:
  if event['event']=='clinical_test_reviewed':assert event['actor_id']=='synthetic-http-clinician:'+d['review']['reviewed_by']
  if event['event'] in ('clinical_validation','clinical_rejection','marker_correction'):assert event['actor_id']=='synthetic-http-clinician:'+e['confirmation']['validated_by']
 corrected='clinical_validation' in events
 assert len(history)==(1 if corrected else 0)
 assert sum(a['event']=='marker_correction' for a in audits)==(1 if corrected else 0)
 assert e['proposal']['panels'][0]['markers'][0]['value_raw']=='90' and e['confirmed']['panels'][0]['markers'][0]['value_raw']=='95'
# An authorized replay retains immutable reviewer and does not duplicate audit.
v=version(stale);review_body={'review_note':'SYNTHETIC IDEMPOTENT','expected_version':v}
assert call(stale,'/review',review_body)[0]==200
before=fingerprint(stale)
assert call(stale,'/review',review_body)[0]==200
assert call(stale,'/review',review_body,1)[0]==409
assert call(stale,'/review',{**review_body,'review_note':'changed'})[0]==409
assert call(stale,'/extraction/validate',{**validate(101),'expected_version':v})[0]==409
assert fingerprint(stale)==before
# Old clients fail closed with 428 on new writes; malformed tokens fail validation.
for path,body in [('/review',{}),('/extraction/validate',validate(102))]:
 before=fingerprint(legacy)
 assert call(legacy,path,body)[0]==428
 assert call(legacy,path,{**body,'expected_version':'invalid'})[0]==422
 assert fingerprint(legacy)==before
# Valid first correction plus invalid second correction must roll back everything.
before=fingerprint(invalid);body=validate(103);body['expected_version']=version(invalid)
body['marker_corrections'].append({'marker_code':'unknown-synthetic-marker','value_raw':'5','unit_raw':'mg/dL'})
assert call(invalid,'/extraction/validate',body)[0]==422
assert fingerprint(invalid)==before
# A replacement confirmed extraction must not accept the old snapshot's operation.
v=version(superseded);d=db.clinical_tests.find_one({**tenant,'clinical_test_id':superseded});e=db.clinical_test_extractions.find_one({**tenant,'extraction_id':d['extraction']['extraction_id']})
e.pop('_id');e['extraction_id']=str(uuid.uuid4());db.clinical_test_extractions.insert_one(e)
db.clinical_tests.update_one({**tenant,'clinical_test_id':superseded},{'$set':{'extraction.extraction_id':e['extraction_id']}})
before=fingerprint(superseded)
assert call(superseded,'/extraction/validate',{**validate(104),'expected_version':v})[0]==409
assert fingerprint(superseded)==before
# Re-reading permits the distinct next operation, with a new version.
assert call(stale,'/extraction/validate',{**validate(105),'expected_version':version(stale)})[0]==200
print(json.dumps({'concurrent_review_statuses':review,'concurrent_validation_statuses':validation,'concurrent_review_validation_statuses':cross_result,'concurrent_correction_rejection_statuses':mixed_result,'same_version_one_winner':True,'authorized_review_replay_once':True,'stale_and_superseded_rejected':True,'legacy_missing_version_428':True,'invalid_batch_no_partial_writes':True,'audit_history_and_snapshots_consistent':True,'audit_actor_matches_winner':True}))
"""

VERIFY = """
import json,sys
from integration.guard import database
p=json.load(sys.stdin);db=database()
d=db.clinical_tests.find_one({'client_id':p['tenant'],'title':'SYNTHETIC BROWSER UPLOAD'})
assert d['review']['reviewed_by']==p['clinician'] and d['review']['private_note']=='SYNTHETIC PRIVATE REVIEW'
ext=db.clinical_test_extractions.find_one({'client_id':p['tenant'],'extraction_id':d['extraction']['extraction_id']})
assert ext['status']=='clinically_validated' and ext['confirmation']['validation_note']=='SYNTHETIC CLINICAL NOTE'
assert ext['proposal']['panels'][0]['markers'][0]['value_raw']=='90'
assert ext['confirmed']['panels'][0]['markers'][0]['value_raw']=='95'
m=db.clinical_markers.find_one({'client_id':p['tenant'],'clinical_test_id':d['clinical_test_id'],'invalidated_at':None})
assert m['value_raw']=='96' and m['edited_by']=='clinician' and m['original_value_canonical']==90
h=db.clinical_result_history.find_one({'client_id':p['tenant'],'clinical_test_id':d['clinical_test_id']})
assert h['before']['value_raw']=='95' and h['correction']['value_canonical']==96
assert db.audit_events.count_documents({'client_id':p['tenant'],'resource_id':d['clinical_test_id'],'event':'clinical_test_reviewed'})==1
assert db.audit_events.count_documents({'client_id':p['tenant'],'resource_id':ext['extraction_id'],'event':'clinical_validation'})==1
rej=db.clinical_tests.find_one({'client_id':p['tenant'],'clinical_test_id':p['reject']})
assert rej['extraction']['status']=='rejected'
assert db.clinical_markers.count_documents({'client_id':p['tenant'],'clinical_test_id':p['reject'],'invalidated_at':None})==0
assert db.audit_events.count_documents({'client_id':p['tenant'],'resource_id':rej['extraction']['extraction_id'],'event':'clinical_rejection'})==1
race=db.clinical_tests.find_one({'client_id':p['tenant'],'clinical_test_id':p['race']})
assert db.audit_events.count_documents({'client_id':p['tenant'],'resource_id':p['race'],'event':'clinical_test_reviewed'})==1
assert db.audit_events.count_documents({'client_id':p['tenant'],'resource_id':race['extraction']['extraction_id'],'event':'clinical_validation'})==1
print(json.dumps({'review_private_note_persisted':True,'clinical_note_persisted':True,'correction_persisted':True,'proposal_and_patient_confirmation_preserved':True,'history_preserved':True,'rejection_invalidated_markers':True,'single_review_validation_and_rejection_audits':True}))
"""

def check_clinical(forward, session, fixture, api, container_python):
    grants=['clinical:read','clinical:review','extractions:validate']
    own=session('clinician',permissions=grants)
    other=session('clinician',resource=fixture['second_clinician'],permissions=grants)
    results=[]
    def call(path,who,body,method,expected,label):
        headers={'Authorization':'Bearer '+who['accessToken'],'Content-Type':'application/json'}
        r=forward(path,headers,method,json.dumps(body).encode() if body is not None else None)
        assert r['status']==expected,label
        results.append({'check':label,'status':r['status']})
        return r
    original=forward('/api/v1/clinical-tests?limit=100',{'Authorization':'Bearer '+session()['accessToken']})
    docs=json.loads(base64.b64decode(original['body']))['items']
    identity=next(d['clinical_test_id'] for d in docs if d['title']=='SYNTHETIC BROWSER UPLOAD')
    base='/api/v1/clinical-tests/'+identity
    for suffix,method,body in [('/review','PATCH',{'review_note':'SYNTHETIC PRIVATE REVIEW'}),('/extraction/validate','POST',{'validation_status':'validated'})]:
        for label,who,status in [('missing-scope',session('clinician'),403),('patient-role',session(permissions=grants),403),('unrelated',session('clinician',resource='synthetic-unrelated',permissions=grants),403),('other-tenant',session('clinician',tenant='synthetic-other-tenant',permissions=grants),404),('expired',session('clinician',permissions=grants,expired=True),401)]:
            call(base+suffix,who,body,method,status,label+suffix)
    call(base+'/review',own,{'review_note':'SYNTHETIC PRIVATE REVIEW'},'PATCH',200,'same-reviewer-replay')
    call(base+'/review',own,{'review_note':'changed'},'PATCH',409,'immutable-review-note')
    call(base+'/review',other,{'review_note':'SYNTHETIC PRIVATE REVIEW'},'PATCH',409,'immutable-reviewer')
    call(base+'/extraction/validate',own,{'validation_status':'validated'},'POST',409,'validation-not-idempotent')
    call('/api/v1/clinical-tests/'+fixture['reject']+'/extraction/validate',own,{'validation_status':'rejected'},'POST',409,'rejection-not-idempotent')
    for suffix in ['', '/extraction']:
        r=forward(base+suffix,{'Authorization':'Bearer '+session()['accessToken']})
        text=base64.b64decode(r['body']).decode()
        assert r['status']==200 and 'SYNTHETIC PRIVATE REVIEW' not in text and 'SYNTHETIC CLINICAL NOTE' not in text
    reject_path='/api/v1/clinical-tests/'+fixture['reject']+'/extraction'
    for label,who,status in [('rejected-authorized',own,200),('rejected-other-clinician',other,200),('rejected-unrelated',session('clinician',resource='synthetic-unrelated',permissions=grants),403),('rejected-other-patient',session(resource='synthetic-other-patient'),403),('rejected-other-tenant',session('clinician',tenant='synthetic-other-tenant',permissions=grants),404),('rejected-no-scope',session('clinician',permissions=[]),403)]:
        r=call(reject_path,who,None,'GET',status,label)
        if status==200:
            body=json.loads(base64.b64decode(r['body']))
            assert body['status']=='rejected' and 'SYNTHETIC REJECTION NOTE' not in json.dumps(body)
    race=container_python(api,RACE,{**fixture,'tokens':[own['accessToken'],other['accessToken']]})
    proof=container_python(api,VERIFY,fixture)
    return {'checks':results,'concurrency':race,'mongo_proof':proof,'private_notes_absent_from_patient_gets':True}
