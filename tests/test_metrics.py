import pytest
import datetime as dt

from django.utils import timezone
from elasticsearch_metrics import Metric
from elasticsearch_dsl import IndexTemplate, connections


@pytest.fixture()
def client():
    return connections.get_connection()


class PreprintView(Metric):
    class Meta:
        # TODO: Make this unnecessary and compute this.
        template_name = "osf_metrics_preprintviews"
        template = "osf_metrics_preprintviews-*"


def test_get_index_template():
    template = PreprintView.get_index_template()
    assert isinstance(template, IndexTemplate)
    assert template._template_name == "osf_metrics_preprintviews"
    assert "osf_metrics_preprintviews-*" in template.to_dict()["index_patterns"]


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
def test_create_metric_creats_template_with_mapping(client):
    PreprintView.create_index_template()

    template = client.indices.get_template(name="osf_metrics-preprint-views")
    mappings = template["osf_metrics-preprint-views"]["mappings"]
    properties = mappings["_default_"]["properties"]
    assert "timestamp" in properties
    assert properties["timestamp"] == {"doc_values": True, "type": "date"}
