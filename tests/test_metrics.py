from elasticsearch_metrics import Metric
from elasticsearch_dsl import IndexTemplate


class PreprintView(Metric):
    class Meta:
        template_name = "osf_metrics-preprint-views"


def test_index_template():
    assert isinstance(PreprintView.get_index_template(), IndexTemplate)
