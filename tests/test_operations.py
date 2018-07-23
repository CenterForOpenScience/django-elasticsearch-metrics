"""Tests for metrics-related migration operations."""
import pytest
from elasticsearch_metrics import Metric
from elasticsearch_metrics.operations import _create_metric
from elasticsearch_dsl import connections

class PreprintView(Metric):
    class Meta:
        template_name = "osf_metrics-preprint-views"

@pytest.fixture()
def client():
    return connections.get_connection('default')

@pytest.mark.es
def test_create_metric_creates_template(client):
    _create_metric(PreprintView)
    assert client.indices.get_template(name="osf_metrics-preprint-views")


@pytest.mark.es
def test_create_metric_creats_template_with_mapping(client):
    _create_metric(PreprintView)
    template = client.indices.get_template(name="osf_metrics-preprint-views")
    mappings = template["osf_metrics-preprint-views"]['mappings']
    properties = mappings['_default_']['properties']
    assert '@timestamp' in properties
    assert properties['@timestamp'] == {'doc_values': True, 'type': 'date'}
