"""Tests for the document upload form's file-type validation."""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from .forms import DocumentUploadForm


class DocumentUploadFormTests(SimpleTestCase):
    def _is_valid(self, name):
        form = DocumentUploadForm(files={'file': SimpleUploadedFile(name, b'x' * 16)})
        return form.is_valid()

    def test_new_formats_accepted(self):
        for name in ['a.docx', 'a.doc', 'a.xlsx', 'a.xls', 'a.csv']:
            self.assertTrue(self._is_valid(name), f'{name} should be accepted')

    def test_existing_formats_accepted(self):
        for name in ['a.pdf', 'a.png', 'a.jpg', 'a.tiff', 'a.webp']:
            self.assertTrue(self._is_valid(name), f'{name} should be accepted')

    def test_unsupported_formats_rejected(self):
        for name in ['a.txt', 'a.exe', 'a.zip']:
            self.assertFalse(self._is_valid(name), f'{name} should be rejected')