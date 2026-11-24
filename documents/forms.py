import os

from django import forms
from .models import LandDocument

ALLOWED_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.webp'}
MAX_UPLOAD_MB = 10


class DocumentUploadForm(forms.ModelForm):
    original_name = forms.CharField(
        required=False,
        label='Document title',
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'e.g. Survey 142/2 - Pune',
        }),
    )

    class Meta:
        model = LandDocument
        fields = ['file', 'original_name', 'survey_number', 'district', 'state', 'area', 'owner_name']
        widgets = {
            'file': forms.ClearableFileInput(attrs={
                'class': 'form-input file-input',
                'accept': '.pdf,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp',
            }),
            'survey_number': forms.TextInput(attrs={
                'class': 'form-input', 'placeholder': 'e.g. 142/2',
            }),
            'district': forms.TextInput(attrs={
                'class': 'form-input', 'placeholder': 'e.g. Pune',
            }),
            'state': forms.TextInput(attrs={
                'class': 'form-input', 'placeholder': 'e.g. Maharashtra',
            }),
            'area': forms.TextInput(attrs={
                'class': 'form-input', 'placeholder': 'e.g. 1.25 acres',
            }),
            'owner_name': forms.TextInput(attrs={
                'class': 'form-input', 'placeholder': 'Owner / pattadar name',
            }),
        }

    def clean_file(self):
        upload = self.cleaned_data.get('file')
        if not upload:
            return upload
        extension = os.path.splitext(upload.name)[1].lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise forms.ValidationError(
                'Unsupported file type. Upload a PDF or image (PNG, JPG, TIFF, BMP, WEBP).'
            )
        if upload.size > MAX_UPLOAD_MB * 1024 * 1024:
            raise forms.ValidationError(f'File is too large. Maximum size is {MAX_UPLOAD_MB} MB.')
        return upload
