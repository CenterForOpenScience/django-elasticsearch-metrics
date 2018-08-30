import sys
import logging
from django.core.management.base import BaseCommand, CommandError

from elasticsearch_metrics.registry import registry
from elasticsearch_metrics.management.color import color_style


class Command(BaseCommand):
    help = "Check if registered metrics have a corresponding index templates in Elasticsearch."

    def add_arguments(self, parser):
        parser.add_argument("app_label", nargs="?", help="App label of an application.")
        parser.add_argument(
            "--connection",
            action="store",
            dest="connection",
            default=None,
            help='Elasticsearch connection to use. Defaults to the "default" connection.',
        )

    def handle(self, *args, **options):
        # Avoid elasticsearch requests from getting logged
        logging.getLogger("elasticsearch").setLevel(logging.CRITICAL)
        style = color_style()
        connection = options["connection"]
        if options["app_label"]:
            if options["app_label"] not in registry.all_metrics:
                raise CommandError(
                    "No metrics found for app '{}'".format(options["app_label"])
                )
            app_labels = [options["app_label"]]
        else:
            app_labels = registry.all_metrics.keys()

        out_of_sync = False
        self.stdout.write("Checking for missing index templates...")
        for app_label in app_labels:
            metrics = registry.get_metrics(app_label=app_label)
            for metric in metrics:
                metric_has_template = metric.check_index_template_exists(
                    using=connection
                )
                if not out_of_sync and not metric_has_template:
                    out_of_sync = True
                if not metric_has_template:
                    metric_name = metric.__name__
                    template_name = metric._template_name
                    self.stdout.write(
                        "  {template_name} does not exist for {metric_name}".format(
                            **locals()
                        ),
                        style.ERROR,
                    )
        if out_of_sync:
            sys.exit(1)
        else:
            self.stdout.write("All metrics in sync.", style.SUCCESS)
