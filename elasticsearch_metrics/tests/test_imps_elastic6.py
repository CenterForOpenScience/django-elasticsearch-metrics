import unittest
from unittest import mock
import datetime as dt

from django.utils import timezone

from elasticsearch_metrics.imps import elastic6
from elasticsearch6_dsl import (
    IndexTemplate,
    analyzer,
    tokenizer,
    connections,
)
from elasticsearch6_dsl.document import MetaField

from elasticsearch_metrics import signals
from elasticsearch_metrics.exceptions import (
    IndexTemplateNotFoundError,
    IndexTemplateOutOfSyncError,
)
from elasticsearch_metrics.tests.util import (
    SimpleDjelmeTestCase,
    MockConnectionTestCase,
    RealElasticTestCase,
    NoSetupRealElasticTestCase,
)
from elasticsearch_metrics.tests.dummy6app.metrics import (
    Dummy6Metric,
    Dummy6MetricWithExplicitTemplateName,
)

route_prefix_analyzer = analyzer(
    "route_prefix_analyzer",
    tokenizer=tokenizer("route_prefix_tokenizer", "path_hierarchy", delimiter="."),
)


class PreprintView(elastic6.Metric):
    provider_id = elastic6.Keyword(index=True)
    page_id = elastic6.Keyword(index=True)
    preprint_id = elastic6.Keyword(index=True)
    route_name = elastic6.Text(analyzer=route_prefix_analyzer)

    class Index:
        settings = {"refresh_interval": "-1"}

    class Meta:
        app_label = "dummy6app"
        template_name = "osf_metrics_preprintviews"


class TestGetIndexName(SimpleDjelmeTestCase):
    def test_get_index_name(self):
        date = dt.date(2020, 2, 14)
        assert (
            PreprintView.get_index_name(date=date)
            == "osf_metrics_preprintviews_2020.02.14"
        )

    def test_get_index_name_respects_date_format_setting(self):
        with self.settings(ELASTICSEARCH_METRICS_DATE_FORMAT="%Y-%m-%d"):
            date = dt.date(2020, 2, 14)
            assert (
                PreprintView.get_index_name(date=date)
                == "osf_metrics_preprintviews_2020-02-14"
            )

    def test_get_index_name_gets_index_for_today_by_default(self):
        today = timezone.now().date()
        today_formatted = today.strftime("%Y.%m.%d")
        assert PreprintView.get_index_name() == "osf_metrics_preprintviews_{}".format(
            today_formatted
        )


class TestGetIndexTemplate(SimpleDjelmeTestCase):
    def test_get_index_template_returns_template_with_correct_name_and_pattern(self):
        template = PreprintView.get_timeseries_index_template()
        assert isinstance(template, IndexTemplate)
        assert template._template_name == "osf_metrics_preprintviews"
        assert "osf_metrics_preprintviews_*" in template.to_dict()["index_patterns"]

    def test_get_index_template_respects_index_settings(self):
        template = PreprintView.get_timeseries_index_template()
        assert template._index.to_dict()["settings"] == {
            "refresh_interval": "-1",
            "analysis": {
                "analyzer": {
                    "route_prefix_analyzer": {
                        "tokenizer": "route_prefix_tokenizer",
                        "type": "custom",
                    },
                },
                "tokenizer": {
                    "route_prefix_tokenizer": {
                        "delimiter": ".",
                        "type": "path_hierarchy",
                    },
                },
            },
        }

    def test_get_index_template_creates_template_with_mapping(self):
        template = PreprintView.get_timeseries_index_template()
        mappings = template.to_dict()["mappings"]
        assert mappings["doc"]["_source"]["enabled"] is False
        properties = mappings["doc"]["properties"]
        assert "timestamp" in properties
        assert properties["timestamp"] == {"doc_values": True, "type": "date"}
        assert properties["provider_id"] == {"type": "keyword", "index": True}
        assert properties["page_id"] == {"type": "keyword", "index": True}
        assert properties["preprint_id"] == {"type": "keyword", "index": True}

    # regression test
    def test_mappings_are_not_shared(self):
        template1 = Dummy6Metric.get_timeseries_index_template()
        template2 = Dummy6MetricWithExplicitTemplateName.get_timeseries_index_template()
        assert "my_int" in template1.to_dict()["mappings"]["doc"]["properties"]
        assert "my_keyword" not in template1.to_dict()["mappings"]["doc"]["properties"]
        assert "my_int" not in template2.to_dict()["mappings"]["doc"]["properties"]
        assert "my_keyword" in template2.to_dict()["mappings"]["doc"]["properties"]

    @unittest.skip(
        "TODO: detects containing app, now tests under elasticsearch_metrics"
    )
    def test_declaring_metric_with_no_app_label_or_template_name_errors(self):
        with self.assertRaises(RuntimeError):

            class BadMetric(elastic6.Metric):
                pass

        with self.assertRaises(RuntimeError):

            class MyMetric(elastic6.Metric):
                class Meta:
                    template_name = "osf_metrics_preprintviews"

    def test_get_index_template_default_template_name(self):
        template = Dummy6Metric.get_timeseries_index_template()
        assert isinstance(template, IndexTemplate)
        assert template._template_name == "dummy6app_dummy6metric"
        assert "dummy6app_dummy6metric_*" in template.to_dict()["index_patterns"]

    def test_get_index_template_uses_app_label_in_class_meta(self):
        class MyMetric(elastic6.Metric):
            class Meta:
                app_label = "myapp"

        template = MyMetric.get_timeseries_index_template()
        assert template._template_name == "myapp_mymetric"

    def test_template_name_defined_with_no_template_falls_back_to_default_template(
        self,
    ):
        template = Dummy6MetricWithExplicitTemplateName.get_timeseries_index_template()
        # template name specified in class Meta
        assert template._template_name == "dummy6metric"
        # template pattern generated using template name
        assert "dummy6metric_*" in template.to_dict()["index_patterns"]

    def test_inheritance(self):
        class MyBaseMetric(elastic6.Metric):
            page_id = elastic6.Keyword(index=True)

            class Index:
                settings = {"number_of_shards": 2}

            class Meta:
                abstract = True

        class ConcreteMetric(MyBaseMetric):
            class Meta:
                app_label = "dummy6app"

        template = ConcreteMetric.get_timeseries_index_template()
        assert template._template_name == "dummy6app_concretemetric"
        assert template._index.to_dict()["settings"] == {"number_of_shards": 2}

    def test_source_may_be_enabled(self):
        class MyMetric(elastic6.Metric):
            class Meta:
                app_label = "dummy6app"
                template_name = "mymetric"
                source = MetaField(enabled=True)

        template = MyMetric.get_timeseries_index_template()

        template_dict = template.to_dict()
        doc = template_dict["mappings"]["doc"]
        assert doc["_source"]["enabled"] is True


class TestRecord(MockConnectionTestCase):
    def test_calls_index(self):
        timestamp = dt.datetime(2017, 8, 21)
        p = PreprintView.record(timestamp=timestamp, provider_id="abc12")
        assert self.mock_es6_connection.index.call_count == 1
        assert p.timestamp == timestamp
        assert p.provider_id == "abc12"

    @mock.patch.object(timezone, "now")
    def test_defaults_timestamp_to_now(self, mock_now):
        fake_now = dt.datetime(2016, 8, 21)
        mock_now.return_value = fake_now

        p = PreprintView.record(provider_id="abc12")
        assert self.mock_es6_connection.index.call_count == 1
        assert p.timestamp == fake_now


class TestSignals(MockConnectionTestCase):
    @mock.patch.object(PreprintView, "get_timeseries_index_template")
    def test_create_metric_sends_signals(self, mock_get_index_template):
        mock_pre_index_template_listener = mock.Mock()
        mock_post_index_template_listener = mock.Mock()
        signals.pre_index_template_create.connect(mock_pre_index_template_listener)
        signals.post_index_template_create.connect(mock_post_index_template_listener)
        PreprintView.sync_index_template()
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
        signals.pre_save.connect(mock_pre_save_listener, sender=PreprintView)
        signals.post_save.connect(mock_post_save_listener, sender=PreprintView)

        provider_id = "12345"
        page_id = "abcde"
        preprint_id = "zyxwv"
        doc = PreprintView(
            provider_id=provider_id, page_id=page_id, preprint_id=preprint_id
        )
        doc.save()

        assert mock_pre_save_listener.call_count == 1
        pre_save_kwargs = mock_pre_save_listener.call_args[1]
        assert isinstance(pre_save_kwargs["instance"], PreprintView)
        assert "index" in pre_save_kwargs
        assert "using" in pre_save_kwargs
        assert pre_save_kwargs["sender"] is PreprintView

        assert mock_post_save_listener.call_count == 1
        post_save_kwargs = mock_pre_save_listener.call_args[1]
        assert isinstance(post_save_kwargs["instance"], PreprintView)
        assert "index" in post_save_kwargs
        assert "using" in post_save_kwargs
        assert post_save_kwargs["sender"] is PreprintView


class TestIntegration(RealElasticTestCase):
    @property
    def es6_client(self):
        return connections.get_connection("my_elastic6")

    def test_create_document(self):
        provider_id = "12345"
        page_id = "abcde"
        preprint_id = "zyxwv"
        doc = PreprintView(
            provider_id=provider_id, page_id=page_id, preprint_id=preprint_id
        )
        doc.save()
        document = PreprintView.get(id=doc.meta.id, index=PreprintView.get_index_name())
        assert document is not None  # TODO: more thoroughly

        # index mappings should match the index template
        name = PreprintView.get_index_name()
        mapping = self.es6_client.indices.get_mapping(index=name)
        properties = mapping[name]["mappings"]["doc"]["properties"]
        assert properties["timestamp"] == {"type": "date"}
        assert properties["provider_id"] == {"type": "keyword"}
        assert properties["page_id"] == {"type": "keyword"}
        assert properties["preprint_id"] == {"type": "keyword"}


class TestIntegrationSetup(NoSetupRealElasticTestCase):
    @property
    def es6_client(self):
        return connections.get_connection("my_elastic6")

    def test_init(self):
        PreprintView.init()
        name = PreprintView.get_index_name()
        mapping = self.es6_client.indices.get_mapping(index=name)
        properties = mapping[name]["mappings"]["doc"]["properties"]
        assert properties["timestamp"] == {"type": "date"}
        assert properties["provider_id"] == {"type": "keyword"}
        assert properties["page_id"] == {"type": "keyword"}
        assert properties["preprint_id"] == {"type": "keyword"}

    def test_check_djelme_setup(self):
        with self.assertRaises(IndexTemplateNotFoundError):
            PreprintView.check_djelme_setup()
        PreprintView.sync_index_template()
        assert PreprintView.check_djelme_setup() is None

        # When settings change, template is out of sync
        PreprintView._index.settings(
            **{"refresh_interval": "1s", "number_of_shards": 1, "number_of_replicas": 2}
        )
        with self.assertRaises(IndexTemplateOutOfSyncError) as excinfo:
            PreprintView.check_djelme_setup()
        error = excinfo.exception
        assert error.settings_in_sync is False
        assert error.mappings_in_sync is True
        assert error.patterns_in_sync is True

        PreprintView.sync_index_template()
        assert PreprintView.check_djelme_setup() is None
