"""Extract selectable PDF text and ruled tables without saving uploads."""
from io import BytesIO
import pdfplumber
from fastapi import HTTPException
from pdfminer.pdfdocument import PDFPasswordIncorrect

MAX_BYTES = 10 * 1024 * 1024
MAX_PAGES = 30
MAX_TEXT = 30000


def extract_pdf(content):
    if not content.startswith(b'%PDF-'):
        raise HTTPException(422, 'Choose a valid PDF file.')
    try:
        with pdfplumber.open(BytesIO(content)) as pdf:
            if len(pdf.pages) > MAX_PAGES:
                raise HTTPException(422, 'Use a PDF with at most 30 pages, or export only the relevant course pages.')
            pages, chunks = [], []
            warnings = ['Check the extracted text and tables before comparing. Merged cells, '
                        'borderless tables and complex layouts may need manual correction. '
                        'Detected tables are listed after the other text on each page.']
            readable = False
            for number, page in enumerate(pdf.pages, 1):
                tables = page.find_tables()
                rows = [[[cell or '' for cell in row] for row in table.extract()]
                        for table in tables]
                # Avoid duplicating table cells in the narrative text.
                def outside_tables(obj):
                    if obj.get('object_type') != 'char':
                        return True
                    x = (obj['x0'] + obj['x1']) / 2
                    y = (obj['top'] + obj['bottom']) / 2
                    return not any(t.bbox[0] <= x <= t.bbox[2] and
                                   t.bbox[1] <= y <= t.bbox[3] for t in tables)
                prose = page.filter(outside_tables).extract_text(layout=True).strip()
                parts = [prose] if prose else []
                for i, table in enumerate(rows, 1):
                    lines = [' | '.join(' '.join(cell.split()) for cell in row) for row in table]
                    parts.append(f'[Table {i}]\n' + '\n'.join(lines))
                if not page.chars:
                    warnings.append(f'Page {number} has no selectable text. If it contains a scan, OCR is required; its content was not extracted.')
                else:
                    readable = True
                chunks.append(f'[Page {number}]\n' + '\n\n'.join(parts))
                pages.append({'number': number, 'text': prose, 'tables': rows})
                if sum(len(chunk) + 2 for chunk in chunks) > MAX_TEXT:
                    raise HTTPException(422, 'Extracted text exceeds 30,000 characters. Upload only the relevant course pages.')
                page.close()
            if not readable:
                raise HTTPException(422, 'No selectable text found. This PDF may be scanned: use OCR (text recognition) first, then upload it again.')
            return {'text': '\n\n'.join(chunks), 'pages': pages,
                    'page_count': len(pages), 'warnings': warnings}
    except HTTPException:
        raise
    except PDFPasswordIncorrect:
        raise HTTPException(422, 'This PDF is password protected. Upload an unlocked copy.') from None
    except Exception as error:
        # Recent pdfplumber versions wrap pdfminer errors.
        if any(isinstance(arg, PDFPasswordIncorrect) for arg in error.args):
            raise HTTPException(422, 'This PDF is password protected. Upload an unlocked copy.') from None
        # Never echo parser errors or document text to the client or logs.
        raise HTTPException(422, 'Cannot read this PDF. Try exporting a fresh, unlocked PDF.') from None
