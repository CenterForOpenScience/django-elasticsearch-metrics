from django.core.management.base import BaseCommand, CommandError

from elasticsearch_metrics.registry import djelme_registry
from elasticsearch_metrics.management.color import color_style


class Command(BaseCommand):
    help = "Pretty-print a listing of all registered djelme recordtypes."

    def add_arguments(self, parser):
        parser.add_argument("app_label", nargs="?", help="App label of an application.")

    def handle(self, *args, **options):
        style = color_style()
        if options["app_label"]:
            if options["app_label"] not in djelme_registry.each_app_label():
                raise CommandError(
                    "No recordtypes found for app '{}'".format(options["app_label"])
                )
            app_labels = [options["app_label"]]
        else:
            app_labels = list(djelme_registry.each_app_label())
        for app_label in app_labels:
            self.stdout.write(f"Recordtypes for '{app_label}':", style.MIGRATE_HEADING)
            for _recordtype in djelme_registry.each_recordtype(app_label=app_label):
                _recordtype_name = style.TYPENAME(_recordtype.__name__)
                self.stdout.write(f"{app_label}.{_recordtype_name}")
