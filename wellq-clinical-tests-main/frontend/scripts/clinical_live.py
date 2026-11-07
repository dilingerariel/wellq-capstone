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
import json,sys,urllib.request,urllib.error
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
p=json.load(sys.stdin)
def race(path,bodies):
 gate=Barrier(2)
 def call(args):
  token,body=args;gate.wait()
  req=urllib.request.Request('http://127.0.0.1:8000/api/v1/clinical-tests/'+p['race']+path,data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},method='PATCH' if path=='/review' else 'POST')
  try:r=urllib.request.urlopen(req,timeout=20)
  except urllib.error.HTTPError as e:r=e
  with r:return r.status
 with ThreadPoolExecutor(max_workers=2) as pool:result=sorted(pool.map(call,zip(p['tokens'],bodies)))
 assert result==[200,409], 'Concurrent operations must have one winner'
 return result
review=race('/review',[{'review_note':'SYNTHETIC RACE A'},{'review_note':'SYNTHETIC RACE B'}])
validation=race('/extraction/validate',[{'validation_status':'validated','marker_corrections':[{'marker_code':'glucose','value_raw':str(v),'unit_raw':'mg/dL'}]} for v in [97,98]])
print(json.dumps({'concurrent_review_statuses':review,'concurrent_validation_statuses':validation}))
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
        r=forward(path,headers,method,json.dumps(body).encode())
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
    race=container_python(api,RACE,{**fixture,'tokens':[own['accessToken'],other['accessToken']]})
    proof=container_python(api,VERIFY,fixture)
    return {'checks':results,'concurrency':race,'mongo_proof':proof,'private_notes_absent_from_patient_gets':True}
