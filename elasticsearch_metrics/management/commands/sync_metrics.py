from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Ensures index templates exist for all Metric classes."

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        # TODO
        self.stdout.write("Synchronized metrics.", self.style.SUCCESS)
