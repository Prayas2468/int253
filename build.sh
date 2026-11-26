#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input

python manage.py migrate --no-input

# Ensure the default admin/demo accounts exist (idempotent; never resets passwords).
python manage.py bootstrap_accounts

# Optional: seed the 2,400-row synthetic demo dataset on first deploy.
# Safe to enable — seeding is idempotent and skips projects that already exist.
# python manage.py generate_synthetic_data --seed-db