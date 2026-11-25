from django.core.management.base import BaseCommand, CommandError

from predictions import ml, services


class Command(BaseCommand):
    help = 'Train and compare the delay-prediction models and activate the best pipeline.'

    def handle(self, *args, **options):
        try:
            metrics = ml.train_models()
        except FileNotFoundError as exc:
            raise CommandError(str(exc)) from exc

        model, metrics = services.train_and_register()
        self.stdout.write(self.style.SUCCESS(f'Active model: {model.name} ({model.version})'))
        for name, values in metrics['algorithms'].items():
            self.stdout.write(
                f'  {name:20s} accuracy={values["accuracy"]:.3f} '
                f'precision={values["precision"]:.3f} recall={values["recall"]:.3f} '
                f'f1={values["f1"]:.3f} roc_auc={values["roc_auc"]:.3f}'
            )
        self.stdout.write(f'Selected: {metrics["selected"]}')
        if metrics.get('regressor'):
            reg = metrics['regressor']
            self.stdout.write(
                f'Delay-days regressor: MAE={reg["mae"]:.1f} days, '
                f'RMSE={reg["rmse"]:.1f}, R2={reg["r2"]:.3f}'
            )
        self.stdout.write(f'Metrics written to {ml.METRICS_PATH}')
