"""ClamAV TCP daemon is real here; no storage or model certification is implied."""
import json
import socket
import time
from pathlib import Path
import pytest
from app.config import settings
from app.services.file_validation import ClamAVScanner, ScannerUnavailable, FileRejected, validate_document
from app.services.file_validation import scanner
from app.services.uploads import upload_status
from app.tenancy import TenantDatabase
from app.workers.processing import run_once
from integration.guard import database
from integration.adapters import object_path
import hashlib
import uuid
from datetime import datetime, timedelta


@pytest.fixture(scope='module',autouse=True)
def wait_for_daemon():
    for _ in range(90):
        try:
            with socket.create_connection(('clamav-int',3310),3) as connection:
                connection.sendall(b'zVERSION\0');version=connection.recv(4096).decode().strip('\0')
            Path('/evidence/clamav-version.json').write_text(json.dumps({'daemon':version,'service':'clamav-int','real_daemon':True}))
            return
        except OSError:
            time.sleep(1)
    pytest.fail('ClamAV daemon unavailable; do not classify as passed')


def test_real_clamav_clean_synthetic_document():
    ClamAVScanner().scan(b'SYNTHETIC CLEAN INTEGRATION DOCUMENT')


def test_real_clamav_eicar_innocuous_standard_test():
    data=b'X5O!P%@AP[4'+b'\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*'
    with pytest.raises(FileRejected,match='MALWARE_DETECTED'):
        ClamAVScanner().scan(data)


def test_real_scanner_fails_closed_when_endpoint_unavailable(monkeypatch):
    monkeypatch.setattr(settings,'CLAMAV_HOST','127.0.0.1')
    monkeypatch.setattr(settings,'CLAMAV_PORT',65534)
    with pytest.raises(ScannerUnavailable):
        ClamAVScanner().scan(b'SYNTHETIC')


@pytest.mark.parametrize('kind',['clean','eicar','unavailable'])
def test_worker_real_scanner_real_mongo_storage_double(monkeypatch,kind):
    from integration.tests.conftest import output,pdf
    raw=database();tenant='av-'+uuid.uuid4().hex;db=TenantDatabase(raw,tenant)
    ct='ct-av-'+uuid.uuid4().hex;data=pdf(output())
    if kind=='eicar':
        import io
        from pypdf import PdfWriter
        writer=PdfWriter(clone_from=io.BytesIO(data))
        writer.add_attachment('eicar.com',b'X5O!P%@AP[4'+b'\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*')
        document=io.BytesIO();writer.write(document);data=document.getvalue()
        with pytest.raises(FileRejected,match='MALWARE_DETECTED'):
            ClamAVScanner().scan(data)
    key='quarantine/clinical-tests/'+hashlib.sha256(tenant.encode()).hexdigest()+'/'+ct+'/original'
    path=object_path(key);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    path.with_name(path.name+'.meta').write_text(json.dumps({'mime':'application/pdf','generation':1}))
    now=datetime.utcnow()+timedelta(days=1)
    db.clinical_tests.insert_one({'clinical_test_id':ct,'patient_id':'synthetic-av-patient','deleted_at':None,'ai_consent':False,
        'file':{'gcs_object_key':key,'mime_type':'application/pdf','size_bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()},
        'upload':{'upload_id':ct,'client_upload_id':ct,'idempotency_key':ct,'status':'processing',
                  'processing_status':{'malware_scan':'pending','mime_validation':'pending'},
                  'job':{'status':'pending','attempts':0,'available_at':now}}})
    if kind=='unavailable':
        monkeypatch.setattr(settings,'CLAMAV_HOST','127.0.0.1');monkeypatch.setattr(settings,'CLAMAV_PORT',65534)
    monkeypatch.setattr(scanner,'scan',ClamAVScanner().scan)
    # Existing synthetic retries may precede this job on repeat runs. Keep the
    # real queue selection; drain eligible owned jobs until THIS job is claimed.
    for _ in range(100):
        assert run_once(raw,'upload',now=now)
        stored=db.clinical_tests.find_one({'clinical_test_id':ct})
        if stored['upload']['job']['attempts']>0:break
    assert stored['upload']['job']['attempts']==1
    status=upload_status(ct,'synthetic-av-patient',db)
    if kind=='clean':
        assert status['local_file_can_be_deleted'] is True and stored['upload']['status']=='ready_for_review'
        assert stored['extraction']['status']=='not_applicable'
    elif kind=='eicar':
        assert stored['upload']['status']=='rejected' and not status['local_file_can_be_deleted']
        assert stored['upload']['job']['error_code']=='MALWARE_DETECTED'
    else:
        assert stored['upload']['status']=='processing' and not status['local_file_can_be_deleted']
        assert stored['upload']['job']['error_code']=='DEPENDENCY_UNAVAILABLE'
