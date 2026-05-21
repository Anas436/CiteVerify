import PyPDF2
from docx import Document
from pathlib import Path


def extract_text_from_pdf(file_path: str) -> str:
    text_parts = []
    with open(file_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return '\n\n'.join(text_parts)


def extract_text_from_docx(file_path: str) -> str:
    doc = Document(file_path)
    text_parts = []
    for paragraph in doc.paragraphs:
        text_parts.append(paragraph.text)
    return '\n'.join(text_parts)


def get_file_text(file_path: str, file_type: str) -> str:
    if file_type == 'pdf':
        return extract_text_from_pdf(file_path)
    elif file_type == 'docx':
        return extract_text_from_docx(file_path)
    else:
        msg = f'Unsupported file type: {file_type}'
        raise ValueError(msg)


def estimate_word_count(text: str) -> int:
    return len(text.split())
