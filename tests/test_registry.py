import pytest

from elasticsearch_metrics.metrics import Metric
from elasticsearch_metrics.registry import registry
from tests.dummyapp.metrics import DummyMetric


class MetricWithAppLabel(Metric):
    class Meta:
        app_label = "dummyapp"


def test_metric_in_app_is_in_registry():
    assert "dummyapp" in registry.all_metrics
    assert registry.all_metrics["dummyapp"]["dummymetric"] is DummyMetric


def test_metric_with_explicit_label_set_is_in_regisry():
    assert registry.all_metrics["dummyapp"]["metricwithapplabel"] is MetricWithAppLabel


def test_conflicting_metric():
    with pytest.raises(RuntimeError):

        class DummyMetric(Metric):
            class Meta:
                app_label = "dummyapp"


def test_get_metric():
    assert registry.get_metric("dummyapp", "DummyMetric") is DummyMetric
    assert registry.get_metric("dummyapp.DummyMetric") is DummyMetric

    with pytest.raises(LookupError) as excinfo:
        registry.get_metric("dummyapp", "DoesNotExist")
    assert (
        "App 'dummyapp' doesn't have a 'DoesNotExist' metric." in excinfo.value.args[0]
    )

    with pytest.raises(LookupError) as excinfo:
        registry.get_metric("notanapp", "DummyMetric")
    assert "No metrics found in app with label 'notanapp'." in excinfo.value.args[0]


def test_get_metrics():
    class AnotherMetric(Metric):
        class Meta:
            app_label = "anotherapp"

    assert DummyMetric in registry.get_metrics()
    assert DummyMetric in registry.get_metrics(app_label="dummyapp")
    assert AnotherMetric not in registry.get_metrics(app_label="dummyapp")

    with pytest.raises(LookupError):
        registry.get_metrics("notanapp")
