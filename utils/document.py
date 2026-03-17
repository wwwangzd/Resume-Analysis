import io
import json
import urllib.request

from pdfminer.high_level import extract_text


def _normalize_lines(text):
    lines = text.splitlines()
    cleaned = [line.strip('\t').replace('\t', ' ').strip() for line in lines]
    return [line for line in cleaned if line]


def _build_multipart_form_data(file_bytes, filename='resume.pdf', language='chs'):
    boundary = '----ResumeAnalysisBoundary'
    part1 = (
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="language"\r\n\r\n'
        f'{language}\r\n'
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="isOverlayRequired"\r\n\r\n'
        f'false\r\n'
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f'Content-Type: application/pdf\r\n\r\n'
    ).encode('utf-8')
    part2 = f'\r\n--{boundary}--\r\n'.encode('utf-8')
    body = part1 + file_bytes + part2
    content_type = f'multipart/form-data; boundary={boundary}'
    return body, content_type


def _cloud_ocr_with_settings(file_bytes, settings, filename='resume.pdf'):
    ocr_settings = settings['ocr']
    if not ocr_settings['enabled']:
        return ''

    api_key = ocr_settings['api_key'].strip()
    if not api_key:
        raise ValueError('ocr.api_key is empty in settings.json.')

    ocr_url = ocr_settings['api_url']
    language = ocr_settings['language']
    timeout_seconds = ocr_settings['timeout_seconds']

    body, content_type = _build_multipart_form_data(file_bytes, filename=filename, language=language)
    req = urllib.request.Request(ocr_url, data=body, method='POST')
    req.add_header('apikey', api_key)
    req.add_header('Content-Type', content_type)

    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
        payload = json.loads(resp.read().decode('utf-8', errors='ignore'))

    parsed_results = payload.get('ParsedResults', [])
    if not parsed_results:
        return ''

    texts = [item.get('ParsedText', '') for item in parsed_results if item.get('ParsedText')]
    return '\n'.join(texts).strip()


async def get_resume_text(file_bytes, settings):
    if not file_bytes.startswith(b'%PDF'):
        raise ValueError('Only PDF resumes are supported.')

    ocr_text = _cloud_ocr_with_settings(file_bytes, settings, filename='resume.pdf')
    if ocr_text:
        return '\n'.join(_normalize_lines(ocr_text))

    text = extract_text(io.BytesIO(file_bytes))
    return '\n'.join(_normalize_lines(text))
