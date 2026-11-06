"""Read evidence and owned Docker metadata; never record environments or logs."""
import argparse
import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


def command(*args):
    return subprocess.check_output(args, text=True, encoding='utf-8').strip()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--baseline',type=Path,required=True)
    args=parser.parse_args()
    backend=Path(__file__).resolve().parent.parent
    repo=backend.parent.parent
    evidence=backend/'docs/evidencias_integracion'
    state=json.loads((backend/'integration/.runtime/state.json').read_text())
    assert re.fullmatch(r'wellq-int-[a-f0-9]{12}',state['project'])
    baseline=json.loads(args.baseline.read_text(encoding='utf-8-sig'))
    branch=command('git','-C',str(repo),'branch','--show-current')
    head=command('git','-C',str(repo),'rev-parse','HEAD')
    assert branch==baseline['branch'] and head==baseline['head']
    changed=[];missing=[]
    for rel,previous in baseline['hashes'].items():
        file=repo/rel
        if not file.is_file():missing.append(rel)
        elif hashlib.sha256(file.read_bytes()).hexdigest()!=previous:changed.append(rel)
    expected={f'wellq-clinical-tests-main/backend/{p}' for p in ('.dockerignore','app/services/scoring.py','checks/test_scoring.py')}
    assert not missing and set(changed)==expected,(missing,changed)
    preservation={'baseline':str(args.baseline),'checked_files':len(baseline['hashes']),
        'existing_changed_only':sorted(changed),'missing':missing,'branch':branch,'head':head,
        'original_tests_docs_01_12_frontend_requirements_unchanged':True}
    (evidence/'preservation.json').write_text(json.dumps(preservation,indent=2),encoding='utf-8')
    summaries={}
    for name in ('integration-first','integration-after-fixes','integration','application-regressions','clamav-first','clamav-second','clamav'):
        file=evidence/(name+'.xml')
        if file.exists():
            cases=ET.parse(file).getroot().findall('.//testcase')
            counts={k:sum(case.find(tag) is not None for case in cases) for k,tag in [('failed','failure'),('errors','error'),('skipped','skipped')]}
            counts.update(collected=len(cases),passed=len(cases)-sum(counts.values()))
            summaries[name]=counts
    historical=[]
    cases=ET.parse(evidence/'integration.xml').getroot().findall('.//testcase')
    audit=Path(r'C:\Dev\wellq-auditoria-final\06_REGRESIONES_Y_PRUEBAS_HISTORICAS.md').read_text(encoding='utf-8-sig')
    for case in cases:
        if not case.attrib['classname'].endswith('test_historical_ports'):continue
        name=case.attrib['name'];original=re.search(r'`(tests/[^`]+::'+re.escape(name)+r')`',audit)
        assert original,name
        pure=name in ('test_same_input_gives_same_output','test_subscore_is_always_between_0_and_100')
        historical.append({'original':original.group(1),'integration':name,'result':'PASS' if not list(case) else 'CHECK XML',
            'infrastructure':'original pure function; no Mongo/HTTP' if pure else 'real Mongo + HTTP + workers; explicit object/AI/scanner doubles',
            'real_gcs_or_external_ai':'not certified'})
    assert len(historical)==30
    (evidence/'historical-matrix.json').write_text(json.dumps(historical,indent=2),encoding='utf-8')
    rows=['| Original | Caso de integración | Resultado / alcance |','|---|---|---|']
    for item in historical:rows.append(f"| `{item['original']}` | `{item['integration']}` | {item['result']}; {item['infrastructure']} |")
    (evidence/'historical-matrix.md').write_text('\n'.join(rows)+'\n',encoding='utf-8')
    ids=command('docker','ps','-aq','--filter','label=com.docker.compose.project='+state['project']).splitlines()
    resources=[]
    for cid in ids:
        entry=json.loads(command('docker','inspect',cid))[0]
        assert entry['Config']['Labels']['com.docker.compose.project']==state['project']
        resources.append({'name':entry['Name'].lstrip('/'),'image':entry['Config']['Image'],'image_id':entry['Image'],
            'state':entry['State']['Status'],'oom_killed':entry['State']['OOMKilled'],
            'ports':entry['HostConfig']['PortBindings'],'memory_limit':entry['HostConfig']['Memory'],
            'mounts':[{k:m.get(k) for k in ('Type','Name','Source','Destination','RW')} for m in entry['Mounts']]})
    inventory={'project':state['project'],'containers':resources,
        'volumes':command('docker','volume','ls','--filter','label=com.docker.compose.project='+state['project'],'--format','{{.Name}}').splitlines(),
        'networks':command('docker','network','ls','--filter','label=com.docker.compose.project='+state['project'],'--format','{{.Name}}').splitlines(),
        'host_ports_published':False}
    inventory['docker']={'engine':command('docker','version','--format','{{.Server.Version}}'),
        'context':command('docker','context','show'),'compose':command('docker','compose','version','--short'),
        'memory_bytes':int(command('docker','info','--format','{{.MemTotal}}'))}
    inventory['external_images']={tag:json.loads(command('docker','image','inspect',tag,'--format','{{json .RepoDigests}}'))
        for tag in ('mongo:7.0','clamav/clamav:stable')}
    assert all(not r['ports'] for r in resources)
    (evidence/'resources.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
    summary={'generated_at':datetime.now(timezone.utc).isoformat(),'suites':summaries,
        'historical_cases':30,'historical_real_mongo_with_doubles':28,'historical_pure':2,
        'restart_probe':json.loads((evidence/'restart-probe.json').read_text()),
        'synthetic_http_examples':len(json.loads((evidence/'frontend-examples.json').read_text())['samples'])}
    (evidence/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    source_files=[backend/'.dockerignore',backend/'app/services/scoring.py',backend/'checks/test_scoring.py']
    source_files.extend(p for p in (backend/'integration').rglob('*') if p.is_file() and not {'.runtime','__pycache__'}.intersection(p.parts))
    source_files.extend(p for p in (backend/'docs').glob('1[3-6]_*.md'))
    delivery={'branch':branch,'head':head,'existing_changed':sorted(changed),
        'source_sha256':{p.relative_to(backend).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source_files)},
        'git_status':command('git','-C',str(repo),'status','--short')}
    (evidence/'delivery-manifest.json').write_text(json.dumps(delivery,indent=2),encoding='utf-8')
    manifest={}
    for file in sorted(evidence.iterdir()):
        if file.is_file() and file.name!='sha256.json':manifest[file.name]=hashlib.sha256(file.read_bytes()).hexdigest()
    (evidence/'sha256.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps({'suites':summaries,'preserved_files':len(baseline['hashes'])-len(changed),'historical_cases':len(historical)}))


if __name__=='__main__':main()
