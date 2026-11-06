import json
import time
from pathlib import Path
from integration.guard import database, environment
from integration.tests.conftest import Context


def run(mode):
    raw=database();file=Path('/evidence/restart-probe.json');project,ident,_,_=environment()
    if mode=='prepare':
        ctx=Context(raw);init=ctx.start()
        doc=raw.clinical_tests.find_one({'client_id':ctx.tenant,'clinical_test_id':init['clinical_test_id']})
        assert doc['upload']['job']['status']=='pending'
        data={'project':project,'run':ident,'tenant':ctx.tenant,'patient':ctx.patient,
              'clinical_test_id':init['clinical_test_id'],'upload_id':init['upload_id'],'before':'pending'}
    else:
        data=json.loads(file.read_text());assert data['project']==project and data['run']==ident
        ctx=Context(raw);ctx.tenant=data['tenant'];ctx.patient=data['patient']
        ext=ctx.wait_ext(data)
        status=ctx.req('GET','/clinical-tests/uploads/'+data['upload_id']+'/status').json()
        assert status['local_file_can_be_deleted'] and ext['status']=='awaiting_confirmation'
        assert raw.clinical_test_extractions.count_documents({'client_id':ctx.tenant,'clinical_test_id':data['clinical_test_id']})==1
        data.update(after='done',real_process_restart_verified=True)
    file.write_text(json.dumps(data,indent=2));print('Restart probe '+mode+' passed (real persisted job)')
