"""Validation rules for extracted land-record fields."""

import re

from .models import ValidationRule, ValidationResult

DEFAULT_RULES = [
    ('Survey number present', 'A survey / khasra number must be extracted from the document.'),
    ('District present', 'The district name must be identified.'),
    ('Area is numeric', 'The land area must start with a numeric value.'),
    ('Owner name present', 'An owner or pattadar name must be extracted.'),
    ('OCR confidence', 'Average field confidence must be at least 70%.'),
]


def ensure_default_rules():
    rules = {}
    for name, description in DEFAULT_RULES:
        rule, _ = ValidationRule.objects.get_or_create(
            name=name,
            defaults={'description': description, 'active': True},
        )
        rules[name] = rule
    return rules


def _field_map(document):
    return {
        field.field_name: field
        for field in document.fields.all()
    }


def validate_document(document):
    """(Re)run all active validation rules for a document."""
    rules = ensure_default_rules()
    document.validations.all().delete()

    fields = _field_map(document)

    def value(name):
        field = fields.get(name)
        if not field:
            return ''
        return (field.field_value or '').strip()

    survey = value('Survey Number')
    district = value('District')
    area = value('Area')
    owner = value('Owner Name')

    confidences = [f.confidence for f in fields.values() if f.confidence]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    checks = {
        'Survey number present': bool(survey) and survey.lower() != 'not detected',
        'District present': bool(district) and district.lower() != 'not detected',
        'Area is numeric': bool(re.match(r'^\s*\d', area)) and area.lower() != 'not detected',
        'Owner name present': bool(owner) and owner.lower() != 'not detected',
        'OCR confidence': avg_confidence >= 70,
    }

    messages = {
        'Survey number present': f'Survey number: {survey or "missing"}',
        'District present': f'District: {district or "missing"}',
        'Area is numeric': f'Area: {area or "missing"}',
        'Owner name present': f'Owner: {owner or "missing"}',
        'OCR confidence': f'Average confidence: {avg_confidence:.1f}%',
    }

    results = []
    for name, rule in rules.items():
        if not rule.active:
            continue
        results.append(ValidationResult(
            document=document,
            rule=rule,
            passed=bool(checks.get(name)),
            message=messages.get(name, ''),
        ))
    ValidationResult.objects.bulk_create(results)
    return results


def validation_summary(document):
    results = list(document.validations.all())
    total = len(results)
    passed = sum(1 for result in results if result.passed)
    return {
        'total': total,
        'passed': passed,
        'failed': total - passed,
        'percent': round((passed / total) * 100) if total else 0,
    }
