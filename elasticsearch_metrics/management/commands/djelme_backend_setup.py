from django.core.management.base import BaseCommand, CommandError

from elasticsearch_metrics.registry import djelme_registry
from elasticsearch_metrics.management.color import color_style


class Command(BaseCommand):
    help = "Ensures index templates exist for all Metric classes."

    def add_arguments(self, parser):
        parser.add_argument(
            "app_label",
            nargs="?",
            help="App label of an application to synchronize the state.",
        )

    def handle(self, *args, **options):
        style = color_style()
        _given_app_label: str | None = options["app_label"]
        _app_labels: list[str]
        _app_labels = (
            [_given_app_label]
            if _given_app_label
            else list(djelme_registry.each_app_label())
        )
        for _app_label in _app_labels:
            self.stdout.write(
                f"Syncing recordtypes for app: '{_app_label}'",
                style.MIGRATE_HEADING,
            )
            try:
                _types_by_backend = djelme_registry.recordtypes_by_backend(
                    app_label=_app_label
                )
            except LookupError as _err:
                raise CommandError(
                    f"No recordtypes found for app {_app_label!r}"
                ) from _err
            for _backend_name, _each_recordtype in _types_by_backend.items():
                _backend = djelme_registry.get_backend(_backend_name)
                self.stdout.write(f"  Using backend {_backend_name!r}...")
                _backend.djelme_setup(_each_recordtype)

        self.stdout.write("Synchronized recordtypes.", style.SUCCESS)
