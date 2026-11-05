"""Remaining document producers retain selected facts and explicit unknowns."""
import importlib
import uuid
import pytest
from buyeros_api.sales.context import snapshot_from_sources
from buyeros_api.sales.contracts import SourceRef


@pytest.mark.parametrize('language', ['en', 'zh-HK'])
def test_grounded_documents_and_missing_proof(language):
    from buyeros_api.sales import research
    assert importlib.util.find_spec('buyeros_api.sales.documents'), 'Task12 document producer missing'
    from buyeros_api.sales.documents import compose_sales_document
    id=uuid.uuid4()
    ref=SourceRef(id=id,version=1,kind='project_fact',locator='fact:profile:'+str(uuid.uuid4())+':'+str(id),retention_class='durable')
    context=snapshot_from_sources([ref],[{'ref':ref.model_dump(mode='json'),'excerpts':['Acme supplies industrial sensors.']}],1,'fixture')
    common={'language':language}
    meeting=compose_sales_document('sales-prep',context,{**common,'objective':'Discuss sensors','duration_minutes':30})
    assert 'Acme' in meeting.content.cheat_sheet
    assert sum(x.minutes for x in meeting.content.agenda)==30
    objections=compose_sales_document('sales-objections',context,{**common,'objections':['Too expensive']})
    assert objections.content.responses[0].objection=='Too expensive'
    assert objections.content.unknowns
    with pytest.raises(ValueError,match='pricing'):
        compose_sales_document('sales-proposal',context,common)
    with pytest.raises(ValueError,match='competitor'):
        compose_sales_document('sales-competitors',context,{**common,'competitor_names':['Unproven Inc']})


def test_pdf_preserves_hong_kong_text_without_active_content():
    assert importlib.util.find_spec('buyeros_api.sales.rendering'), 'Task12 bundled renderer missing'
    from buyeros_api.sales.rendering import render_pdf
    from pypdf import PdfReader
    from io import BytesIO
    text='香港銷售報告：廣東話、採購、競爭對手。\n<script>alert(1)</script>'
    pdf=render_pdf(text)
    reader=PdfReader(BytesIO(pdf))
    assert text.splitlines()[0] in ''.join(p.extract_text() for p in reader.pages)
    assert '/OpenAction' not in reader.trailer['/Root']
    assert '/Names' not in reader.trailer['/Root']
    assert all('/Annots' not in p for p in reader.pages)
    from fontTools.ttLib import TTFont
    for font in reader.pages[0]['/Resources']['/Font'].values():
        child=font.get_object()['/DescendantFonts'][0].get_object()
        embedded=child['/FontDescriptor']['/FontFile2'].get_data()
        assert 'glyf' in TTFont(BytesIO(embedded)), 'CIDFontType2 must embed TrueType outlines, not CFF'


def test_markdown_export_has_no_embedded_active_content():
    from buyeros_api.sales.rendering import render_markdown
    value=render_markdown('<script>bad()</script>\n![track](https://example.test)\n[run](javascript:bad())')
    assert '<script>' not in value and '&lt;script&gt;' in value
    assert '\\!\\[track\\]' in value and '\\[run\\]' in value
