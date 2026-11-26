"""Tests for the OCR text-extraction engine across supported file formats."""

import os
import tempfile

from django.test import SimpleTestCase

from .services import OCREngine


class OCRTextExtractionTests(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def _path(self, name):
        return os.path.join(self.tmp, name)

    def test_docx_extraction(self):
        import docx

        path = self._path('record.docx')
        document = docx.Document()
        document.add_paragraph('Survey No: 142/2')
        document.add_paragraph('District: Pune')
        document.save(path)

        result = OCREngine().extract_text(path)
        self.assertIn('142/2', result['text'])
        self.assertIsNone(result['error'])

    def test_xlsx_extraction(self):
        import openpyxl

        path = self._path('record.xlsx')
        workbook = openpyxl.Workbook()
        worksheet = workbook.active
        worksheet.append(['District', 'Pune'])
        worksheet.append(['Owner', 'Ramesh Deshmukh'])
        workbook.save(path)

        result = OCREngine().extract_text(path)
        self.assertIn('Pune', result['text'])
        self.assertIn('Ramesh', result['text'])

    def test_csv_extraction(self):
        path = self._path('record.csv')
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write('Owner,Ramesh Deshmukh\nDistrict,Pune\n')

        result = OCREngine().extract_text(path)
        self.assertIn('Ramesh', result['text'])

    def test_unsupported_format_is_graceful(self):
        path = self._path('note.txt')
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write('hello')

        result = OCREngine().extract_text(path)
        self.assertEqual(result['error'], 'Unsupported file format for text extraction')
        self.assertEqual(result['text'], '')

    def test_legacy_doc_is_graceful(self):
        path = self._path('legacy.doc')
        with open(path, 'wb') as handle:
            handle.write(b'\x00')

        result = OCREngine().extract_text(path)
        self.assertIn('Legacy .doc', result['error'])

    def test_missing_file_is_graceful(self):
        result = OCREngine().extract_text(self._path('missing.docx'))
        self.assertEqual(result['error'], 'File not found')

    def test_process_returns_no_fields_when_no_text(self):
        path = self._path('note.txt')
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write('hello')

        fields = OCREngine().process(path)
        self.assertTrue(all(f['value'] == 'Not detected' for f in fields))