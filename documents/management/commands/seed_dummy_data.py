"""Seed realistic demo land records so maps, charts and tables are populated.

Usage:
    python manage.py seed_dummy_data
    python manage.py seed_dummy_data --force   # add another batch
"""

from datetime import timedelta
from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import CustomUser
from documents.models import ExtractedField, LandDocument
from duplicates.services import find_duplicates
from notifications.models import Notification
from validation.services import ensure_default_rules, validate_document

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except Exception:  # pragma: no cover
    HAS_PIL = False


RECORDS = [
    # district, state, survey, area, owner, status, days_ago, confidence
    ('Pune', 'Maharashtra', '142/2', '1.25 acres', 'Ramesh Deshmukh', 'done', 2, 94.5),
    ('Nashik', 'Maharashtra', '88/1', '2.10 acres', 'Sunita Patil', 'done', 5, 91.2),
    ('Mumbai', 'Maharashtra', '45/3', '0.35 acres', 'Anil Mehta', 'processing', 1, 0),
    ('Lucknow', 'Uttar Pradesh', '210/7', '3.40 acres', 'Ram Prasad', 'done', 8, 89.7),
    ('Varanasi', 'Uttar Pradesh', '77/5', '0.90 acres', 'Meena Devi', 'pending', 3, 0),
    ('Noida', 'Uttar Pradesh', '512/1', '1.75 acres', 'Vikram Singh', 'done', 12, 96.1),
    ('New Delhi', 'Delhi', '19/8', '0.50 acres', 'Harpreet Kaur', 'done', 6, 93.4),
    ('Jaipur', 'Rajasthan', '301/4', '4.20 acres', 'Mahendra Rathore', 'done', 15, 87.9),
    ('Ahmedabad', 'Gujarat', '64/9', '2.65 acres', 'Nilesh Patel', 'pending', 4, 0),
    ('Bengaluru', 'Karnataka', '128/6', '1.10 acres', 'Lakshmi Rao', 'done', 9, 92.8),
    ('Chennai', 'Tamil Nadu', '92/2', '0.80 acres', 'K. Subramanian', 'failed', 7, 0),
    ('Hyderabad', 'Telangana', '155/3', '2.00 acres', 'Farhan Ali', 'processing', 2, 0),
    ('Kolkata', 'West Bengal', '33/1', '1.45 acres', 'Arnab Ghosh', 'pending', 11, 0),
    ('Bhopal', 'Madhya Pradesh', '208/5', '5.30 acres', 'Deepak Verma', 'done', 18, 90.3),
    ('Patna', 'Bihar', '61/7', '1.95 acres', 'Ravi Kumar', 'done', 21, 88.6),
]

DUPLICATE_RECORD = (
    'Pune', 'Maharashtra', '142/2', '1.25 acres', 'Ramesh Deshmukh', 'done', 1, 95.2
)


def _font(size, bold=False):
    candidates = [
        r'C:\Windows\Fonts\segoeuib.ttf' if bold else r'C:\Windows\Fonts\segoeui.ttf',
        r'C:\Windows\Fonts\arialbd.ttf' if bold else r'C:\Windows\Fonts\arial.ttf',
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _render_record(record):
    """Create a PNG that looks like a scanned land record."""
    district, state, survey, area, owner = record[:5]
    if not HAS_PIL:
        return None
    width, height = 900, 1200
    image = Image.new('RGB', (width, height), '#F8F5EC')
    draw = ImageDraw.Draw(image)

    draw.rectangle([0, 0, width, 14], fill='#17365D')
    draw.rectangle([40, 40, width - 40, height - 40], outline='#B9AE93', width=3)
    draw.text((60, 70), 'RECORD OF RIGHTS', font=_font(38, True), fill='#17365D')
    draw.text((60, 122), 'Government of India  |  Land Records Department', font=_font(18), fill='#5B6B80')
    draw.line([60, 160, width - 60, 160], fill='#B9AE93', width=2)

    rows = [
        ('Survey / Khasra No.', survey),
        ('District', district),
        ('State', state),
        ('Area', area),
        ('Owner / Pattadar', owner),
        ('Document Type', 'Record of Rights (RoR)'),
        ('Issue Date', timezone.localdate().strftime('%d %B %Y')),
    ]
    y = 210
    for label, value in rows:
        draw.text((70, y), label.upper(), font=_font(16), fill='#7A879A')
        draw.text((70, y + 30), str(value), font=_font(28, True), fill='#1B2B42')
        y += 96

    draw.line([60, y + 10, width - 60, y + 10], fill='#B9AE93', width=2)
    draw.text((70, y + 40), 'This is a computer-generated demonstration record.', font=_font(18), fill='#7A879A')
    draw.text((70, y + 72), 'BhoomiAI demo data - not a legal document.', font=_font(18), fill='#7A879A')

    draw.ellipse([width - 240, y - 40, width - 80, y + 120], outline='#C9922E', width=4)
    draw.text((width - 218, y + 10), 'VERIFIED', font=_font(22, True), fill='#C9922E')

    buffer = BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


class Command(BaseCommand):
    help = 'Create realistic demo land records across Indian states.'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Add demo records even if documents already exist.')

    def handle(self, *args, **options):
        if LandDocument.objects.exists() and not options['force']:
            self.stdout.write(self.style.WARNING(
                'Documents already exist; skipping seed. Use --force to add another batch.'
            ))
            return

        ensure_default_rules()

        user = (
            CustomUser.objects.filter(is_superuser=True).first()
            or CustomUser.objects.first()
        )
        if user is None:
            user = CustomUser.objects.create_user(
                username='demo',
                email='demo@bhoomiai.local',
                password='BhoomiAI@2026',
                full_name='Demo Administrator',
                role='admin',
            )
            self.stdout.write('Created demo user demo@bhoomiai.local / BhoomiAI@2026')

        created = []
        for index, record in enumerate(RECORDS + [DUPLICATE_RECORD], start=1):
            district, state, survey, area, owner, status, days_ago, confidence = record
            document = LandDocument(
                owner=user,
                original_name=f'{district} Survey {survey} - Record of Rights.png',
                survey_number=survey,
                district=district,
                state=state,
                area=area,
                owner_name=owner,
                status=status,
                confidence=confidence,
            )
            payload = _render_record(record)
            if payload:
                document.file.save(
                    f'demo-{index:02d}-{district.lower()}-{survey.replace("/", "-")}.png',
                    ContentFile(payload),
                    save=False,
                )
            else:
                document.file.name = f'demo-{index:02d}.txt'
            document.save()

            uploaded = timezone.now() - timedelta(days=days_ago, hours=index)
            processed = uploaded + timedelta(minutes=12) if status in {'done', 'failed'} else None
            LandDocument.objects.filter(pk=document.pk).update(
                uploaded_at=uploaded, processed_at=processed
            )

            if status in {'done', 'failed'}:
                field_values = [
                    ('Survey Number', survey, confidence or 0),
                    ('District', district, confidence or 0),
                    ('Area', area, confidence or 0),
                    ('Owner Name', owner, confidence or 0),
                ]
                if status == 'failed':
                    field_values = [
                        ('Survey Number', 'Not detected', 0),
                        ('District', 'Not detected', 0),
                        ('Area', 'Not detected', 0),
                        ('Owner Name', 'Not detected', 0),
                    ]
                for name, value, field_confidence in field_values:
                    ExtractedField.objects.create(
                        document=document,
                        field_name=name,
                        field_value=value,
                        confidence=field_confidence,
                        is_valid=field_confidence >= 50,
                    )
                validate_document(document)

            created.append(document)

        # Create duplicate candidates from the intentional duplicate pair.
        duplicate_doc = created[-1]
        candidates = find_duplicates(duplicate_doc)
        if not candidates:
            # The first record and duplicate share survey/district/owner, so this
            # should normally match; fall back to the first done document.
            from duplicates.models import DuplicateCandidate
            first = created[0]
            DuplicateCandidate.objects.get_or_create(
                document=duplicate_doc,
                matched_document=first,
                defaults={'similarity': 0.98},
            )

        messages = [
            'Welcome to BhoomiAI. Your demo workspace is ready.',
            f'{len(created)} demo land records were imported across Indian states.',
            'Possible duplicate detected: Pune survey 142/2 appears twice.',
            'OCR finished for Pune survey 142/2 at 94.5% confidence.',
            'Validation completed for Lucknow survey 210/7.',
        ]
        Notification.objects.filter(user=user, message__startswith='Welcome to BhoomiAI.').delete()
        for message in messages:
            Notification.objects.create(user=user, message=message)

        self.stdout.write(self.style.SUCCESS(
            f'Seeded {len(created)} documents, {len(candidates) or 1} duplicate candidate(s) '
            f'and {len(messages)} notifications for {user.email}.'
        ))
