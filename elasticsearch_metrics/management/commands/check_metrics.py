import sys
import logging
from django.core.management.base import BaseCommand, CommandError

from django.utils.termcolors import colorize

from elasticsearch_metrics.registry import registry
from elasticsearch_metrics import exceptions
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

        out_of_sync_count = 0
        self.stdout.write("Checking for outdated index templates...")
        for app_label in app_labels:
            metrics = registry.get_metrics(app_label=app_label)
            for metric in metrics:
                try:
                    metric.check_index_template(using=connection)
                except (
                    exceptions.IndexTemplateNotFoundError,
                    exceptions.IndexTemplateOutOfSyncError,
                ) as error:
                    self.stdout.write("  " + error.args[0])
                    out_of_sync_count += 1

        if out_of_sync_count:
            self.stdout.write(
                "{} index template(s) out of sync.".format(out_of_sync_count),
                style.ERROR,
            )
            cmd = colorize("python manage.py sync_metrics", opts=("bold",))
            self.stdout.write("Run {cmd} to synchronize.".format(cmd=cmd))
            sys.exit(1)
        else:
            self.stdout.write("All metrics in sync.", style.SUCCESS)
