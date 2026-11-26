"""Idempotently create the default admin and demo accounts.

Safe to run on every deploy: existing accounts are left untouched, so a password
changed through the admin panel is never overwritten. Credentials can be
overridden with environment variables (ADMIN_EMAIL, ADMIN_PASSWORD, DEMO_EMAIL,
DEMO_PASSWORD).

Usage:
    python manage.py bootstrap_accounts
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


def _unique_username(user_model, base):
    """Return a username that does not already exist."""
    base = (base or 'user')[:130]
    name = base
    counter = 1
    while user_model.objects.filter(username=name).exists():
        counter += 1
        name = f'{base}{counter}'
    return name


class Command(BaseCommand):
    help = 'Create the default superuser and demo account if they do not exist.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--admin-email',
            default=os.environ.get('ADMIN_EMAIL', 'admin@bhoomiai.com'),
        )
        parser.add_argument(
            '--admin-password',
            default=os.environ.get('ADMIN_PASSWORD', 'Admin@Bhoomi2026'),
        )
        parser.add_argument(
            '--demo-email',
            default=os.environ.get('DEMO_EMAIL', 'demo@bhoomiai.com'),
        )
        parser.add_argument(
            '--demo-password',
            default=os.environ.get('DEMO_PASSWORD', 'Demo@Bhoomi2026'),
        )

    def handle(self, *args, **options):
        user_model = get_user_model()

        self._ensure(
            user_model,
            email=options['admin_email'],
            password=options['admin_password'],
            username='admin',
            full_name='BhoomiAI Administrator',
            role='admin',
            is_staff=True,
            is_superuser=True,
        )
        self._ensure(
            user_model,
            email=options['demo_email'],
            password=options['demo_password'],
            username='demo',
            full_name='Demo User',
            role='user',
            is_staff=False,
            is_superuser=False,
        )

    def _ensure(self, user_model, *, email, password, username, full_name, role,
                is_staff, is_superuser):
        email = (email or '').strip().lower()
        user = user_model.objects.filter(email__iexact=email).first()

        if user is not None:
            # Never reset an existing password. Only escalate privileges if the
            # account exists but is missing the expected flags (e.g. first deploy).
            promoted = False
            if is_staff and not user.is_staff:
                user.is_staff = True
                promoted = True
            if is_superuser and not user.is_superuser:
                user.is_superuser = True
                promoted = True
            if promoted:
                user.save(update_fields=['is_staff', 'is_superuser'])
                self.stdout.write(self.style.WARNING(
                    f'Account already existed and was elevated: {email}'
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    f'Account already exists (left unchanged): {email}'
                ))
            return

        user = user_model(email=email)
        user.username = _unique_username(user_model, username)
        user.full_name = full_name
        user.role = role
        user.is_staff = is_staff
        user.is_superuser = is_superuser
        user.is_active = True
        user.set_password(password)
        user.save()
        self.stdout.write(self.style.SUCCESS(
            f'Created account: {email} (staff={is_staff}, superuser={is_superuser})'
        ))