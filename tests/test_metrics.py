import mock
import pytest
import datetime as dt
from django.conf import settings
from django.utils import timezone
from elasticsearch_metrics import Metric
from elasticsearch_dsl import IndexTemplate, connections, Keyword

from elasticsearch_metrics.signals import pre_index_template_create


@pytest.fixture()
def client():
    return connections.get_connection()


class PreprintView(Metric):
    # TODO these fields are not appearing in the mapping
    provider_id = Keyword(index=True)
    user_id = Keyword(index=True)
    preprint_id = Keyword(index=True)

    class Meta:
        # TODO: Make this unnecessary and compute this.
        template_name = "osf_metrics_preprintviews"
        template = "osf_metrics_preprintviews-*"


class TestPreprintView:
    @classmethod
    def setup_class(cls):
        client().indices.delete(index="*")

    @classmethod
    def teardown_class(cls):
        client().indices.delete(index="*")

    def test_get_index_template(self):
        template = PreprintView.get_index_template()
        assert isinstance(template, IndexTemplate)
        assert template._template_name == "osf_metrics_preprintviews"
        assert "osf_metrics_preprintviews-*" in template.to_dict()["index_patterns"]

    @pytest.mark.es
    def test_create_index(self, client):
        PreprintView.create_index()
        name = PreprintView.get_index_name()
        mapping = client.indices.get_mapping(index=name)
        properties = mapping[name]["mappings"]["doc"]["properties"]
        assert properties["timestamp"] == {"type": "date"}
        assert properties["provider_id"] == {"type": "keyword"}
        assert properties["user_id"] == {"type": "keyword"}
        assert properties["preprint_id"] == {"type": "keyword"}

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

    def test_create_metric_sends_pre_index_template_create_signal(self):
        mock_listener = mock.Mock()
        pre_index_template_create.connect(mock_listener)
        PreprintView.create_index_template()
        assert mock_listener.call_count == 1
        assert "index_template" in mock_listener.call_args[1]
