"""Text extraction and overlapping chunking. No OCR for scanned PDFs."""
from io import BytesIO
from pypdf import PdfReader
from .config import MAX_PAGES


def extract_pages(raw: bytes, filename: str) -> list[tuple[int, str]]:
    if filename.lower().endswith('.txt'):
        try:
            text = raw.decode('utf-8-sig')
        except UnicodeDecodeError as exc:
            raise ValueError('Text files must be UTF-8 encoded.') from exc
        return [(1, text)]
    if not filename.lower().endswith('.pdf'):
        raise ValueError('Only PDF and TXT files are supported.')
    try:
        reader = PdfReader(BytesIO(raw), strict=False)
        if reader.is_encrypted:
            raise ValueError('Password-protected PDFs are not supported.')
        if len(reader.pages) > MAX_PAGES:
            raise ValueError(f'PDF has too many pages (maximum: {MAX_PAGES}).')
        pages = [(i + 1, page.extract_text() or '') for i, page in enumerate(reader.pages)]
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError('Unable to read this PDF. Try a text-based, non-encrypted PDF.') from exc
    if not any(s.strip() for _, s in pages):
        raise ValueError('No extractable text found. Scanned PDFs need OCR (not supported yet).')
    return pages


def chunk_pages(pages: list[tuple[int, str]], size: int = 850, overlap: int = 140):
    """Chunks with stable page numbers and character overlap; avoids empty chunks."""
    if not 0 <= overlap < size:
        raise ValueError('overlap must be less than size')
    for page, text in pages:
        text = ' '.join(text.split())
        if not text:
            continue
        start, index = 0, 0
        while start < len(text):
            end = min(len(text), start + size)
            if end < len(text):
                space = text.rfind(' ', start + max(1, size // 2), end)
                if space > start:
                    end = space
            content = text[start:end].strip()
            if content:
                yield {'page': page, 'index': index, 'content': content}
                index += 1
            if end >= len(text):
                break
            next_start = max(start + 1, end - overlap)
            # Avoid starting the next source chunk in the middle of a word.
            if next_start > 0 and next_start < len(text) and text[next_start - 1] != ' ':
                following_space = text.find(' ', next_start, min(end + 1, len(text)))
                if following_space != -1:
                    next_start = following_space + 1
            start = next_start
