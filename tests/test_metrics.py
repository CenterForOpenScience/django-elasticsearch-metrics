import mock
import pytest
import datetime as dt

from django.utils import timezone
from elasticsearch_metrics import Metric
from elasticsearch_dsl import IndexTemplate, connections, Keyword, MetaField

from elasticsearch_metrics.signals import pre_index_template_create


@pytest.fixture()
def client():
    return connections.get_connection()


class PreprintView(Metric):
    # TODO these fields are not appearing in the mapping
    provider_id = Keyword(index=True)
    user_id = Keyword(index=True)
    preprint_id = Keyword(index=True)

    class Index:
        settings = {"refresh_interval": "-1"}

    class Meta:
        # TODO: Make this unnecessary and compute this.
        template_name = "osf_metrics_preprintviews"
        template = "osf_metrics_preprintviews-*"


def test_get_index_template_returns_template_with_correct_name_and_pattern():
    template = PreprintView.get_index_template()
    assert isinstance(template, IndexTemplate)
    assert template._template_name == "osf_metrics_preprintviews"
    assert "osf_metrics_preprintviews-*" in template.to_dict()["index_patterns"]


def test_get_index_template_respects_index_settings():
    template = PreprintView.get_index_template()
    assert template._index.to_dict()["settings"] == {"refresh_interval": "-1"}


@pytest.mark.xfail
def test_get_index_template_returns_template_with_correct_mapping():
    assert 0, "todo"


def test_get_index_name():
    date = dt.date(2020, 2, 14)
    assert (
        PreprintView.get_index_name(date=date) == "osf_metrics_preprintviews-2020.02.14"
    )


def test_get_index_name_gets_index_for_today_by_default():
    today = timezone.now().date()
    # TODO: should be in settings
    dateformat = "%Y.%m.%d"
    today_formatted = today.strftime(dateformat)
    assert PreprintView.get_index_name() == "osf_metrics_preprintviews-{}".format(
        today_formatted
    )


@pytest.mark.es
def test_create_metric_creates_template_with_mapping(client):
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


def test_create_metric_sends_pre_index_template_create_signal():
    mock_listener = mock.Mock()
    pre_index_template_create.connect(mock_listener)
    PreprintView.create_index_template()
    assert mock_listener.call_count == 1
    assert "index_template" in mock_listener.call_args[1]


# TODO: Can we make this test not use ES?
@pytest.mark.es
def test_source_may_be_enabled(client):
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
