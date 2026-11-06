"""Render every downloaded page with PDFium, record geometric diagnostics."""
import json
import shutil
from pathlib import Path
import pypdfium2 as pdfium


def render(folder):
    doc=pdfium.PdfDocument(folder/'wellq-reporte-clinico-demo.pdf')
    target=folder/'pdf-pages';target.mkdir(exist_ok=True)
    pages=[]
    for n,page in enumerate(doc):
        bitmap=page.render(scale=120/72);image=bitmap.to_pil()
        name=f'pagina-{n+1:02d}.png';image.save(target/name)
        width,height=page.get_size();text=page.get_textpage();outside=[]
        for char in range(text.count_chars()):
            letter=text.get_text_range(char,1)
            if not letter.strip():continue
            left,bottom,right,top=text.get_charbox(char)
            # Page furniture: footer at 14 pt, synthetic banner at height-22.
            if left<30 or right>width-30 or bottom<8 or top>height-12:
                outside.append({'char':letter,'box':[round(x,2) for x in (left,bottom,right,top)]})
        pages.append({'page':n+1,'size_pt':[width,height],'image':str(target/name),
            'text_chars':text.count_chars(),'outside_margin_chars':len(outside),'outside_examples':outside[:12]})
        text.close();bitmap.close();page.close()
    doc.close()
    result={'renderer':'pypdfium2/PDFium','dpi':120,'pages':pages,
        'all_pages_rendered':True,'visual_review':'requires inspection of every PNG; geometry alone is insufficient'}
    (folder/'renderizado.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


def main():
    root=Path(__file__).resolve().parent/'demo-output'
    for name in ('suficiente','incompleto'):render(root/name)
    (root/'pdf-pages').mkdir(exist_ok=True)
    for file in (root/'suficiente/pdf-pages').glob('pagina-*.png'):shutil.copyfile(file,root/'pdf-pages'/file.name)
    results=json.loads((root/'resultados-demo.json').read_text())
    results['rendering']={name:json.loads((root/name/'renderizado.json').read_text()) for name in ('suficiente','incompleto')}
    (root/'resultados-demo.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(json.dumps({name:{'pages':len(results['rendering'][name]['pages']),
        'outside_margin_chars':sum(p['outside_margin_chars'] for p in results['rendering'][name]['pages'])} for name in ('suficiente','incompleto')}))


if __name__=='__main__':main()
