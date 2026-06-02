from unittest import mock

from django.core.management.base import CommandError

from elasticsearch_metrics import exceptions
from elasticsearch_metrics.management.commands import djelme_backend_check
from elasticsearch_metrics.registry import registry
from elasticsearch_metrics.tests.util import SimpleDjelmeTestCase


class TestCheckRecordtypes(SimpleDjelmeTestCase):
    def setUp(self):
        self.mock8_timeseries_check_djelme_setup = self.enterContext(
            mock.patch(
                "elasticsearch_metrics.imps.elastic8.TimeseriesRecord.check_djelme_setup"
            ),
        )
        self.mock8_simple_check_djelme_setup = self.enterContext(
            mock.patch(
                "elasticsearch_metrics.imps.elastic8.SimpleRecord.check_djelme_setup"
            ),
        )

    def test_exits_with_error_if_out_of_sync_8(self):
        self.mock8_timeseries_check_djelme_setup.side_effect = (
            exceptions.IndexTemplateNotFoundError(
                "Index template does not exist", client_error=None
            )
        )
        with self.assertRaises(CommandError):
            self.run_mgmt_command(djelme_backend_check)

    def test_exits_with_error_if_out_of_sync_8_simplerec(self):
        self.mock8_simple_check_djelme_setup.side_effect = (
            exceptions.IndexNotFoundError("Index does not exist", client_error=None)
        )
        with self.assertRaises(CommandError):
            self.run_mgmt_command(djelme_backend_check)

    def test_exits_with_success(self):
        self.run_mgmt_command(djelme_backend_check)
        _call_count = (
            self.mock8_timeseries_check_djelme_setup.call_count
            + self.mock8_simple_check_djelme_setup.call_count
        )
        assert _call_count == len(list(registry.each_recordtype()))

    def test_with_invalid_app(self):
        with self.assertRaises(LookupError):
            self.run_mgmt_command(djelme_backend_check, "notanapp")
