"""Heuristic duplicate detection for land documents."""

from difflib import SequenceMatcher

from .models import DuplicateCandidate


def _norm(value):
    return ' '.join((value or '').lower().split())


def similarity_score(a, b):
    """Return a 0..1 similarity score between two documents."""
    survey_a, survey_b = _norm(a.survey_number), _norm(b.survey_number)
    district_a, district_b = _norm(a.district), _norm(b.district)
    owner_a, owner_b = _norm(a.owner_name), _norm(b.owner_name)
    area_a, area_b = _norm(a.area), _norm(b.area)

    score = 0.0
    if survey_a and survey_a == survey_b:
        score += 0.55
        if district_a and district_a == district_b:
            score += 0.30
    if owner_a and owner_a == owner_b:
        score += 0.20
    if area_a and area_a == area_b:
        score += 0.15

    fingerprint_a = ' '.join([survey_a, district_a, owner_a, area_a])
    fingerprint_b = ' '.join([survey_b, district_b, owner_b, area_b])
    if fingerprint_a.strip() and fingerprint_b.strip():
        score += 0.10 * SequenceMatcher(None, fingerprint_a, fingerprint_b).ratio()

    return round(min(1.0, score), 3)


def find_duplicates(document, threshold=0.6):
    """Create DuplicateCandidate rows for documents similar to ``document``."""
    from documents.models import LandDocument

    others = (
        LandDocument.objects
        .filter(owner=document.owner)
        .exclude(pk=document.pk)
    )

    created = []
    for other in others:
        score = similarity_score(document, other)
        if score < threshold:
            continue
        candidate, was_created = DuplicateCandidate.objects.get_or_create(
            document=document,
            matched_document=other,
            defaults={'similarity': score},
        )
        if not was_created and score > candidate.similarity:
            candidate.similarity = score
            candidate.save(update_fields=['similarity'])
        created.append(candidate)
    return created
