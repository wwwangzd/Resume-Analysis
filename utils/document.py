import argparse
import asyncio
import io
from pathlib import Path
from typing import List

import numpy as np
import pypdfium2 as pdfium
from paddleocr import PaddleOCR

import config
from config.logger import get_logger, log_stage_timing, start_timer

paddleOcrInstance = None
paddleOcrSignature = None
logger = get_logger('resume_analysis.document')


def normalize_lines(text: str) -> List[str]:
    lines = text.splitlines()
    cleaned = [line.strip('\t').replace('\t', ' ').strip() for line in lines]
    return [line for line in cleaned if line]


def build_ocr_instance(ocr_settings):
    build_start = start_timer()
    global paddleOcrInstance
    global paddleOcrSignature

    signature = (
        ocr_settings['lang'],
        ocr_settings['use_angle_cls'],
        ocr_settings['use_gpu'],
        ocr_settings['show_log'],
    )

    if paddleOcrInstance is not None and paddleOcrSignature == signature:
        log_stage_timing(logger, 'ocr_instance_reuse', build_start, reused=True)
        return paddleOcrInstance

    paddleOcrInstance = PaddleOCR(
        lang=ocr_settings['lang'],
        use_angle_cls=ocr_settings['use_angle_cls'],
        use_gpu=ocr_settings['use_gpu'],
        show_log=ocr_settings['show_log'],
    )
    paddleOcrSignature = signature
    log_stage_timing(logger, 'ocr_instance_init', build_start, reused=False)
    return paddleOcrInstance


def render_pdf_pages_to_images(file_bytes: bytes, render_scale: float) -> List[np.ndarray]:
    render_start = start_timer()
    pdf = pdfium.PdfDocument(io.BytesIO(file_bytes))
    images = []
    try:
        for page_index in range(len(pdf)):
            page = pdf.get_page(page_index)
            try:
                bitmap = page.render(scale=render_scale)
                pil_image = bitmap.to_pil().convert('RGB')
                # PaddleOCR expects ndarray image input.
                images.append(np.array(pil_image))
            finally:
                page.close()
    finally:
        pdf.close()
    log_stage_timing(logger, 'pdf_render', render_start, pages=len(images), render_scale=render_scale)
    return images


def extract_paddle_text(ocr_result) -> List[str]:
    texts = []
    for page_result in ocr_result or []:
        if not isinstance(page_result, list):
            continue
        for line in page_result:
            if not isinstance(line, (list, tuple)) or len(line) < 2:
                continue
            line_info = line[1]
            if not isinstance(line_info, (list, tuple)) or not line_info:
                continue
            line_text = str(line_info[0]).strip()
            if line_text:
                texts.append(line_text)
    return texts


def validate_pdf(file_bytes: bytes) -> None:
    if not file_bytes.startswith(b'%PDF'):
        raise ValueError('Only PDF documents are supported.')


def extract_native_pdf_text(file_bytes: bytes) -> tuple[str, int]:
    native_text_start = start_timer()
    pdf = pdfium.PdfDocument(io.BytesIO(file_bytes))
    page_texts = []

    try:
        for page_index in range(len(pdf)):
            page = pdf.get_page(page_index)
            try:
                text_page = page.get_textpage()
                try:
                    page_texts.append(text_page.get_text_bounded())
                finally:
                    text_page.close()
            finally:
                page.close()
    finally:
        pdf.close()

    normalized_text = '\n'.join(normalize_lines('\n'.join(page_texts)))
    log_stage_timing(
        logger,
        'native_pdf_text',
        native_text_start,
        pages=len(page_texts),
        text_length=len(normalized_text),
    )
    return normalized_text, len(page_texts)


def should_use_native_text(native_text: str, document_settings) -> bool:
    minimum_chars = document_settings.get('native_text_min_chars', 200)
    minimum_lines = document_settings.get('native_text_min_lines', 5)
    normalized_lines = normalize_lines(native_text)
    return len(native_text) >= minimum_chars and len(normalized_lines) >= minimum_lines


def extract_pdf_text(file_bytes: bytes) -> str:
    total_start = start_timer()
    validate_pdf(file_bytes)

    document_settings = config.get_document_config()
    if document_settings.get('native_text_enabled', True):
        native_text, native_page_count = extract_native_pdf_text(file_bytes)
        if should_use_native_text(native_text, document_settings):
            log_stage_timing(
                logger,
                'document_extract_total',
                total_start,
                source='native_text',
                pages=native_page_count,
                text_length=len(native_text),
            )
            return native_text

    ocr_settings = config.get_ocr_config()
    if not ocr_settings['enabled']:
        raise ValueError('PaddleOCR document parsing is disabled in settings.')

    ocr_engine = build_ocr_instance(ocr_settings)
    page_images = render_pdf_pages_to_images(file_bytes, ocr_settings['pdf_render_scale'])
    if not page_images:
        log_stage_timing(logger, 'document_extract_total', total_start, source='ocr', pages=0, text_length=0)
        return ''

    texts = []
    ocr_start = start_timer()
    for page_image in page_images:
        page_result = ocr_engine.ocr(page_image, cls=ocr_settings['use_angle_cls'])
        texts.extend(extract_paddle_text(page_result))
    log_stage_timing(
        logger,
        'ocr_inference',
        ocr_start,
        pages=len(page_images),
        extracted_lines=len(texts),
        use_angle_cls=ocr_settings['use_angle_cls'],
    )

    normalized_text = '\n'.join(normalize_lines('\n'.join(texts)))
    log_stage_timing(
        logger,
        'document_extract_total',
        total_start,
        source='ocr',
        pages=len(page_images),
        text_length=len(normalized_text),
    )
    return normalized_text


async def get_resume_text(file_bytes: bytes) -> str:
    return await asyncio.to_thread(extract_pdf_text, file_bytes)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='PDF text extraction test entry for document module.')
    parser.add_argument('pdf_path', help='Path to the PDF resume file.')
    parser.add_argument(
        '--preview-lines',
        type=int,
        default=60,
        help='How many extracted lines to print for quick inspection.',
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f'PDF file not found: {pdf_path}')

    file_bytes = pdf_path.read_bytes()
    resume_text = asyncio.run(get_resume_text(file_bytes))

    lines = resume_text.splitlines()
    preview_lines = lines[:args.preview_lines]
    print(f'Extracted chars: {len(resume_text)}')
    print(f'Extracted lines: {len(lines)}')
    print('--- Preview ---')
    print('\n'.join(preview_lines))
