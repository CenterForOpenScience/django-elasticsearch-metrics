from django.core.management.base import BaseCommand, CommandError

from elasticsearch_metrics.registry import registry


class Command(BaseCommand):
    help = "Ensures index templates exist for all Metric classes."

    def add_arguments(self, parser):
        parser.add_argument(
            "app_label",
            nargs="?",
            help="App label of an application to synchronize the state.",
        )
        # TODO: "using"

    def handle(self, *args, **options):
        if options["app_label"]:
            if options["app_label"] not in registry.all_metrics:
                raise CommandError(
                    "No metrics found for app '{}'".format(options["app_label"])
                )
            app_labels = [options["app_label"]]
        else:
            app_labels = registry.all_metrics.keys()
        for app_label in app_labels:
            self.stdout.write("Syncing metrics for app '{}'".format(app_label))
            metrics = registry.get_metrics(app_label=app_label)
            for metric in metrics:
                template_name = metric._template_name
                template = metric._template
                self.stdout.write(
                    "  Syncing template {template_name} ({template})".format(**locals())
                )
                metric.create_index_template()

        self.stdout.write("Synchronized metrics.", self.style.SUCCESS)
