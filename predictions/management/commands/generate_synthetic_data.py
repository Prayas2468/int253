from django.core.management.base import BaseCommand

from predictions.synthetic import dataset_path, write_dataset


class Command(BaseCommand):
    help = 'Generate the synthetic land-acquisition dataset (2,400 rows by default).'

    def add_arguments(self, parser):
        parser.add_argument('--rows', type=int, default=2400, help='Number of rows to generate.')
        parser.add_argument('--seed', type=int, default=42, help='Random seed for reproducibility.')
        parser.add_argument('--seed-db', action='store_true', help='Import the generated rows into the database.')
        parser.add_argument('--no-predict', action='store_true', help='Skip predictions when seeding the database.')
        parser.add_argument('--limit', type=int, default=0, help='Import only the first N rows when seeding.')

    def handle(self, *args, **options):
        path = write_dataset(rows=options['rows'], seed=options['seed'])
        self.stdout.write(self.style.SUCCESS(f'Wrote {options["rows"]} synthetic rows to {path}'))
        self.stdout.write(f'Dataset: {dataset_path()}')

        if options['seed_db']:
            from predictions import services

            result = services.seed_projects_from_dataset(
                predict=not options['no_predict'],
                limit=options['limit'] or None,
            )
            self.stdout.write(self.style.SUCCESS(
                f'Imported {result["created"]} projects and stored '
                f'{result["predictions"]} predictions.'
            ))
