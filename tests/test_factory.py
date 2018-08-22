import factory

from elasticsearch_metrics import metrics
from elasticsearch_metrics.factory import MetricFactory
from tests.dummyapp.metrics import DummyMetric


class DummyMetricFactory(MetricFactory):
    my_int = factory.Faker("pyint")

    class Meta:
        model = DummyMetric


def test_build():
    metric = DummyMetricFactory.build()
    assert isinstance(metric, metrics.Metric)
    assert isinstance(metric.my_int, int)


def test_save(mock_save):
    metric = DummyMetricFactory()
    assert isinstance(metric, metrics.Metric)
    assert mock_save.call_count == 1
