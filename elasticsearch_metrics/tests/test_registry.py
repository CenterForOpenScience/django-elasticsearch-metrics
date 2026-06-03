from django.test import SimpleTestCase

from elasticsearch_metrics.imps import elastic8
from elasticsearch_metrics.registry import djelme_registry
from elasticsearch_metrics.tests.dummy8app.metrics import Dummy8Event


class RecordWithAppLabel(elastic8.TimeseriesRecord):
    class Meta:
        app_label = "dummy8app"


class TestTimeseriesTypeRegistry(SimpleTestCase):
    def test_conflicting_recordtype(self):
        with self.assertRaises(RuntimeError):

            class RecordWithAppLabel(elastic8.TimeseriesRecord):
                class Meta:
                    app_label = "dummy8app"

    def test_get_recordtype(self):
        assert djelme_registry.get_recordtype("dummy8app", "Dummy8Event") is Dummy8Event
        assert djelme_registry.get_recordtype("dummy8app.Dummy8Event") is Dummy8Event

        with self.assertRaises(LookupError) as excinfo:
            djelme_registry.get_recordtype("dummy8app", "DoesNotExist")
        assert (
            "App 'dummy8app' doesn't have a 'DoesNotExist' metric."
            in excinfo.exception.args[0]
        )

        with self.assertRaises(LookupError) as excinfo:
            djelme_registry.get_recordtype("notanapp", "Dummy8Event")
        assert "'notanapp'" in excinfo.exception.args[0]

    def test_get_recordtypes(self):
        class AnotherRecord(elastic8.TimeseriesRecord):
            class Meta:
                app_label = "anotherapp"

        assert Dummy8Event in djelme_registry.each_recordtype()
        assert AnotherRecord in djelme_registry.each_recordtype()
        assert Dummy8Event in djelme_registry.each_recordtype(app_label="dummy8app")
        assert AnotherRecord not in djelme_registry.each_recordtype(
            app_label="dummy8app"
        )

        with self.assertRaises(LookupError) as excinfo:
            list(djelme_registry.each_recordtype(app_label="notanapp"))
        assert "'notanapp'" in excinfo.exception.args[0]

    def test_get_recordtypes_excludes_abstract_recordtypes(self):
        class AbstractRecord(elastic8.TimeseriesRecord):
            class Meta:
                abstract = True

        class ConcreteRecord(AbstractRecord):
            class Meta:
                app_label = "anotherapp"

        assert elastic8.BaseDjelmeRecord not in djelme_registry.each_recordtype()
        assert elastic8.TimeseriesRecord not in djelme_registry.each_recordtype()
        assert elastic8.EventRecord not in djelme_registry.each_recordtype()
        assert elastic8.CyclicReport not in djelme_registry.each_recordtype()
        assert AbstractRecord not in djelme_registry.each_recordtype()
        assert ConcreteRecord in djelme_registry.each_recordtype()
