"""PDF presentation regressions, no sockets or clinical calculations."""
import io
import pytest
from pypdf import PdfReader
from app.config import settings
from app.routes.clinical_tests import _build_lab_report_pdf, _PDF_LEGEND


def report(rows=1,reference=None,test_only=True):
    return {'generated_at':'2026-11-05T12:00:00Z','header':{'mode':'exam','window':{'months':12},
        'exams':[{'clinical_test_id':'examen-ficticio','title':'DATOS FICTICIOS','issuer':'Laboratorio ficticio Álamo',
                  'description':'Análisis sintético con tildes: músculo y articulación.'}]},
        'score':None,'flags':[],'results':{'panels':[{'panel_code':'prueba','specimen':'blood','rows':[
            {'marker_code':f'fila{i:04d}','name':f'Marcador sintético fila{i:04d}','value':94,'unit':'mg/dL',
             'reference':reference or {'source':'document'},'status':'indeterminate','subscore':None,
             'subscore_blank_reason':'NO_REFERENCE_RANGE','edited':True,'origin':{'clinical_test_id':'examen-ficticio'}}
            for i in range(rows)]}]},'longitudinal':{'marker_series':[]},
        'traceability':{'catalog_version':'cat-test','scoring_version':'score-test',
                        'extractions':[{'extraction_meta':{'test_only':test_only}}]}}


def pages(data,patient='paciente-ficticio',clinician='clinico-ficticio'):
    pdf=PdfReader(io.BytesIO(_build_lab_report_pdf(data,patient,clinician)),strict=True)
    return [p.extract_text() for p in pdf.pages]


def test_long_table_repeats_header_and_complete_footer_on_every_page(env):
    patient='paciente-'+('x'*80);clinician='clinico-'+('y'*96)
    text=pages(report(100),patient,clinician)
    assert len(text)>=3
    for n,page in enumerate(text,1):
        assert patient in page and clinician in page
        assert 'cat-test' in page and 'score-test' in page and '2026-11-05' in page
        assert _PDF_LEGEND in page and f'Página {n}' in page
        assert 'DEMOSTRACIÓN SINTÉTICA' in page and 'NO USO CLÍNICO' in page
    all_text='\n'.join(text)
    for i in range(100):assert f'fila{i:04d}' in all_text
    table_pages=[p for p in text if 'fila' in p]
    assert all('Rango de referencia' in p and 'Subscore' in p for p in table_pages)


def test_no_score_does_not_invent_a_cause_and_missing_ranges_are_readable(env):
    text=' '.join('\n'.join(pages(report())).split())
    assert 'Sin puntaje publicable' in text and 'no hay examenes confirmados' not in text
    assert 'Sin rango (documento)' in text and 'Sin rango de referencia' in text
    assert '- (None)' not in text and 'NO_REFERE\nNCE_RANGE' not in text
    assert 'al menos dos mediciones' in text and 'No se infieren tendencias' in text
    assert 'Laboratorio ficticio Álamo' in text and 'músculo y articulación' in text
    assert '94' in text and '(editado)' in text


@pytest.mark.parametrize('reference,label',[
    ({'high':100,'source':'document','unit':'mg/dL'},'Hasta 100'),
    ({'low':40,'source':'document','unit':'mg/dL'},'Desde 40'),
    ({'low':70,'high':100,'source':'catalog','unit':'mg/dL'},'70 - 100 mg/dL (catálogo)')])
def test_reference_bounds_are_not_invented_in_pdf(env,reference,label):
    assert label in '\n'.join(pages(report(reference=reference)))


@pytest.mark.parametrize('environment,test_only,banner',[
    ('test',False,True),('development',True,True),('development',False,False)])
def test_synthetic_banner_follows_test_environment_or_explicit_provenance(env,environment,test_only,banner):
    env['monkeypatch'].setattr(settings,'ENVIRONMENT',environment)
    text='\n'.join(pages(report(test_only=test_only)))
    assert ('DEMOSTRACIÓN SINTÉTICA' in text)==banner
