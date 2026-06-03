from django.core.management.base import BaseCommand

from elasticsearch_metrics.registry import djelme_registry
from elasticsearch_metrics.management.color import color_style


class Command(BaseCommand):
    help = "Pretty-print a listing of all registered djelme recordtypes."

    def add_arguments(self, parser):
        parser.add_argument(
            "app_label", nargs="?", help="App label of a django application."
        )

    def handle(self, *args, **options):
        style = color_style()
        _app_labels = (
            [options["app_label"]]
            if options["app_label"]
            else list(djelme_registry.each_app_label())
        )
        for app_label in _app_labels:
            self.stdout.write(f"Recordtypes for {app_label!r}", style.MIGRATE_HEADING)
            for _recordtype in djelme_registry.each_recordtype(app_label=app_label):
                _recordtype_name = style.TYPENAME(_recordtype.__name__)
                self.stdout.write(f"{app_label}.{_recordtype_name}")
