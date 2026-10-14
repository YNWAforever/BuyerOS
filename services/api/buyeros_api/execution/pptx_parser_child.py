"""Bounded, network-free OOXML text extraction. No application configuration."""
from __future__ import annotations

import io
import json
import os
import posixpath
import re
import socket
import sys
import zipfile

from defusedxml import ElementTree as ET

MAX_INPUT = 20 * 1024 * 1024
MAX_EXPANDED = 64 * 1024 * 1024
MAX_XML = 2 * 1024 * 1024
MAX_TEXT = 100_000
P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
REL = 'http://schemas.openxmlformats.org/package/2006/relationships'


def _deny_network(*_args, **_kwargs):
    raise RuntimeError('network disabled in PowerPoint parser')


def extract(body: bytes) -> dict:
    with zipfile.ZipFile(io.BytesIO(body)) as z:
        entries = z.infolist()
        if not 1 <= len(entries) <= 1000 or sum(e.file_size for e in entries) > MAX_EXPANDED:
            raise ValueError('package bounds')
        names = set()
        xml = {}
        external = embedded = expanded = 0
        for e in entries:
            name = e.filename
            clean = name.rstrip('/')
            if (not clean or len(name) > 1024 or '\\' in name or name.startswith('/')
                    or posixpath.normpath(clean) != clean or ':' in name
                    or any(part in ('.', '..') for part in clean.split('/'))
                    or any(ord(c) < 32 for c in name) or clean in names
                    or e.flag_bits & 1 or e.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                    or 'vbaproject' in name.casefold()):
                raise ValueError('unsafe package')
            names.add(clean)
            is_xml = name.endswith(('.xml', '.rels'))
            if is_xml and e.file_size > MAX_XML:
                raise ValueError('XML bounds')
            if name.startswith('ppt/embeddings/') and not e.is_dir():
                embedded += 1
            data = bytearray() if is_xml else None
            actual = 0
            with z.open(e) as part:
                while block := part.read(65536):
                    actual += len(block)
                    expanded += len(block)
                    if actual > e.file_size or expanded > MAX_EXPANDED or is_xml and actual > MAX_XML:
                        raise ValueError('expanded bounds')
                    if data is not None:
                        data.extend(block)
            if actual != e.file_size:
                raise ValueError('invalid size')
            if data is not None:
                root = ET.fromstring(bytes(data), forbid_dtd=True, forbid_entities=True, forbid_external=True)
                xml[name] = root
                if name.endswith('.rels'):
                    external += sum(r.get('TargetMode', '').casefold() == 'external' for r in root)
        types = xml['[Content_Types].xml']
        content_types = [e.get('ContentType', '').casefold() for e in types]
        if (not any(t == 'application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml' for t in content_types)
                or any('macroenabled' in t or 'vbaproject' in t for t in content_types)):
            raise ValueError('presentation type')
        presentation = xml['ppt/presentation.xml']
        if presentation.tag != f'{{{P}}}presentation':
            raise ValueError('presentation root')
        relationships = xml['ppt/_rels/presentation.xml.rels']
        by_id = {}
        for rel in relationships:
            ident = rel.get('Id')
            if not ident or ident in by_id:
                raise ValueError('relationship identifiers')
            by_id[ident] = rel
        ids = presentation.findall(f'{{{P}}}sldIdLst/{{{P}}}sldId')
        if not 1 <= len(ids) <= 100:
            raise ValueError('slide count')
        slides, seen, total_text = [], set(), 0
        for number, item in enumerate(ids, 1):
            rel = by_id[item.attrib[f'{{{R}}}id']]
            if rel.get('Type') != f'{R}/slide' or rel.get('TargetMode', '').casefold() == 'external':
                raise ValueError('invalid slide relationship')
            target = rel.get('Target', '')
            if '\\' in target or ':' in target or target.startswith('/'):
                raise ValueError('invalid slide target')
            name = posixpath.normpath(posixpath.join('ppt', target))
            if not re.fullmatch(r'ppt/slides/[^/]+\.xml', name) or name in seen:
                raise ValueError('invalid slide target')
            seen.add(name)
            root = xml[name]
            if root.tag != f'{{{P}}}sld':
                raise ValueError('slide root')
            paragraphs = []
            for paragraph in root.iter(f'{{{A}}}p'):
                text = ''.join('\n' if node.tag == f'{{{A}}}br' else node.text or ''
                               for node in paragraph.iter() if node.tag in (f'{{{A}}}t', f'{{{A}}}br'))
                if text:
                    paragraphs.append(text)
            text = '\n'.join(paragraphs)
            total_text += len(text.encode('utf-8'))
            if total_text > MAX_TEXT:
                raise ValueError('text bounds')
            slides.append({'number': number, 'text': text, 'classification': 'text' if text.strip() else 'image_only'})
        text_slides = sum(s['classification'] == 'text' for s in slides)
        facts = []
        for slide in slides:
            for line in slide['text'].splitlines():
                label, separator, value = line.partition(':')
                field = {'product': 'product', 'value proposition': 'value_proposition'}.get(label.strip().casefold())
                value = value.strip()
                excerpt = f"Slide {slide['number']}: {line}"
                if field and separator and value and len(value) <= 1000 and len(excerpt) <= 20000:
                    facts.append({'field': field, 'value': value, 'approved': False,
                                  'excerpt': excerpt, 'slide_number': slide['number']})
        return {'slides': slides, 'facts': facts[:20], 'metadata': {
            'format': 'pptx', 'slide_count': len(slides), 'text_slide_count': text_slides,
            'classification': 'text' if text_slides else 'image_only', 'text_bytes': total_text,
            'external_relationships_ignored': external, 'embedded_parts_ignored': embedded,
        }}


def main() -> int:
    if os.name == 'posix':
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
        resource.setrlimit(resource.RLIMIT_CPU, (6, 6))
        resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024,) * 2)
    socket.socket = _deny_network
    socket.create_connection = _deny_network
    body = sys.stdin.buffer.read(MAX_INPUT + 1)
    if not body.startswith(b'PK\x03\x04') or len(body) > MAX_INPUT:
        return 2
    try:
        output = json.dumps(extract(body), ensure_ascii=False).encode('utf-8')
        if len(output) > 256 * 1024:
            return 2
        sys.stdout.buffer.write(output)
        return 0
    except Exception:
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
