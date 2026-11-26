from django.db import models
from django.conf import settings

class LandDocument(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('done', 'Done'),
        ('failed', 'Failed'),
    ]
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='documents',
    )
    file = models.FileField(upload_to='documents/%Y/%m/')
    original_name = models.CharField(max_length=255)
    survey_number = models.CharField(max_length=64, blank=True, db_index=True)
    district = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=80, blank=True, db_index=True)
    area = models.CharField(max_length=64, blank=True)
    owner_name = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    confidence = models.FloatField(default=0.0)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    # Populated when OCR cannot extract text (e.g. unsupported or unreadable file).
    processing_error = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.original_name} ({self.status})"


class ExtractedField(models.Model):
    document = models.ForeignKey(
        LandDocument,
        on_delete=models.CASCADE,
        related_name='fields',
    )
    field_name = models.CharField(max_length=80)
    field_value = models.TextField()
    confidence = models.FloatField(default=0.0)
    is_valid = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.field_name}: {self.field_value[:40]}"
