import logging
from django.core.management.base import BaseCommand, CommandError

from django.utils.termcolors import colorize

from elasticsearch_metrics.registry import djelme_registry
from elasticsearch_metrics import exceptions
from elasticsearch_metrics.management.color import color_style


class Command(BaseCommand):
    help = "Check if registered recordtypes have a corresponding index templates in Elasticsearch."

    def add_arguments(self, parser):
        parser.add_argument("app_label", nargs="?", help="App label of an application.")

    def handle(self, *args, **options):
        # Avoid elasticsearch requests from getting logged
        logging.getLogger("elasticsearch").setLevel(logging.CRITICAL)
        style = color_style()
        _app_labels = (
            [options["app_label"]]
            if options["app_label"]
            else list(djelme_registry.each_app_label())
        )

        out_of_sync_count = 0
        self.stdout.write("Checking for outdated index templates...")
        for _app_label in _app_labels:
            for _recordtype in djelme_registry.each_recordtype(app_label=_app_label):
                try:
                    _recordtype.check_djelme_setup()
                except exceptions.DjelmeSetupError as error:
                    self.stdout.write("  " + error.args[0])
                    out_of_sync_count += 1

        if out_of_sync_count:
            self.stdout.write(
                f"{out_of_sync_count} index template(s) not set up.",
                style.ERROR,
            )
            cmd = colorize("python manage.py djelme_backend_setup", opts=("bold",))
            self.stdout.write(f"Run {cmd} to set up index templates.")
            raise CommandError(1)
        else:
            self.stdout.write("All djelme recordtypes set up.", style.SUCCESS)
