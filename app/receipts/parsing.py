import os
import io

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


def extract_text(file_path: str, filename: str = '') -> str:
    """Extract plain text from PDF, HTML, or TXT file."""
    ext = os.path.splitext(filename or file_path)[1].lower()
    
    if ext == '.pdf':
        return _extract_pdf(file_path)
    elif ext in ('.html', '.htm'):
        return _extract_html(file_path)
    else:
        return _extract_txt(file_path)


def _extract_pdf(file_path: str) -> str:
    if not HAS_PDFPLUMBER:
        return ''
    text_parts = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    return '\n'.join(text_parts)


def _extract_html(file_path: str) -> str:
    if not HAS_BS4:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        soup = BeautifulSoup(f, 'lxml')
    return soup.get_text(separator='\n')


def _extract_txt(file_path: str) -> str:
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()
