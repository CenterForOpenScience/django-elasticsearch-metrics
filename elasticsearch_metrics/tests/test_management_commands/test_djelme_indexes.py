import datetime
from unittest import mock

from elasticsearch_metrics.management.commands import djelme_indexes
from elasticsearch_metrics.tests.util import MockConnectionTestCase


class TestDjelmeIndexes(MockConnectionTestCase):
    def setUp(self):
        super().setUp()
        self._fake_now = datetime.datetime(2016, 8, 21, tzinfo=datetime.timezone.utc)
        self.enterContext(
            mock.patch(
                "elasticsearch_metrics.imps.elastic8.utcnow",
                return_value=self._fake_now,
            )
        )
        self.mock_es8_connection.indices.get.side_effect = self._fake_get_indexes
        self.mock_es6_connection.indices.get.side_effect = self._fake_get_indexes

    def _fake_get_indexes(self, *, index, **kwargs):
        if index == "dummy8app_happen_*":
            return {
                "dummy8app_happen_1999.1.": {},
                "dummy8app_happen_2015.1.": {},
                "dummy8app_happen_2015.12.": {},
                "dummy8app_happen_2016.1.": {},
                "dummy8app_happen_2016.2.": {},
                "dummy8app_happen_2016.3.": {},
                "dummy8app_happen_2016.4.": {},
                "dummy8app_happen_2016.5.": {},
                "dummy8app_happen_2016.6.": {},
                "dummy8app_happen_2016.7.": {},
                "dummy8app_happen_2016.8.": {},
            }
        if index == "dummy8app_dummy8event_*":
            return {
                "dummy8app_dummy8event_1999.1.": {},
                "dummy8app_dummy8event_2015.12.": {},
                "dummy8app_dummy8event_2016.1.": {},
                "dummy8app_dummy8event_2016.2.": {},
                "dummy8app_dummy8event_2016.3.": {},
                "dummy8app_dummy8event_2016.4.": {},
                "dummy8app_dummy8event_2016.5.": {},
                "dummy8app_dummy8event_2016.6.": {},
                "dummy8app_dummy8event_2016.7.": {},
                "dummy8app_dummy8event_2016.8.": {},
            }
        if index == "blarg_dummy8app_thinghappeningsreport_*":
            return {
                "dummy8app_thinghappeningsreport_1999.": {},
                "dummy8app_thinghappeningsreport_2015.": {},
                "dummy8app_thinghappeningsreport_2016.": {},
            }
        return {}

    def test_without_args(self):
        _out, _err = self.run_mgmt_command(djelme_indexes)
        self.assertFalse(self.mock_es8_connection.indices.delete.called)
        _outlines = _out.split("\n")
        self.assertIn("dummy8app_happen_1999.1. (expired)", _outlines)
        self.assertIn("dummy8app_happen_2015.1. (expired)", _outlines)
        self.assertIn("dummy8app_happen_2015.12. (expired)", _outlines)
        self.assertIn("dummy8app_happen_2016.1. (expired)", _outlines)
        self.assertIn("dummy8app_happen_2016.2. (expired)", _outlines)
        self.assertIn("dummy8app_happen_2016.3. (expired)", _outlines)
        self.assertIn("dummy8app_happen_2016.4. (expired)", _outlines)
        self.assertIn("dummy8app_happen_2016.5.", _outlines)
        self.assertIn("dummy8app_happen_2016.6.", _outlines)
        self.assertIn("dummy8app_happen_2016.7.", _outlines)
        self.assertIn("dummy8app_happen_2016.8.", _outlines)
        self.assertIn("dummy8app_dummy8event_1999.1.", _outlines)
        self.assertIn("dummy8app_dummy8event_2015.12.", _outlines)
        self.assertIn("dummy8app_dummy8event_2016.1.", _outlines)
        self.assertIn("dummy8app_dummy8event_2016.2.", _outlines)
        self.assertIn("dummy8app_dummy8event_2016.3.", _outlines)
        self.assertIn("dummy8app_dummy8event_2016.4.", _outlines)
        self.assertIn("dummy8app_dummy8event_2016.5.", _outlines)
        self.assertIn("dummy8app_dummy8event_2016.6.", _outlines)
        self.assertIn("dummy8app_dummy8event_2016.7.", _outlines)
        self.assertIn("dummy8app_dummy8event_2016.8.", _outlines)
        self.assertIn("dummy8app_thinghappeningsreport_1999.", _outlines)
        self.assertIn("dummy8app_thinghappeningsreport_2015.", _outlines)
        self.assertIn("dummy8app_thinghappeningsreport_2016.", _outlines)

    def test_delete_expired_really(self):
        out, err = self.run_mgmt_command(
            djelme_indexes, "--delete-expired", "--really-really"
        )
        self.assertEqual(
            self.mock_es8_connection.indices.delete.call_args_list,
            [
                mock.call(index="dummy8app_happen_1999.1."),
                mock.call(index="dummy8app_happen_2015.1."),
                mock.call(index="dummy8app_happen_2015.12."),
                mock.call(index="dummy8app_happen_2016.1."),
                mock.call(index="dummy8app_happen_2016.2."),
                mock.call(index="dummy8app_happen_2016.3."),
                mock.call(index="dummy8app_happen_2016.4."),
            ],
        )

    def test_with_invalid_app(self):
        with self.assertRaises(LookupError):
            self.run_mgmt_command(djelme_indexes, "notanapp")
