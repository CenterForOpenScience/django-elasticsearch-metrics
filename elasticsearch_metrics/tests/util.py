import contextlib
from io import StringIO
import types
from unittest import mock
import uuid

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.test import SimpleTestCase

from elasticsearch_metrics.registry import djelme_registry


@contextlib.contextmanager
def djelme_test_backends():
    """context manager to wrap tests that use djelme with actual elasticsearch

    gives index names a unique prefix

    sets up and tears down all backends configured in django.conf.settings.DJELME_BACKENDS
    """
    clear_setup_check_caches()
    with prefixed_index_names():
        setup_backends()
        try:
            yield
        finally:
            teardown_backends()


class SimpleDjelmeTestCase(SimpleTestCase):
    """SimpleDjelmeTestCase: base test case with djelme-specific conveniences"""

    def setUp(self):
        super().setUp()
        clear_setup_check_caches()

    def enterContext(self, context_manager):
        # unittest.TestCase.enterContext added in python3.11 -- implementing here until 3.10 eol
        self.addCleanup(lambda: context_manager.__exit__(None, None, None))
        return context_manager.__enter__()

    def run_mgmt_command(
        self, cmd: str | BaseCommand | types.ModuleType, *args: str, **options: str
    ) -> tuple[str, str]:
        """run a django management command, return (stdout, stderr) tuple

        wraps django.core.management.call_command to handle string-io and
        also accept a management command module
        """
        _cmd = cmd.Command() if isinstance(cmd, types.ModuleType) else cmd
        _out, _err = StringIO(), StringIO()
        call_command(_cmd, *args, **options, stdout=_out, stderr=_err)
        return _out.getvalue(), _err.getvalue()


class RealElasticTestCase(SimpleDjelmeTestCase):
    """RealElasticTestCase: base test case with actual elasticsearch running"""

    def setUp(self):
        self.enterContext(djelme_test_backends())


class NoSetupRealElasticTestCase(SimpleDjelmeTestCase):
    """NoSetupRealElasticTestCase: base test case with actual elasticsearch running

    same as RealElasticTestCase but skip djelme backend setup
    """

    def setUp(self):
        clear_setup_check_caches()
        self.enterContext(prefixed_index_names())
        super().setUp()

    def tearDown(self):
        teardown_backends()
        super().tearDown()


class MockConnectionTestCase(SimpleDjelmeTestCase):
    def setUp(self):
        super().setUp()
        clear_setup_check_caches()
        self.mock_es6_connection = mock.Mock()
        self.mock_es8_connection = mock.Mock()
        self.mock_es6_connection.index.return_value = {"result": "created"}
        self.mock_es8_connection.index.return_value = {"result": "created"}
        self.enterContext(
            mock.patch(
                "elasticsearch_metrics.imps.elastic6.Document._get_connection",
                return_value=self.mock_es6_connection,
            ),
        )
        self.enterContext(
            mock.patch(
                "elasticsearch_metrics.imps.elastic8.esdsl.Document._get_connection",
                return_value=self.mock_es8_connection,
            ),
        )
        self.mock_es6_require_been_setup = self.enterContext(
            mock.patch("elasticsearch_metrics.imps.elastic6.Metric.require_been_setup"),
        )
        self.mock_es8_require_been_setup = self.enterContext(
            mock.patch(
                "elasticsearch_metrics.imps.elastic8.BaseDjelmeRecord.require_been_setup"
            ),
        )


@contextlib.contextmanager
def prefixed_index_names(prefix: str = ""):
    _name_prefix = prefix or f"testrun{uuid.uuid4().hex}_"
    with (
        mock.patch(
            "elasticsearch_metrics.imps.elastic8.BaseDjelmeRecord.get_index_name_prefix",
            return_value=_name_prefix,
        ),
        mock.patch(
            "elasticsearch_metrics.imps.elastic6.BaseMetric.get_index_name_prefix",
            return_value=_name_prefix,
        ),
    ):
        yield


def clear_setup_check_caches():
    from elasticsearch_metrics.imps import elastic6, elastic8

    elastic6.Metric.require_been_setup.cache_clear()
    elastic8.BaseDjelmeRecord.require_been_setup.cache_clear()


def setup_backends():
    # backends based on settings in django.conf.settings.DJELME_BACKENDS
    _types_by_backend = djelme_registry.recordtypes_by_backend()
    for _backend_name, _recordtypes in _types_by_backend.items():
        djelme_registry.get_backend(_backend_name).djelme_setup(_recordtypes)


def teardown_backends():
    # backends based on settings in django.conf.settings.DJELME_BACKENDS
    _types_by_backend = djelme_registry.recordtypes_by_backend()
    for _backend_name, _recordtypes in _types_by_backend.items():
        djelme_registry.get_backend(_backend_name).djelme_teardown(_recordtypes)
