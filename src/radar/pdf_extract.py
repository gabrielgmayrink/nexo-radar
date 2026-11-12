"""Extract bounded PDF evidence in a disposable child process, never execute content."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

MAX_BYTES = 3 * 1024 * 1024
MAX_PAGES = 80


def extract_pdf(payload):
    if not payload.startswith(b'%PDF-') or len(payload) > MAX_BYTES:
        return {'state': 'unsupported_document', 'pages': []}
    with tempfile.TemporaryDirectory(prefix='nexo-pdf-') as directory:
        source, target = Path(directory) / 'input.pdf', Path(directory) / 'output.json'
        source.write_bytes(payload)
        worker = str(Path(__file__).resolve())
        try:
            subprocess.run([sys.executable, '-I', worker, str(source), str(target)], check=True, timeout=20,
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if target.stat().st_size > 400_000:
                return {'state': 'extraction_limit', 'pages': []}
            return json.loads(target.read_text(encoding='utf-8'))
        except (subprocess.SubprocessError, OSError, ValueError):
            return {'state': 'extraction_failed', 'pages': []}


def _worker(source, target):
    if os.name == 'posix':
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
        resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
        resource.setrlimit(resource.RLIMIT_FSIZE, (500_000, 500_000))
    from pypdf import PdfReader
    reader = PdfReader(source, strict=True)
    if reader.is_encrypted:
        result = {'state': 'encrypted', 'pages': []}
    else:
        total = len(reader.pages)
        pages = []
        remaining = 240_000
        for index, page in enumerate(reader.pages):
            if index >= MAX_PAGES or remaining <= 0:
                break
            # Large decompressed streams can consume disproportionate memory/time.
            contents = page.get_contents()
            if contents and len(contents.get_data()) > 5 * 1024 * 1024:
                break
            content = (page.extract_text() or '')[:min(6_000, remaining)].strip()
            remaining -= len(content)
            pages.append({'page': index + 1, 'text': content})
        truncated = any(len(p['text']) >= 6_000 for p in pages)
        partial = total > len(pages) or truncated
        state = 'partial' if partial else 'text_available' if any(p['text'] for p in pages) else 'ocr_required'
        result = {'state': state, 'pages': pages, 'totalPages': total,
                  'textTruncated': truncated}
    Path(target).write_text(json.dumps(result, ensure_ascii=True), encoding='utf-8')


if __name__ == '__main__':
    _worker(sys.argv[1], sys.argv[2])
