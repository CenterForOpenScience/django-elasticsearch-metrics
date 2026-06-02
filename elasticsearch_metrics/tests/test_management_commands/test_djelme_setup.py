import unittest

from elasticsearch_metrics.imps import elastic8
from elasticsearch_metrics.management.commands import djelme_backend_setup
from elasticsearch_metrics.registry import djelme_registry
from elasticsearch_metrics.tests.util import SimpleDjelmeTestCase


class TestDjelmeSetup(SimpleDjelmeTestCase):
    mock_inits: list[unittest.mock.Mock]

    def setUp(self):
        self.mock_inits = [
            self.enterContext(
                unittest.mock.patch(
                    "elasticsearch_metrics.imps.elastic8.TimeseriesRecord.init"
                ),
            ),
            self.enterContext(
                unittest.mock.patch(
                    "elasticsearch_metrics.imps.elastic8.SimpleRecord.init"
                ),
            ),
        ]

    def test_without_args(self):
        out, err = self.run_mgmt_command(djelme_backend_setup)
        _call_count = sum(_mock.call_count for _mock in self.mock_inits)
        assert _call_count == len(list(djelme_registry.each_recordtype()))
        assert "Synchronized recordtypes." in out

    def test_with_invalid_app(self):
        with self.assertRaises(LookupError):
            self.run_mgmt_command(djelme_backend_setup, "notanapp")

    def test_with_app_label(self):
        class DummyMetric2(elastic8.SimpleRecord):
            class Meta:
                app_label = "dummyapp2"

        out, err = self.run_mgmt_command(djelme_backend_setup, "dummyapp2")
        _call_count = sum(_mock.call_count for _mock in self.mock_inits)
        assert _call_count == 1
