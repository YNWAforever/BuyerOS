"""Real package/subprocess boundaries: order, provenance and hostile input."""
import io
import subprocess
import sys
import zipfile

import pytest
from pptx_fixtures import pptx_bytes, REL, R


def parse(body):
    from buyeros_api.execution.pptx_parser import parse_pptx
    return parse_pptx(body)


def test_actual_slide_order_and_literal_page_provenance():
    result = parse(pptx_bytes(('Product: Alpha', 'Product: Beta'), order=[2, 1]))
    assert [(s['number'], s['text']) for s in result['slides']] == [(1, 'Product: Beta'), (2, 'Product: Alpha')]
    assert result['facts'][0]['value'] == 'Beta'
    assert result['facts'][0]['excerpt'] == 'Slide 1: Product: Beta'
    assert all(f['approved'] is False for f in result['facts'])
    assert result['metadata']['slide_count'] == 2
    assert result['metadata']['text_slide_count'] == 2


def test_no_editable_text_is_explicit_not_invented_facts():
    result = parse(pptx_bytes(('', '')))
    assert result['metadata']['text_slide_count'] == 0
    assert result['metadata']['classification'] == 'image_only'
    assert result['facts'] == []
    assert [s['text'] for s in result['slides']] == ['', '']


def test_unicode_runs_and_escaped_markup_remain_literal():
    result = parse(pptx_bytes(('Product: 泰國米 <script>不執行</script>\nValue proposition: 香港 / UK',)))
    assert result['slides'][0]['text'] == 'Product: 泰國米 <script>不執行</script>\nValue proposition: 香港 / UK'
    assert [f['value'] for f in result['facts']] == ['泰國米 <script>不執行</script>', '香港 / UK']


def test_external_relationship_and_embedded_objects_are_not_parsed():
    external = f'<Relationships xmlns="{REL}"><Relationship Id="evil" Type="{R}/hyperlink" Target="http://127.0.0.1:9/private" TargetMode="External"/></Relationships>'
    result = parse(pptx_bytes(extra={'ppt/slides/_rels/slide1.xml.rels': external, 'ppt/embeddings/object.bin': b'MZnot executable'}))
    assert result['slides'][0]['text'] == 'Product: Alpha'
    assert result['metadata']['external_relationships_ignored'] == 1
    assert result['metadata']['embedded_parts_ignored'] == 1


@pytest.mark.parametrize('extra', [
    {'../escape': b'x'}, {'ppt/vbaProject.bin': b'x'},
    {'ppt/slides/big.xml': b'x' * (2 * 1024 * 1024 + 1)},
    {'ppt/media/bomb': b'x' * (64 * 1024 * 1024 + 1)},
])
def test_unsafe_or_excessive_package_is_rejected(extra):
    with pytest.raises(ValueError):
        parse(pptx_bytes(extra=extra))


def test_dtd_entity_is_rejected_inside_xml():
    with pytest.raises(ValueError):
        parse(pptx_bytes(xml_override={'ppt/slides/slide1.xml': '<!DOCTYPE x [<!ENTITY evil "expanded">]><x>&evil;</x>'}))


def test_duplicate_member_is_rejected():
    body = pptx_bytes()
    out = io.BytesIO(body)
    with zipfile.ZipFile(out, 'a') as z:
        with pytest.warns(UserWarning):
            z.writestr('ppt/slides/slide1.xml', '<x/>')
    with pytest.raises(ValueError):
        parse(out.getvalue())


def test_missing_or_external_slide_relationship_is_rejected():
    rel = f'<Relationships xmlns="{REL}"><Relationship Id="rId1" Type="{R}/slide" Target="https://example.invalid/slide.xml" TargetMode="External"/></Relationships>'
    with pytest.raises(ValueError):
        parse(pptx_bytes(xml_override={'ppt/_rels/presentation.xml.rels': rel}))


def test_slide_limit_is_enforced_before_reading_text():
    with pytest.raises(ValueError):
        parse(pptx_bytes(tuple('x' for _ in range(101))))


def test_total_unicode_text_limit_is_bytes_not_characters():
    with pytest.raises(ValueError):
        parse(pptx_bytes(tuple('漢' * 1000 for _ in range(34))))


def test_entry_limit_and_body_limit_are_enforced():
    with pytest.raises(ValueError):
        parse(pptx_bytes(extra={f'ignored/{i}': b'' for i in range(1001)}))
    with pytest.raises(ValueError):
        parse(b'PK\x03\x04' + b'x' * (20 * 1024 * 1024))


def test_parent_enforces_deadline_with_real_process(monkeypatch):
    from buyeros_api.execution import pptx_parser
    real_run = subprocess.run
    def slow_child(args, **kwargs):
        return real_run([sys.executable, '-c', 'import time; time.sleep(2)'], **kwargs)
    monkeypatch.setattr(pptx_parser, 'PARSER_TIMEOUT_SECONDS', 0.05)
    monkeypatch.setattr(pptx_parser.subprocess, 'run', slow_child)
    with pytest.raises(pptx_parser.PptxParserTimeout):
        parse(pptx_bytes())


def test_candidate_excerpt_stays_within_profile_contract_without_truncating_source():
    literal='Product'+(' ' * 25000)+': Rice'
    parsed=parse(pptx_bytes((literal,)))
    assert parsed['slides'][0]['text']==literal
    assert parsed['facts']==[]
