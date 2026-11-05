"""Inert text exports. Bundled HK font only; no HTML, URLs, scripts or attachments."""
import hashlib
import html
from pathlib import Path

FONT=Path(__file__).with_name('fonts')/'BuyerOSHK-Regular.ttf'
FONT_SHA256='beac1bcbe253ab183aa120983f1777a39c8c620326744d1bc402da4000d1e39a'


def output_text(output):
    lines=[f'{output.kind} — revision {output.revision}',str(output.id),'']
    def walk(value,depth=0):
        if isinstance(value,dict):
            for key,item in value.items():
                if key in {'record_basis','document_basis','setup_basis'}: continue
                if not isinstance(item,(dict,list)):
                    lines.append(key.replace('_',' ')+': '+('Unknown' if item is None else str(item)))
                elif item:
                    lines.append(key.replace('_',' ')+':')
                    walk(item,depth+1)
        elif isinstance(value,list):
            for item in value: walk(item,depth+1)
        else: lines.append('Unknown' if value is None else str(value))
    walk(output.content.model_dump(mode='json'))
    lines.append('Selected sources:')
    lines.extend(f'{r.kind}: {r.id} (revision {r.version})' for r in output.citations)
    text='\n'.join(lines)
    if len(text.encode('utf-8'))>1_000_000: raise ValueError('export text exceeds limit')
    return text


def render_markdown(text):
    # Escape HTML and Markdown link/image syntax; no active content in downstream previews.
    text=html.escape(text,quote=False)
    for c in ('\\','[',']','!','`','*','_'):
        text=text.replace(c,'\\'+c)
    return text+'\n'


def render_pdf(text):
    from fpdf import FPDF
    from fontTools.ttLib import TTFont
    if hashlib.sha256(FONT.read_bytes()).hexdigest()!=FONT_SHA256: raise ValueError('bundled font integrity mismatch')
    with TTFont(FONT) as font:
        supported=font.getBestCmap()
        missing={ord(c) for c in text if not c.isspace() and ord(c) not in supported}
        if missing: raise ValueError('selected text has glyphs unavailable in the bundled font')
    pdf=FPDF()
    pdf.set_auto_page_break(auto=True,margin=16)
    pdf.add_font('NotoHK',fname=str(FONT))
    pdf.add_page()
    pdf.set_font('NotoHK',size=10)
    pdf.multi_cell(0,6,text=text,wrapmode='CHAR',new_x='LMARGIN',new_y='NEXT')
    # Remove the renderer's harmless default viewport OpenAction too, so the
    # artifact has no action dictionary of any kind.
    from pypdf import PdfReader, PdfWriter
    from io import BytesIO
    writer=PdfWriter(clone_from=PdfReader(BytesIO(bytes(pdf.output()))))
    writer.root_object.pop('/OpenAction',None)
    buffer=BytesIO();writer.write(buffer)
    data=buffer.getvalue()
    if len(data)>8_000_000: raise ValueError('rendered PDF exceeds limit')
    return data
