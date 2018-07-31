import mock
import pytest
import datetime as dt
from django.conf import settings
from django.utils import timezone
from elasticsearch_metrics.metric import Metric
from elasticsearch_dsl import IndexTemplate, connections, Keyword, MetaField

from elasticsearch_metrics.signals import pre_index_template_create
from tests.dummyapp.metrics import (
    DummyMetric,
    DummyMetricWithExplicitTemplateName,
    DummyMetricWithExplicitTemplatePattern,
)


@pytest.fixture()
def client():
    return connections.get_connection()


class PreprintView(Metric):
    provider_id = Keyword(index=True)
    user_id = Keyword(index=True)
    preprint_id = Keyword(index=True)

    class Index:
        settings = {"refresh_interval": "-1"}

    class Meta:
        template_name = "osf_metrics_preprintviews"
        template = "osf_metrics_preprintviews-*"


class TestGetIndexName:
    def test_get_index_name(self):
        date = dt.date(2020, 2, 14)
        assert (
            PreprintView.get_index_name(date=date)
            == "osf_metrics_preprintviews-2020.02.14"
        )

    def test_get_index_name_gets_index_for_today_by_default(self):
        today = timezone.now().date()
        dateformat = settings.DATE_FORMAT
        today_formatted = today.strftime(dateformat)
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

    def test_declaring_metric_with_no_app_label_or_template_name_errors(self):
        with pytest.raises(RuntimeError):

            class BadMetric(Metric):
                pass

        with pytest.raises(RuntimeError):

            class MyMetric(Metric):
                class Meta:
                    template_name = "osf_metrics_preprintviews"

    def test_get_index_template_default_template_name(self):
        template = DummyMetric.get_index_template()
        assert isinstance(template, IndexTemplate)
        assert template._template_name == "dummyapp_dummymetric"
        assert "dummyapp_dummymetric-*" in template.to_dict()["index_patterns"]

    def test_get_index_template_uses_app_label_in_class_meta(self):
        class MyMetric(Metric):
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
        class MyBaseMetric(Metric):
            user_id = Keyword(index=True)

            class Meta:
                abstract = True

        class ConcreteMetric(MyBaseMetric):
            class Meta:
                app_label = "dummyapp"

        template = ConcreteMetric.get_index_template()
        assert template._template_name == "dummyapp_concretemetric"


class TestIntegration:
    @classmethod
    def setup_class(cls):
        # TODO hook into pytest.mark.es to delete indices
        client().indices.delete(index="*")
        client().indices.delete_template("*")

    @classmethod
    def teardown_class(cls):
        client().indices.delete(index="*")
        client().indices.delete_template("*")

    @pytest.mark.es
    def test_init(self, client):
        PreprintView.init()
        name = PreprintView.get_index_name()
        mapping = client.indices.get_mapping(index=name)
        properties = mapping[name]["mappings"]["doc"]["properties"]
        assert properties["timestamp"] == {"type": "date"}
        assert properties["provider_id"] == {"type": "keyword"}
        assert properties["user_id"] == {"type": "keyword"}
        assert properties["preprint_id"] == {"type": "keyword"}

    @pytest.mark.es
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

    @pytest.mark.es
    def test_create_metric_creates_template_with_mapping(self, client):
        PreprintView.create_index_template()
        template_name = PreprintView._template_name
        template = client.indices.get_template(name=template_name)
        mappings = template[template_name]["mappings"]
        assert mappings["doc"]["_all"]["enabled"] is False
        assert mappings["doc"]["_source"]["enabled"] is False
        properties = mappings["doc"]["properties"]
        assert "timestamp" in properties
        assert properties["timestamp"] == {"doc_values": True, "type": "date"}
        assert properties["provider_id"] == {"type": "keyword", "index": True}
        assert properties["user_id"] == {"type": "keyword", "index": True}
        assert properties["preprint_id"] == {"type": "keyword", "index": True}

    @pytest.mark.es
    def test_create_metric_sends_pre_index_template_create_signal(self):
        mock_listener = mock.Mock()
        pre_index_template_create.connect(mock_listener)
        PreprintView.create_index_template()
        assert mock_listener.call_count == 1
        assert "index_template" in mock_listener.call_args[1]

    # TODO: Can we make this test not use ES?
    @pytest.mark.es
    def test_source_may_be_enabled(self, client):
        class MyMetric(Metric):
            class Meta:
                template_name = "mymetric"
                template = "mymetric-*"
                source = MetaField(enabled=True)

        MyMetric.create_index_template()
        template_name = MyMetric._template_name
        template = client.indices.get_template(name=template_name)
        mappings = template[template_name]["mappings"]
        assert mappings["doc"]["_all"]["enabled"] is False
        assert mappings["doc"]["_source"]["enabled"] is True
