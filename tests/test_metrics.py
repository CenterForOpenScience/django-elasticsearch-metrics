import mock
import pytest
import datetime as dt
from django.utils import timezone
from elasticsearch_metrics import metrics
from elasticsearch_dsl import IndexTemplate

from elasticsearch_metrics import signals
from tests.dummyapp.metrics import (
    DummyMetric,
    DummyMetricWithExplicitTemplateName,
    DummyMetricWithExplicitTemplatePattern,
)


class PreprintView(metrics.Metric):
    provider_id = metrics.Keyword(index=True)
    user_id = metrics.Keyword(index=True)
    preprint_id = metrics.Keyword(index=True)

    class Index:
        settings = {"refresh_interval": "-1"}

    class Meta:
        app_label = "dummyapp"
        template_name = "osf_metrics_preprintviews"
        template = "osf_metrics_preprintviews-*"


class TestGetIndexName:
    def test_get_index_name(self):
        date = dt.date(2020, 2, 14)
        assert (
            PreprintView.get_index_name(date=date)
            == "osf_metrics_preprintviews-2020.02.14"
        )

    def test_get_index_name_respects_date_format_setting(self, settings):
        settings.ELASTICSEARCH_METRICS_DATE_FORMAT = "%Y-%m-%d"
        date = dt.date(2020, 2, 14)
        assert (
            PreprintView.get_index_name(date=date)
            == "osf_metrics_preprintviews-2020-02-14"
        )

    def test_get_index_name_gets_index_for_today_by_default(self):
        today = timezone.now().date()
        today_formatted = today.strftime("%Y.%m.%d")
        assert PreprintView.get_index_name() == "osf_metrics_preprintviews-{}".format(
            today_formatted
        )


class TestGetIndexTemplate:
    def test_get_index_template_returns_template_with_correct_name_and_pattern(self):
        template = PreprintView.get_index_template()
        assert isinstance(template, IndexTemplate)
        assert template._template_name == "osf_metrics_preprintviews"
        assert "osf_metrics_preprintviews-*" in template.to_dict()["index_patterns"]

    def test_get_index_template_respects_index_settings(self):
        template = PreprintView.get_index_template()
        assert template._index.to_dict()["settings"] == {"refresh_interval": "-1"}

    def test_get_index_template_creates_template_with_mapping(self):
        template = PreprintView.get_index_template()
        mappings = template.to_dict()["mappings"]
        assert mappings["doc"]["_all"]["enabled"] is False
        assert mappings["doc"]["_source"]["enabled"] is False
        properties = mappings["doc"]["properties"]
        assert "timestamp" in properties
        assert properties["timestamp"] == {"doc_values": True, "type": "date"}
        assert properties["provider_id"] == {"type": "keyword", "index": True}
        assert properties["user_id"] == {"type": "keyword", "index": True}
        assert properties["preprint_id"] == {"type": "keyword", "index": True}

    def test_declaring_metric_with_no_app_label_or_template_name_errors(self):
        with pytest.raises(RuntimeError):

            class BadMetric(metrics.Metric):
                pass

        with pytest.raises(RuntimeError):

            class MyMetric(metrics.Metric):
                class Meta:
                    template_name = "osf_metrics_preprintviews"

    def test_get_index_template_default_template_name(self):
        template = DummyMetric.get_index_template()
        assert isinstance(template, IndexTemplate)
        assert template._template_name == "dummyapp_dummymetric"
        assert "dummyapp_dummymetric-*" in template.to_dict()["index_patterns"]

    def test_get_index_template_uses_app_label_in_class_meta(self):
        class MyMetric(metrics.Metric):
            class Meta:
                app_label = "myapp"

        template = MyMetric.get_index_template()
        assert template._template_name == "myapp_mymetric"

    def test_template_name_defined_with_no_template_falls_back_to_default_template(
        self
    ):
        template = DummyMetricWithExplicitTemplateName.get_index_template()
        # template name specified in class Meta
        assert template._template_name == "dummymetric"
        # template is not specified, so it's generated
        assert (
            "dummyapp_dummymetricwithexplicittemplatename-*"
            in template.to_dict()["index_patterns"]
        )

    def test_template_defined_with_no_template_name_falls_back_to_default_name(self):
        template = DummyMetricWithExplicitTemplatePattern.get_index_template()
        # template name specified in class Meta
        assert (
            template._template_name == "dummyapp_dummymetricwithexplicittemplatepattern"
        )
        # template is not specified, so it's generated
        assert "dummymetric-*" in template.to_dict()["index_patterns"]

    def test_inheritance(self):
        class MyBaseMetric(metrics.Metric):
            user_id = metrics.Keyword(index=True)

            class Meta:
                abstract = True

        class ConcreteMetric(MyBaseMetric):
            class Meta:
                app_label = "dummyapp"

        template = ConcreteMetric.get_index_template()
        assert template._template_name == "dummyapp_concretemetric"

    def test_source_may_be_enabled(self):
        class MyMetric(metrics.Metric):
            class Meta:
                app_label = "dummyapp"
                template_name = "mymetric"
                template = "mymetric-*"
                source = metrics.MetaField(enabled=True)

        template = MyMetric.get_index_template()

        template_dict = template.to_dict()
        doc = template_dict["mappings"]["doc"]
        assert doc["_all"]["enabled"] is False
        assert doc["_source"]["enabled"] is True


class TestRecord:
    def test_calls_save(self, mock_save):
        timestamp = dt.datetime(2017, 8, 21)
        p = PreprintView.record(timestamp=timestamp, provider_id="abc12")
        assert mock_save.call_count == 1
        assert p.timestamp == timestamp
        assert p.provider_id == "abc12"

    @mock.patch.object(timezone, "now")
    def test_defaults_timestamp_to_now(self, mock_now, mock_save):
        fake_now = dt.datetime(2016, 8, 21)
        mock_now.return_value = fake_now

        p = PreprintView.record(provider_id="abc12")
        assert mock_save.call_count == 1
        assert p.timestamp == fake_now


class TestSignals:
    @mock.patch.object(PreprintView, "get_index_template")
    def test_create_metric_sends_signals(self, mock_get_index_template):
        mock_pre_index_template_listener = mock.Mock()
        mock_post_index_template_listener = mock.Mock()
        signals.pre_index_template_create.connect(mock_pre_index_template_listener)
        signals.post_index_template_create.connect(mock_post_index_template_listener)
        PreprintView.create_index_template()
        assert mock_pre_index_template_listener.call_count == 1
        assert mock_post_index_template_listener.call_count == 1
        pre_call_kwargs = mock_pre_index_template_listener.call_args[1]
        assert "index_template" in pre_call_kwargs
        assert "using" in pre_call_kwargs

        post_call_kwargs = mock_pre_index_template_listener.call_args[1]
        assert "index_template" in post_call_kwargs
        assert "using" in post_call_kwargs

    def test_save_sends_signals(self, mock_save):
        mock_pre_save_listener = mock.Mock()
        mock_post_save_listener = mock.Mock()
        signals.pre_save.connect(mock_pre_save_listener, sender=PreprintView)
        signals.post_save.connect(mock_post_save_listener, sender=PreprintView)

        provider_id = "12345"
        user_id = "abcde"
        preprint_id = "zyxwv"
        doc = PreprintView(
            provider_id=provider_id, user_id=user_id, preprint_id=preprint_id
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


@pytest.mark.es
class TestIntegration:
    def test_init(self, client):
        PreprintView.init()
        name = PreprintView.get_index_name()
        mapping = client.indices.get_mapping(index=name)
        properties = mapping[name]["mappings"]["doc"]["properties"]
        assert properties["timestamp"] == {"type": "date"}
        assert properties["provider_id"] == {"type": "keyword"}
        assert properties["user_id"] == {"type": "keyword"}
        assert properties["preprint_id"] == {"type": "keyword"}

    def test_create_document(self, client):
        provider_id = "12345"
        user_id = "abcde"
        preprint_id = "zyxwv"
        doc = PreprintView(
            provider_id=provider_id, user_id=user_id, preprint_id=preprint_id
        )
        doc.save()
        document = PreprintView.get(id=doc.meta.id, index=PreprintView.get_index_name())
        # TODO flesh out this test more.  Try to query ES?
        assert document is not None
