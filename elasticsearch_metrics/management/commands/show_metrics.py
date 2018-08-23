from django.core.management.base import BaseCommand, CommandError

from elasticsearch_metrics.registry import registry
from elasticsearch_metrics.management.color import color_style


class Command(BaseCommand):
    help = "Pretty-print a listing of all registered metrics."

    def add_arguments(self, parser):
        parser.add_argument("app_label", nargs="?", help="App label of an application.")

    def handle(self, *args, **options):
        style = color_style()
        if options["app_label"]:
            if options["app_label"] not in registry.all_metrics:
                raise CommandError(
                    "No metrics found for app '{}'".format(options["app_label"])
                )
            app_labels = [options["app_label"]]
        else:
            app_labels = registry.all_metrics.keys()
        for app_label in app_labels:
            self.stdout.write(
                "Metrics for '{}':".format(app_label), style.MIGRATE_HEADING
            )
            metrics = registry.get_metrics(app_label=app_label)
            for metric in metrics:
                metric_name = style.METRIC(metric.__name__)
                template_name = metric._template_name
                template = style.ES_TEMPLATE(metric._template)
                self.stdout.write(
                    "  {metric_name} -> {template_name} ({template})".format(**locals())
                )
