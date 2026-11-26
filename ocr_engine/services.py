"""OCR engine for BhoomiAI.

Extracts raw text from images/PDFs and turns it into structured land-record
fields. Tesseract is used when available; text-layer PDFs and a filename
fallback keep the feature usable on machines without the binary.
"""

import os
import re
import shutil
from pathlib import Path
from io import BytesIO

try:  # Pillow is required for image handling
    from PIL import Image
    HAS_PIL = True
except Exception:  # pragma: no cover - defensive
    Image = None
    HAS_PIL = False

try:
    import pytesseract
    HAS_TESSERACT = True
except Exception:  # pragma: no cover - defensive
    pytesseract = None
    HAS_TESSERACT = False

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except Exception:  # pragma: no cover - defensive
    fitz = None
    HAS_PYMUPDF = False

try:  # python-docx for .docx files
    import docx
    HAS_DOCX = True
except Exception:  # pragma: no cover - defensive
    docx = None
    HAS_DOCX = False

try:  # openpyxl for .xlsx / .xlsm files
    import openpyxl
    HAS_OPENPYXL = True
except Exception:  # pragma: no cover - defensive
    openpyxl = None
    HAS_OPENPYXL = False

try:  # pandas reads spreadsheets (openpyxl for .xlsx, xlrd for legacy .xls)
    import pandas as pd
    HAS_PANDAS = True
except Exception:  # pragma: no cover - defensive
    pd = None
    HAS_PANDAS = False


def _configure_tesseract():
    """Point pytesseract at a Tesseract install that is not on PATH."""
    if not HAS_TESSERACT:
        return False
    candidates = [
        os.environ.get('TESSERACT_CMD'),
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        shutil.which('tesseract'),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            pytesseract.pytesseract.tesseract_cmd = str(candidate)
            return True
    return False


TESSERACT_READY = _configure_tesseract()


FIELD_PATTERNS = {
    'Survey Number': [
        r'(?:survey|khasra|plot|parcel)\s*(?:no\.?|number|#)?\s*[:\-]\s*([A-Za-z0-9][A-Za-z0-9/\-\. ]{0,30})',
        r'(?:survey|khasra|plot)\s+([0-9]+(?:/[0-9A-Za-z\-]+)?)',
    ],
    'District': [
        r'district\s*[:\-]\s*([A-Za-z][A-Za-z .]{1,40})',
        r'\bdistrict\s+of\s+([A-Za-z][A-Za-z .]{1,40})',
    ],
    'Area': [
        r'(?:area|extent)\s*[:\-]\s*([0-9][0-9.,]*\s*(?:sq\.?\s*(?:ft|m|yd|km)|acres?|hectares?|gunta[s]?)?)',
        r'([0-9][0-9.,]*\s*(?:acres?|hectares?|sq\.?\s*ft))',
    ],
    'Owner Name': [
        r'(?:owner|land\s*owner|name\s*of\s*owner)\s*[:\-]\s*([A-Za-z][A-Za-z .]{1,50})',
        r'(?:owner|pattadar)\s*[:\-]\s*([A-Za-z][A-Za-z .]{1,50})',
    ],
}


class OCREngine:
    """Extract text and structured fields from a land document."""

    def __init__(self):
        self.confidence = 0.0
        self.last_error = None

    # ------------------------------------------------------------------
    # Text extraction
    # ------------------------------------------------------------------
    def _pdf_text_layer(self, path: Path) -> str:
        if not HAS_PYMUPDF:
            return ''
        try:
            doc = fitz.open(str(path))
            parts = [page.get_text() for page in doc]
            doc.close()
            return '\n'.join(parts).strip()
        except Exception as exc:  # pragma: no cover - defensive
            self.last_error = str(exc)
            return ''

    def _pdf_to_images(self, path: Path):
        if not HAS_PYMUPDF or not HAS_PIL:
            return []
        images = []
        try:
            doc = fitz.open(str(path))
            for page in doc:
                pix = page.get_pixmap(dpi=200)
                images.append(Image.open(BytesIO(pix.tobytes('png'))))
            doc.close()
        except Exception as exc:  # pragma: no cover - defensive
            self.last_error = str(exc)
        return images

    def _ocr_image(self, image) -> str:
        if not (HAS_TESSERACT and TESSERACT_READY):
            return ''
        try:
            return pytesseract.image_to_string(image)
        except Exception as exc:  # pragma: no cover - defensive
            self.last_error = str(exc)
            return ''

    # ------------------------------------------------------------------
    # Non-OCR text extraction (Word / Excel / CSV)
    # ------------------------------------------------------------------
    def _docx_text(self, path: Path) -> str:
        """Extract text (paragraphs + table cells) from a .docx file."""
        if not HAS_DOCX:
            self.last_error = 'python-docx is not installed, cannot read Word documents'
            return ''
        try:
            document = docx.Document(str(path))
            parts = [p.text for p in document.paragraphs if p.text.strip()]
            for table in document.tables:
                for row in table.rows:
                    cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if cells:
                        parts.append(' | '.join(cells))
            return '\n'.join(parts).strip()
        except Exception as exc:  # pragma: no cover - defensive
            self.last_error = f'Word document could not be read: {exc}'
            return ''

    def _excel_text(self, path: Path) -> str:
        """Extract cell text from .xlsx / .xlsm / .xls spreadsheets."""
        if not (HAS_PANDAS or HAS_OPENPYXL):
            self.last_error = 'No Excel reader available (pandas/openpyxl not installed)'
            return ''
        # pandas handles .xlsx (openpyxl) and legacy .xls (xlrd) uniformly.
        if HAS_PANDAS:
            try:
                sheets = pd.read_excel(str(path), header=None, sheet_name=None, dtype=str)
                parts = []
                for sheet_name, frame in sheets.items():
                    parts.append(f'[{sheet_name}]')
                    for row in frame.values:
                        cells = [
                            str(cell).strip()
                            for cell in row
                            if cell is not None
                            and str(cell).strip()
                            and str(cell).strip().lower() != 'nan'
                        ]
                        if cells:
                            parts.append(' | '.join(cells))
                text = '\n'.join(parts).strip()
                if text:
                    return text
            except Exception as exc:  # pragma: no cover - defensive
                self.last_error = f'Excel file could not be read: {exc}'
        # Fallback for openpyxl-native workbooks.
        if HAS_OPENPYXL and path.suffix.lower() in ('.xlsx', '.xlsm'):
            try:
                workbook = openpyxl.load_workbook(filename=str(path), read_only=True, data_only=True)
                parts = []
                for sheet in workbook.worksheets:
                    for row in sheet.iter_rows(values_only=True):
                        cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
                        if cells:
                            parts.append(' | '.join(cells))
                try:
                    workbook.close()
                except Exception:  # pragma: no cover - defensive
                    pass
                return '\n'.join(parts).strip()
            except Exception as exc:  # pragma: no cover - defensive
                self.last_error = f'Excel file could not be read: {exc}'
        return ''

    def _csv_text(self, path: Path) -> str:
        """Extract text from a CSV file."""
        import csv

        try:
            parts = []
            with open(path, 'r', encoding='utf-8-sig', errors='replace', newline='') as handle:
                for row in csv.reader(handle):
                    cells = [cell.strip() for cell in row if cell and cell.strip()]
                    if cells:
                        parts.append(' | '.join(cells))
            return '\n'.join(parts).strip()
        except Exception as exc:  # pragma: no cover - defensive
            self.last_error = f'CSV file could not be read: {exc}'
            return ''

    def extract_text(self, file_path):
        """Return {'text', 'confidence', 'error'} for a file.

        Supported: PDF, images (OCR), Word ``.docx``, Excel ``.xls/.xlsx/.xlsm``
        and CSV. Unsupported or unreadable files never raise — they return an
        ``error`` string so the caller can mark the document as failed gracefully.
        """
        path = Path(file_path)
        if not path.exists():
            return {'text': '', 'confidence': 0.0, 'error': 'File not found'}

        suffix = path.suffix.lower()
        text = ''
        error = None
        self.last_error = None

        try:
            if suffix == '.pdf':
                # Prefer the embedded text layer, fall back to rasterising.
                text = self._pdf_text_layer(path)
                if len(text) < 20:
                    pages = self._pdf_to_images(path)
                    text = '\n'.join(self._ocr_image(img) for img in pages).strip()
            elif suffix in {'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.webp'}:
                if HAS_PIL:
                    with Image.open(path) as image:
                        text = self._ocr_image(image)
                else:
                    error = 'Pillow is not installed'
            elif suffix == '.docx':
                text = self._docx_text(path)
            elif suffix in {'.xlsx', '.xlsm', '.xls'}:
                text = self._excel_text(path)
            elif suffix == '.csv':
                text = self._csv_text(path)
            elif suffix == '.doc':
                error = (
                    'Legacy .doc format is not supported for text extraction. '
                    'Please save the file as .docx or PDF.'
                )
            else:
                error = 'Unsupported file format for text extraction'
        except Exception as exc:  # never crash the request on a bad file
            error = f'Could not read this file: {exc}'
            text = ''

        if not text and not error:
            error = self.last_error or 'No readable text found'

        alnum = len(re.findall(r'[A-Za-z0-9]', text))
        self.confidence = round((alnum / len(text)) * 100, 1) if text else 0.0
        return {'text': text, 'confidence': self.confidence, 'error': error}

    # ------------------------------------------------------------------
    # Field parsing
    # ------------------------------------------------------------------
    def _match(self, text, patterns):
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return ' '.join(match.group(1).split()).strip(' .,-')
        return ''

    def _from_filename(self, path: Path) -> dict:
        stem = path.stem.replace('_', ' ').replace('-', ' ')
        data = {}
        survey = re.search(r'\b(\d{1,4}(?:/\d{1,4}[A-Za-z]?)?)\b', stem)
        if survey:
            data['Survey Number'] = survey.group(1)
        for district in (
            'Pune', 'Mumbai', 'Nashik', 'Nagpur', 'Delhi', 'Jaipur', 'Surat',
            'Ahmedabad', 'Bengaluru', 'Chennai', 'Hyderabad', 'Kolkata',
        ):
            if district.lower() in stem.lower():
                data['District'] = district
                break
        area = re.search(r'(\d+(?:\.\d+)?)\s*(acre|acres|hectare|hectares|sq\.?\s*ft)', stem, re.IGNORECASE)
        if area:
            data['Area'] = f'{area.group(1)} {area.group(2)}'
        return data

    def process(self, file_path):
        """Return a list of {name, value, confidence, is_valid} dicts."""
        path = Path(file_path)
        result = self.extract_text(path)
        text = result.get('text') or ''
        base_confidence = result.get('confidence') or 0.0
        self.last_error = result.get('error')

        values = {}
        # Only parse fields when text was actually extracted. If extraction
        # failed (unsupported/unreadable file) leave every field undetected so
        # the caller can mark the document as failed.
        if text:
            for name, patterns in FIELD_PATTERNS.items():
                value = self._match(text, patterns)
                if value:
                    values[name] = value

            # Fill gaps from the filename so a demo upload still produces fields.
            if len(values) < 2:
                for name, value in self._from_filename(path).items():
                    values.setdefault(name, value)

        fields = []
        for name in ('Survey Number', 'District', 'Area', 'Owner Name'):
            value = values.get(name, '')
            if value:
                # Field-level confidence tracks overall OCR quality.
                confidence = round(min(99.0, max(35.0, base_confidence or 60.0)), 1)
                fields.append({
                    'name': name,
                    'value': value,
                    'confidence': confidence,
                    'is_valid': confidence >= 50,
                })
            else:
                fields.append({
                    'name': name,
                    'value': 'Not detected',
                    'confidence': 0.0,
                    'is_valid': False,
                })

        self.confidence = round(
            sum(f['confidence'] for f in fields) / len(fields), 1
        ) if fields else 0.0
        return fields
