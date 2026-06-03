import logging

from django.core.management.base import BaseCommand

from elasticsearch_metrics.registry import djelme_registry
from elasticsearch_metrics.protocols import ProtoDjelmeRecord


class Command(BaseCommand):
    help = "Inspect and manage existing indexes"

    def add_arguments(self, parser):
        parser.add_argument(
            "app_label", nargs="?", help="App label of a django application."
        )
        parser.add_argument(
            "--delete-expired",
            action="store_true",
            help="Delete indexes past their expiration date",
        )
        parser.add_argument(
            "--really-really",
            action="store_true",
            help="Skip confirmation for --delete-expired",
        )

    def handle(self, *args, **options):
        # Avoid elasticsearch requests from getting logged
        logging.getLogger("elastic_transport").setLevel(logging.ERROR)
        _app_labels = (
            [options["app_label"]]
            if options["app_label"]
            else list(djelme_registry.each_app_label())
        )
        if options["delete_expired"]:
            self._delete_expired_indexes(_app_labels, options["really_really"])
        else:
            self._list_existing_indexes(_app_labels)

    def _list_existing_indexes(self, app_labels: list[str]) -> None:
        self.stdout.write("Existing indexes:")
        for _app_label in app_labels:
            for _recordtype in djelme_registry.each_recordtype(app_label=_app_label):
                for _index_status in _recordtype.each_existing_index():
                    _suffix = " (expired)" if _index_status.is_expired else ""
                    self.stdout.write(f"{_index_status.index_name}{_suffix}")

    def _delete_expired_indexes(
        self, app_labels: list[str], skip_confirmation: bool
    ) -> None:
        self.stdout.write("Expired indexes:")
        _to_delete: list[tuple[type[ProtoDjelmeRecord], str]] = []
        for _app_label in app_labels:
            for _recordtype in djelme_registry.each_recordtype(app_label=_app_label):
                for _index_status in _recordtype.each_existing_index():
                    if _index_status.is_expired:
                        _to_delete.append((_recordtype, _index_status.index_name))
                        if not skip_confirmation:
                            self.stdout.write(_index_status.index_name)
        if not _to_delete:
            self.stdout.write("No expired indexes.")
            return
        if not skip_confirmation:
            _confirm_response = input("Really delete all these indexes? (y/N)")
            if _confirm_response.lower() != "y":
                return
        for _recordtype, _index_name in _to_delete:
            self.stdout.write(f"deleting {_index_name}")
            _recordtype.delete_index(_index_name)
