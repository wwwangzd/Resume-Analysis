import argparse
import asyncio
import io
from pathlib import Path
from typing import List

import numpy as np
import pypdfium2 as pdfium
from paddleocr import PaddleOCR

from src import config

paddleOcrInstance = None
paddleOcrSignature = None


def normalize_lines(text: str) -> List[str]:
    lines = text.splitlines()
    cleaned = [line.strip('\t').replace('\t', ' ').strip() for line in lines]
    return [line for line in cleaned if line]


def build_ocr_instance(ocr_settings):
    global paddleOcrInstance
    global paddleOcrSignature

    signature = (
        ocr_settings['lang'],
        ocr_settings['use_angle_cls'],
        ocr_settings['use_gpu'],
        ocr_settings['show_log'],
    )

    if paddleOcrInstance is not None and paddleOcrSignature == signature:
        return paddleOcrInstance

    paddleOcrInstance = PaddleOCR(
        lang=ocr_settings['lang'],
        use_angle_cls=ocr_settings['use_angle_cls'],
        use_gpu=ocr_settings['use_gpu'],
        show_log=ocr_settings['show_log'],
    )
    paddleOcrSignature = signature
    return paddleOcrInstance


def render_pdf_pages_to_images(file_bytes: bytes, render_scale: float) -> List[np.ndarray]:
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


def extract_pdf_text(file_bytes: bytes) -> str:
    validate_pdf(file_bytes)

    ocr_settings = config.get_ocr_config()
    if not ocr_settings['enabled']:
        raise ValueError('PaddleOCR document parsing is disabled in settings.')

    ocr_engine = build_ocr_instance(ocr_settings)
    page_images = render_pdf_pages_to_images(file_bytes, ocr_settings['pdf_render_scale'])
    if not page_images:
        return ''

    texts = []
    for page_image in page_images:
        page_result = ocr_engine.ocr(page_image, cls=ocr_settings['use_angle_cls'])
        texts.extend(extract_paddle_text(page_result))

    return '\n'.join(normalize_lines('\n'.join(texts)))


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
