from unittest import mock
import datetime as dt

import elasticsearch8
from elasticsearch8.dsl import (
    ComposableIndexTemplate,
    MetaField,
)

from elasticsearch_metrics import signals
from elasticsearch_metrics.imps import elastic8 as djelme
from elasticsearch_metrics.exceptions import (
    IndexTemplateNotFoundError,
    IndexTemplateOutOfSyncError,
)
from elasticsearch_metrics.registry import djelme_registry
from elasticsearch_metrics.tests.util import (
    SimpleDjelmeTestCase,
    MockConnectionTestCase,
    RealElasticTestCase,
    NoSetupRealElasticTestCase,
)
from elasticsearch_metrics.tests.dummy8app.metrics import (
    Dummy8Event,
    Monthly8Event,
    ThingHappened,
    ThingHappeningsReport,
    SimpleKV,
)


def _es8_client(
    backend_name: str = "my_elastic8",
) -> elasticsearch8.Elasticsearch:
    _backend = djelme_registry.get_backend(backend_name)
    assert isinstance(_backend, djelme.DjelmeElastic8Backend)
    return _backend.elastic_client


class TestNamesAndPatterns(SimpleDjelmeTestCase):
    def test_index_name(self):
        _stamp = dt.datetime(2020, 2, 14)
        _dum8event = Dummy8Event(timestamp=_stamp, intensity=7)
        self.assertEqual(
            _dum8event.djelme_index_name(),
            "dummy8app_dummy8event_2020.2.14.",
        )
        _month8event = Monthly8Event(timestamp=_stamp, intenzity=8)
        self.assertEqual(
            _month8event.djelme_index_name(),
            "dummy8evenzdummy8app_eventlog_2020.2.",
        )
        _thingevent = ThingHappened(timestamp=_stamp, thing_id="hi")
        self.assertEqual(
            _thingevent.djelme_index_name(),
            "dummy8app_happen_2020.2.",
        )
        _thingreport = ThingHappeningsReport(
            timestamp=_stamp,
            cycle_coverage="1999.3.15",
            thing_id="wo",
            happen_count=2,
        )
        self.assertEqual(
            _thingreport.djelme_index_name(),
            "blarg_dummy8app_thinghappeningsreport_1999.",
        )
        _kv = SimpleKV(key="wha", val=0)
        self.assertEqual(
            _kv.djelme_index_name(),
            "dummy8app_simplekv",
        )

    def test_format_index_name_respects_date_format_setting(self):
        _stamp = dt.datetime(2020, 2, 14)
        with self.settings(DJELME_DEFAULT_TIMEDEPTH=4):
            # no timedepth set; use default setting
            _dum8event = Dummy8Event(timestamp=_stamp, intensity=2)
            self.assertEqual(
                _dum8event.djelme_index_name(),
                "dummy8app_dummy8event_2020.2.14.0.",
            )
            # timedepth set; ignore default setting
            _month8event = Monthly8Event(timestamp=_stamp, intenzity=2)
            self.assertEqual(
                _month8event.djelme_index_name(),
                "dummy8evenzdummy8app_eventlog_2020.2.",
            )
            _thingevent = ThingHappened(timestamp=_stamp, thing_id="ha")
            self.assertEqual(
                _thingevent.djelme_index_name(),
                "dummy8app_happen_2020.2.",
            )
            _thingreport = ThingHappeningsReport(
                timestamp=_stamp,
                cycle_coverage="1999.3.16",
                thing_id="wha",
                happen_count=0,
            )
            self.assertEqual(
                _thingreport.djelme_index_name(),
                "blarg_dummy8app_thinghappeningsreport_1999.",
            )

    def test_format_timeseries_index_pattern__lotsa_parts(self):
        _timeparts = (2020, 2, 14, 0, 1, 2)
        self.assertEqual(
            Dummy8Event.timeseries_index_wildcard(_timeparts),
            "dummy8app_dummy8event_2020.2.14.*",
        )
        self.assertEqual(
            Monthly8Event.timeseries_index_wildcard(_timeparts),
            "dummy8evenzdummy8app_eventlog_2020.2.*",
        )
        self.assertEqual(
            ThingHappened.timeseries_index_wildcard(_timeparts),
            "dummy8app_happen_2020.2.*",
        )
        self.assertEqual(
            ThingHappeningsReport.timeseries_index_wildcard(_timeparts),
            "blarg_dummy8app_thinghappeningsreport_2020.*",
        )

    def test_format_timeseries_index_pattern__some_parts(self):
        _timeparts = (2020, 2, 14)
        self.assertEqual(
            Dummy8Event.timeseries_index_wildcard(_timeparts),
            "dummy8app_dummy8event_2020.2.14.*",
        )
        self.assertEqual(
            Monthly8Event.timeseries_index_wildcard(_timeparts),
            "dummy8evenzdummy8app_eventlog_2020.2.*",
        )
        self.assertEqual(
            ThingHappened.timeseries_index_wildcard(_timeparts),
            "dummy8app_happen_2020.2.*",
        )
        self.assertEqual(
            ThingHappeningsReport.timeseries_index_wildcard(_timeparts),
            "blarg_dummy8app_thinghappeningsreport_2020.*",
        )

    def test_format_timeseries_index_pattern__one_part(self):
        _timeparts = (2020,)
        self.assertEqual(
            Dummy8Event.timeseries_index_wildcard(_timeparts),
            "dummy8app_dummy8event_2020.*",
        )
        self.assertEqual(
            Monthly8Event.timeseries_index_wildcard(_timeparts),
            "dummy8evenzdummy8app_eventlog_2020.*",
        )
        self.assertEqual(
            ThingHappened.timeseries_index_wildcard(_timeparts),
            "dummy8app_happen_2020.*",
        )
        self.assertEqual(
            ThingHappeningsReport.timeseries_index_wildcard(_timeparts),
            "blarg_dummy8app_thinghappeningsreport_2020.*",
        )

    def test_format_timeseries_index_pattern__no_parts(self):
        _timeparts = ()
        self.assertEqual(
            Dummy8Event.timeseries_index_wildcard(_timeparts),
            "dummy8app_dummy8event_*",
        )
        self.assertEqual(
            Monthly8Event.timeseries_index_wildcard(_timeparts),
            "dummy8evenzdummy8app_eventlog_*",
        )
        self.assertEqual(
            ThingHappened.timeseries_index_wildcard(_timeparts),
            "dummy8app_happen_*",
        )
        self.assertEqual(
            ThingHappeningsReport.timeseries_index_wildcard(_timeparts),
            "blarg_dummy8app_thinghappeningsreport_*",
        )

    def test_format_index_pattern_respects_date_format_setting(self):
        with self.settings(DJELME_DEFAULT_TIMEDEPTH=4):
            _timeparts = (2020, 2, 14, 0, 1, 2)
            self.assertEqual(
                Dummy8Event.timeseries_index_wildcard(_timeparts),
                "dummy8app_dummy8event_2020.2.14.0.*",
            )
            self.assertEqual(
                Monthly8Event.timeseries_index_wildcard(_timeparts),
                "dummy8evenzdummy8app_eventlog_2020.2.*",
            )
            self.assertEqual(
                ThingHappened.timeseries_index_wildcard(_timeparts),
                "dummy8app_happen_2020.2.*",
            )


class TestGetIndexTemplate(SimpleDjelmeTestCase):
    def test_get_index_template_returns_template_with_correct_name_and_pattern(self):
        template = ThingHappened.get_timeseries_template()
        self.assertIsInstance(template, ComposableIndexTemplate)
        self.assertEqual(template._template_name, "dummy8app_happen__template")
        _template_dict = template.to_dict()
        self.assertEqual(_template_dict["index_patterns"], ["dummy8app_happen_*"])

    def test_get_index_template_respects_index_settings(self):
        template = ThingHappened.get_timeseries_template()
        assert template._index.to_dict()["settings"] == {
            "refresh_interval": "-1",
            "analysis": {
                "analyzer": {
                    "dot_path_analyzer": {
                        "tokenizer": "dot_path_tokenizer",
                        "type": "custom",
                    }
                },
                "tokenizer": {
                    "dot_path_tokenizer": {
                        "delimiter": ".",
                        "type": "path_hierarchy",
                    }
                },
            },
        }

    def test_get_index_template_creates_template_with_mapping(self):
        template = ThingHappened.get_timeseries_template()
        mappings = template.to_dict()["template"]["mappings"]
        properties = mappings["properties"]
        assert "timestamp" in properties
        assert properties["timestamp"] == {"type": "date"}
        assert properties["thing_id"] == {"type": "keyword"}
        assert properties["happen_code"] == {"type": "keyword"}

    def test_mappings_are_not_shared(self):
        template1 = Dummy8Event.get_timeseries_template().to_dict()
        template2 = Monthly8Event.get_timeseries_template().to_dict()
        assert "intensity" in template1["template"]["mappings"]["properties"]
        assert "intenzity" not in template1["template"]["mappings"]["properties"]
        assert "intensity" not in template2["template"]["mappings"]["properties"]
        assert "intenzity" in template2["template"]["mappings"]["properties"]

    def test_get_index_template_default_template_name(self):
        template = Dummy8Event.get_timeseries_template()
        assert isinstance(template, ComposableIndexTemplate)
        assert template._template_name == "dummy8app_dummy8event__template"
        assert "dummy8app_dummy8event_*" in template.to_dict()["index_patterns"]

    def test_get_index_template_uses_app_label_in_class_meta(self):
        class MyRecord(djelme.TimeseriesRecord):
            class Meta:
                app_label = "myapp"

        template = MyRecord.get_timeseries_template()
        assert template._template_name == "myapp_myrecord__template"

    def test_template_name_defined_with_no_template_falls_back_to_default_template(
        self,
    ):
        template = Monthly8Event.get_timeseries_template()
        # prefix and recordtype specified in class Meta
        assert template._template_name == "dummy8evenzdummy8app_eventlog__template"
        # template pattern generated using same options
        assert "dummy8evenzdummy8app_eventlog_*" in template.to_dict()["index_patterns"]

    def test_inheritance(self):
        class MyBaseRecord(djelme.TimeseriesRecord):
            label: str

            class Index:
                settings = {"number_of_shards": 2}

            class Meta:
                abstract = True

        class ConcreteRecord(MyBaseRecord):
            class Meta:
                app_label = "dummy8app"

        template = ConcreteRecord.get_timeseries_template()
        assert template._template_name == "dummy8app_concreterecord__template"
        assert template._index.to_dict()["settings"] == {"number_of_shards": 2}

    def test_source_may_be_enabled(self):
        class MyRecord(djelme.TimeseriesRecord):
            class Meta:
                app_label = "dummy8app"
                timeseries_recordtype_name = "myrecord"
                source = MetaField(enabled=True)

        template = MyRecord.get_timeseries_template()
        template_dict = template.to_dict()
        doc = template_dict["template"]["mappings"]
        assert doc["_source"]["enabled"] is True


class TestRecord(MockConnectionTestCase):
    def test_calls_save(self):
        timestamp = dt.datetime(2017, 8, 21, tzinfo=dt.timezone.utc)
        p = ThingHappened.record(timestamp=timestamp, thing_id="abc12")
        assert self.mock_es8_connection.index.call_count == 1
        assert p.timestamp == timestamp
        assert p.timeseries_timeparts == "2017.8.21.0.0.0"
        assert p.thing_id == "abc12"

    def test_defaults_timestamp_to_now(self):
        _fake_now = dt.datetime(2016, 8, 21, tzinfo=dt.timezone.utc)
        with mock.patch(
            "elasticsearch_metrics.imps.elastic8.utcnow", return_value=_fake_now
        ):
            p = ThingHappened.record(thing_id="abc12")
        assert self.mock_es8_connection.index.call_count == 1
        assert p.timestamp == _fake_now


class TestSignals(MockConnectionTestCase):
    def test_create_record_sends_signals(self):
        mock_pre_index_template_listener = mock.Mock()
        mock_post_index_template_listener = mock.Mock()
        signals.pre_index_template_create.connect(mock_pre_index_template_listener)
        signals.post_index_template_create.connect(mock_post_index_template_listener)
        ThingHappened.sync_index_template()
        assert mock_pre_index_template_listener.call_count == 1
        assert mock_post_index_template_listener.call_count == 1
        pre_call_kwargs = mock_pre_index_template_listener.call_args[1]
        assert "index_template" in pre_call_kwargs
        assert "using" in pre_call_kwargs

        post_call_kwargs = mock_pre_index_template_listener.call_args[1]
        assert "index_template" in post_call_kwargs
        assert "using" in post_call_kwargs

    def test_save_sends_signals(self):
        mock_pre_save_listener = mock.Mock()
        mock_post_save_listener = mock.Mock()
        signals.pre_save.connect(mock_pre_save_listener, sender=ThingHappened)
        signals.post_save.connect(mock_post_save_listener, sender=ThingHappened)

        thing_id = "12345"
        happen_code = "zyxwv"
        doc = ThingHappened(thing_id=thing_id, happen_code=happen_code)
        doc.save()

        assert mock_pre_save_listener.call_count == 1
        pre_save_kwargs = mock_pre_save_listener.call_args[1]
        assert isinstance(pre_save_kwargs["instance"], ThingHappened)
        assert "index" in pre_save_kwargs
        assert "using" in pre_save_kwargs
        assert pre_save_kwargs["sender"] is ThingHappened

        assert mock_post_save_listener.call_count == 1
        post_save_kwargs = mock_pre_save_listener.call_args[1]
        assert isinstance(post_save_kwargs["instance"], ThingHappened)
        assert "index" in post_save_kwargs
        assert "using" in post_save_kwargs
        assert post_save_kwargs["sender"] is ThingHappened


class TestRealCreate(RealElasticTestCase):
    def test_save(self):
        _thing_id = "12345"
        _happen_code = "zyxwv"
        _doc = ThingHappened(thing_id=_thing_id, happen_code=_happen_code)
        _doc.save()
        assert _doc.timestamp is not None
        _fetched_doc = ThingHappened.get(
            id=_doc.meta.id, index=_doc.djelme_index_name()
        )
        assert _fetched_doc
        assert _fetched_doc.timestamp == _doc.timestamp
        assert _fetched_doc.timeseries_timeparts == _doc.timeseries_timeparts
        assert _fetched_doc.thing_id == _doc.thing_id == _thing_id
        assert _fetched_doc.happen_code == _doc.happen_code == _happen_code

        # index mappings should match the index template
        name = _doc.djelme_index_name()
        mapping = _es8_client().indices.get_mapping(index=name)
        properties = mapping[name]["mappings"]["properties"]
        assert properties["timestamp"] == {"type": "date"}
        assert properties["thing_id"] == {"type": "keyword"}
        assert properties["happen_code"] == {"type": "keyword"}

    def test_record(self):
        _thing_id = "54321"
        _happen_code = "abcde"
        _doc = ThingHappened.record(thing_id=_thing_id, happen_code=_happen_code)
        assert _doc.timestamp is not None
        _fetched_doc = ThingHappened.get(
            id=_doc.meta.id, index=_doc.djelme_index_name()
        )
        assert _fetched_doc
        assert _fetched_doc.timestamp == _doc.timestamp
        assert _fetched_doc.timeseries_timeparts == _doc.timeseries_timeparts
        assert _fetched_doc.thing_id == _doc.thing_id == _thing_id
        assert _fetched_doc.happen_code == _doc.happen_code == _happen_code

        # index mappings should match the index template
        name = _doc.djelme_index_name()
        mapping = _es8_client().indices.get_mapping(index=name)
        properties = mapping[name]["mappings"]["properties"]
        assert properties["timestamp"] == {"type": "date"}
        assert properties["thing_id"] == {"type": "keyword"}
        assert properties["happen_code"] == {"type": "keyword"}


class TestWithoutAutosetup(NoSetupRealElasticTestCase):
    def test_cannot_save_without_template(self):
        _event = Dummy8Event(intensity=2)
        with self.assertRaises(IndexTemplateNotFoundError):
            _event.save()

    def test_cannot_save_with_wrong_template_pattern(self):
        with mock.patch.object(
            Dummy8Event,
            "timeseries_index_wildcard",
            return_value="wrong_pattern_haha_*",
        ):
            Dummy8Event.init()
        with self.assertRaises(IndexTemplateOutOfSyncError):
            Dummy8Event.record(intensity=2)

    def test_cannot_save_with_extra_property_mapping(self):
        # create template with extra property mapping
        _template = Dummy8Event.get_timeseries_template().to_dict()
        _template["template"]["mappings"]["properties"]["foo"] = {"type": "keyword"}
        _es8_client().indices.put_index_template(
            name=Dummy8Event.get_timeseries_template_name(),
            **_template,
        )
        with self.assertRaises(IndexTemplateOutOfSyncError):
            Dummy8Event.record(intensity=2)

    def test_cannot_save_with_missing_property_mapping(self):
        # create template with missing property mapping
        _template = Dummy8Event.get_timeseries_template().to_dict()
        del _template["template"]["mappings"]["properties"]["intensity"]
        _es8_client().indices.put_index_template(
            name=Dummy8Event.get_timeseries_template_name(),
            **_template,
        )
        with self.assertRaises(IndexTemplateOutOfSyncError):
            Dummy8Event.record(intensity=2)

    def test_init(self):
        ThingHappened.init()
        _client = _es8_client()
        _template_name = ThingHappened.get_timeseries_template_name()
        _index_pattern = ThingHappened.timeseries_index_wildcard()
        _template_resp = _client.indices.get_index_template(name=_template_name)
        (_t_info,) = _template_resp["index_templates"]
        self.assertEqual(_t_info["name"], _template_name)
        self.assertEqual(
            _t_info["index_template"]["index_patterns"],
            [_index_pattern],
        )
        _properties = _t_info["index_template"]["template"]["mappings"]["properties"]
        self.assertEqual(_properties["timestamp"], {"type": "date"})
        self.assertEqual(_properties["thing_id"], {"type": "keyword"})
        self.assertEqual(_properties["happen_code"], {"type": "keyword"})
        # no indexes; only the template
        self.assertFalse(list(ThingHappened.each_existing_index()))

    def test_check_djelme_setup(self):
        with self.assertRaises(IndexTemplateNotFoundError):
            ThingHappened.check_djelme_setup()
        ThingHappened.sync_index_template()
        assert ThingHappened.check_djelme_setup() is None

        # When settings change, template is out of sync
        ThingHappened._index.settings(
            **{"refresh_interval": "1s", "number_of_shards": 1, "number_of_replicas": 2}
        )
        with self.assertRaises(IndexTemplateOutOfSyncError) as excinfo:
            ThingHappened.check_djelme_setup()
        error = excinfo.exception
        assert error.settings_in_sync is False
        assert error.mappings_in_sync is True
        assert error.patterns_in_sync is True

        ThingHappened.sync_index_template()
        assert ThingHappened.check_djelme_setup() is None


class TestDailyIndexes(RealElasticTestCase):
    def setUp(self):
        super().setUp()
        Dummy8Event.record(timestamp=dt.datetime(1234, 5, 6), intensity=1)
        Dummy8Event.record(timestamp=dt.datetime(1234, 5, 6, 7), intensity=2)
        Dummy8Event.record(timestamp=dt.datetime(1234, 5, 7), intensity=3)
        Dummy8Event.record(timestamp=dt.datetime(1234, 6, 1), intensity=7)
        Dummy8Event.record(timestamp=dt.datetime(1235, 5, 6), intensity=111)
        Dummy8Event.record(timestamp=dt.datetime(2345, 6, 9), intensity=11)
        Dummy8Event.record(timestamp=dt.datetime(2345, 7, 9), intensity=13)
        Dummy8Event.refresh()

    def test_indexes(self):
        _index_names = {
            _strip_test_prefix(_index_status.index_name)
            for _index_status in Dummy8Event.each_existing_index()
        }
        self.assertEqual(
            _index_names,
            {
                "dummy8app_dummy8event_1234.5.6.",
                "dummy8app_dummy8event_1234.5.7.",
                "dummy8app_dummy8event_1234.6.1.",
                "dummy8app_dummy8event_1235.5.6.",
                "dummy8app_dummy8event_2345.6.9.",
                "dummy8app_dummy8event_2345.7.9.",
            },
        )

    def test_search(self):
        def _assert_intens(hits, expected_intensities):
            _actual = {_hit.intensity for _hit in hits}
            self.assertEqual(_actual, expected_intensities)

        _assert_intens(
            Dummy8Event.search(),
            {1, 2, 3, 7, 11, 13, 111},
        )
        _assert_intens(
            Dummy8Event.search_timeseries_range((1234,), (1235,)),
            {1, 2, 3, 7},
        )
        _assert_intens(
            Dummy8Event.search_timeseries_range((1233,), (1234,)),
            set(),
        )
        _assert_intens(
            Dummy8Event.search_timeseries_range(
                dt.date(1234, 5, 6), dt.date(1234, 5, 7)
            ),
            {1, 2},
        )
        _assert_intens(
            Dummy8Event.search_timeseries_range((1234, 6), dt.date(2345, 7, 1)),
            {7, 111, 11},
        )
        _assert_intens(
            Dummy8Event.search_timeseries_range((1234, 5, 6, 2), (1234, 5, 7)),
            {2},
        )


class TestMonthlyIndexes(RealElasticTestCase):
    def setUp(self):
        super().setUp()
        Monthly8Event.record(timestamp=dt.datetime(1234, 5, 6), intenzity=1)
        Monthly8Event.record(timestamp=dt.datetime(1234, 5, 6, 7), intenzity=2)
        Monthly8Event.record(timestamp=dt.datetime(1234, 5, 7), intenzity=3)
        Monthly8Event.record(timestamp=dt.datetime(1234, 6, 1), intenzity=7)
        Monthly8Event.record(timestamp=dt.datetime(1235, 5, 6), intenzity=111)
        Monthly8Event.record(timestamp=dt.datetime(2345, 6, 9), intenzity=11)
        Monthly8Event.record(timestamp=dt.datetime(2345, 7, 9), intenzity=13)
        Monthly8Event.refresh()

    def test_indexes(self):
        _index_names = {
            _strip_test_prefix(_index_status.index_name)
            for _index_status in Monthly8Event.each_existing_index()
        }
        self.assertEqual(
            _index_names,
            {
                "dummy8app_eventlog_1234.5.",
                "dummy8app_eventlog_1234.6.",
                "dummy8app_eventlog_1235.5.",
                "dummy8app_eventlog_2345.6.",
                "dummy8app_eventlog_2345.7.",
            },
        )

    def test_search(self):
        def _assert_intenz(hits, expected_intenzities):
            _actual = {_hit.intenzity for _hit in hits}
            self.assertEqual(_actual, expected_intenzities)

        _assert_intenz(
            Monthly8Event.search(),
            {1, 2, 3, 7, 11, 13, 111},
        )
        _assert_intenz(
            Monthly8Event.search_timeseries_range((1234,), (1235,)),
            {1, 2, 3, 7},
        )
        _assert_intenz(
            Monthly8Event.search_timeseries_range((1233,), (1234,)),
            set(),
        )
        _assert_intenz(
            Monthly8Event.search_timeseries_range(
                dt.date(1234, 5, 6), dt.date(1234, 5, 7)
            ),
            {1, 2},
        )
        _assert_intenz(
            Monthly8Event.search_timeseries_range((1234, 6), dt.date(2345, 7, 1)),
            {7, 111, 11},
        )
        _assert_intenz(
            Monthly8Event.search_timeseries_range((1234, 5, 6, 2), (1234, 5, 7)),
            {2},
        )


class TestYearlyIndexes(RealElasticTestCase):
    def setUp(self):
        super().setUp()
        ThingHappened.record(timestamp=dt.datetime(1234, 5, 6), thing_id="a")
        ThingHappened.record(timestamp=dt.datetime(1234, 5, 6, 7), thing_id="b")
        ThingHappened.record(timestamp=dt.datetime(1234, 5, 7), thing_id="c")
        ThingHappened.record(timestamp=dt.datetime(1234, 6, 1), thing_id="d")
        ThingHappened.record(timestamp=dt.datetime(1235, 5, 6), thing_id="e")
        ThingHappened.record(timestamp=dt.datetime(2345, 6, 9), thing_id="f")
        ThingHappened.record(timestamp=dt.datetime(2345, 7, 9), thing_id="g")
        ThingHappened.refresh()

    def test_indexes(self):
        _index_names = {
            _strip_test_prefix(_index_status.index_name)
            for _index_status in ThingHappened.each_existing_index()
        }
        self.assertEqual(
            _index_names,
            {
                "dummy8app_happen_1234.5.",
                "dummy8app_happen_1234.6.",
                "dummy8app_happen_1235.5.",
                "dummy8app_happen_2345.6.",
                "dummy8app_happen_2345.7.",
            },
        )

    def test_search(self):
        def _assert_things(hits, expected_thing_ids):
            _actual = {_hit.thing_id for _hit in hits}
            self.assertEqual(_actual, expected_thing_ids)

        _assert_things(
            ThingHappened.search(),
            {"a", "b", "c", "d", "e", "f", "g"},
        )
        _assert_things(
            ThingHappened.search_timeseries_range((1234,), (1235,)),
            {"a", "b", "c", "d"},
        )
        _assert_things(
            ThingHappened.search_timeseries_range((1233,), (1234,)),
            set(),
        )
        _assert_things(
            ThingHappened.search_timeseries_range(
                dt.date(1234, 5, 6), dt.date(1234, 5, 7)
            ),
            {"a", "b"},
        )
        _assert_things(
            ThingHappened.search_timeseries_range((1234, 6), dt.date(2345, 7, 1)),
            {"d", "e", "f"},
        )
        _assert_things(
            ThingHappened.search_timeseries_range((1234, 5, 6, 2), (1234, 5, 7)),
            {"b"},
        )


class TestCyclicReport(RealElasticTestCase):
    def setUp(self):
        super().setUp()
        ThingHappeningsReport.record(
            cycle_coverage="2000.1", thing_id="a", happen_count=2
        )
        ThingHappeningsReport.record(
            cycle_coverage="2000.1", thing_id="b", happen_count=3
        )
        ThingHappeningsReport.record(
            cycle_coverage="2000.1", thing_id="c", happen_count=4
        )
        ThingHappeningsReport.record(
            cycle_coverage="2000.2", thing_id="a", happen_count=5
        )
        ThingHappeningsReport.record(  # this duplicate gets overwritten
            cycle_coverage="2000.2", thing_id="b", happen_count=67
        )
        ThingHappeningsReport.record(  # this duplicate overwrites
            cycle_coverage="2000.2", thing_id="b", happen_count=6
        )
        ThingHappeningsReport.record(
            cycle_coverage="2000.2", thing_id="c", happen_count=7
        )
        ThingHappeningsReport.refresh()

    def test_indexes(self):
        _index_names = {
            _strip_test_prefix(_index_status.index_name)
            for _index_status in ThingHappeningsReport.each_existing_index()
        }
        self.assertEqual(
            _index_names,
            {
                "dummy8app_thinghappeningsreport_2000.",
            },
        )

    def test_search(self):
        _b_search = (
            ThingHappeningsReport.search()
            .query({"term": {"thing_id": "b"}})
            .sort("cycle_coverage")
        )
        (_actual_1, _actual_2) = _b_search
        self.assertEqual(_actual_1.cycle_coverage, "2000.1")
        self.assertEqual(_actual_1.thing_id, "b")
        self.assertEqual(_actual_1.happen_count, 3)
        self.assertEqual(_actual_1.timeseries_timeparts, "2000.1")
        self.assertEqual(_actual_2.cycle_coverage, "2000.2")
        self.assertEqual(_actual_2.thing_id, "b")
        self.assertEqual(_actual_2.happen_count, 6)
        self.assertEqual(_actual_2.timeseries_timeparts, "2000.2")

    def test_search_range(self):
        _b_search = ThingHappeningsReport.search_timeseries_range(
            (2000, 2), (2001,)
        ).query({"term": {"thing_id": "b"}})
        (_actual_2,) = _b_search
        self.assertEqual(_actual_2.cycle_coverage, "2000.2")
        self.assertEqual(_actual_2.thing_id, "b")
        self.assertEqual(_actual_2.happen_count, 6)
        self.assertEqual(_actual_2.timeseries_timeparts, "2000.2")


class TestSingleIndex(RealElasticTestCase):
    def test_index_name(self):
        self.assertEqual(
            _strip_test_prefix(SimpleKV._index._name),
            "dummy8app_simplekv",
        )

    def test_search(self):
        SimpleKV.record(key="hello", val=2)
        SimpleKV.record(key="goodbye", val=-2)
        SimpleKV.refresh()
        (_hello,) = SimpleKV.search().query({"term": {"key": "hello"}}).execute()
        self.assertEqual(_hello.key, "hello")
        self.assertEqual(_hello.val, 2)
        (_goodbye,) = SimpleKV.search().query({"term": {"key": "goodbye"}}).execute()
        self.assertEqual(_goodbye.key, "goodbye")
        self.assertEqual(_goodbye.val, -2)


def _strip_test_prefix(index_name: str) -> str:
    # strip uuid test prefix
    (_, _, _without_prefix) = index_name.partition("_")
    return _without_prefix
