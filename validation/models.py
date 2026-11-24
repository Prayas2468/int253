from django.db import models

class ValidationRule(models.Model):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class ValidationResult(models.Model):
    document = models.ForeignKey(
        'documents.LandDocument',
        on_delete=models.CASCADE,
        related_name='validations',
    )
    rule = models.ForeignKey(ValidationRule, on_delete=models.CASCADE)
    passed = models.BooleanField()
    message = models.TextField(blank=True)
    checked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-checked_at']

    def __str__(self):
        return f"{self.rule.name}: {'PASS' if self.passed else 'FAIL'}"
