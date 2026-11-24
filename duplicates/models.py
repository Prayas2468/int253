from django.db import models

class DuplicateCandidate(models.Model):
    document = models.ForeignKey(
        'documents.LandDocument',
        on_delete=models.CASCADE,
        related_name='duplicates',
    )
    matched_document = models.ForeignKey(
        'documents.LandDocument',
        on_delete=models.CASCADE,
        related_name='matched_by',
    )
    similarity = models.FloatField()
    reviewed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-similarity']

    def __str__(self):
        return f"{self.document_id} ~ {self.matched_document_id} ({self.similarity:.0%})"
