from elasticsearch_metrics.management.commands import djelme_backend_types
from elasticsearch_metrics.tests.util import SimpleDjelmeTestCase


class TestDjelmeTypesCommand(SimpleDjelmeTestCase):
    def test_without_args(self):
        out, err = self.run_mgmt_command(djelme_backend_types)
        assert "Dummy8Event" in out
        assert "Monthly8Event" in out
        assert "ThingHappened" in out
        assert "ThingHappeningsReport" in out
        assert "SimpleKV" in out

    def test_with_invalid_app(self):
        with self.assertRaises(LookupError):
            self.run_mgmt_command(djelme_backend_types, "notanapp")
