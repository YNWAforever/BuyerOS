"""Small hand-authored OOXML fixtures; no customer decks in tests."""
import io
import zipfile
from xml.sax.saxutils import escape

P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
REL = 'http://schemas.openxmlformats.org/package/2006/relationships'


def pptx_bytes(texts=('Product: Alpha',), *, order=None, extra=None, xml_override=None):
    order = list(range(1, len(texts) + 1)) if order is None else order
    parts = {
        '[Content_Types].xml': '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/></Types>',
        'ppt/presentation.xml': f'<p:presentation xmlns:p="{P}" xmlns:r="{R}"><p:sldIdLst>' + ''.join(f'<p:sldId id="{255+i}" r:id="rId{i}"/>' for i in order) + '</p:sldIdLst></p:presentation>',
        'ppt/_rels/presentation.xml.rels': f'<Relationships xmlns="{REL}">' + ''.join(f'<Relationship Id="rId{i}" Type="{R}/slide" Target="slides/slide{i}.xml"/>' for i in range(1, len(texts)+1)) + '</Relationships>',
    }
    for i, text in enumerate(texts, 1):
        paragraphs = ''.join(f'<a:p><a:r><a:t>{escape(line)}</a:t></a:r></a:p>' for line in text.split('\n'))
        parts[f'ppt/slides/slide{i}.xml'] = f'<p:sld xmlns:p="{P}" xmlns:a="{A}"><p:cSld><p:spTree><p:sp><p:txBody>{paragraphs}</p:txBody></p:sp></p:spTree></p:cSld></p:sld>'
    parts.update(extra or {})
    parts.update(xml_override or {})
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for name, body in parts.items():
            z.writestr(name, body)
    return stream.getvalue()
