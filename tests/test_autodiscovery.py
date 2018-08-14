from elasticsearch_metrics.registry import registry


def test_app_metrics_are_automatically_registered():
    # dummyapp.DummyMetric should already be registered because it's
    # in metrics.py
    assert registry.get_metric("dummyapp.DummyMetric")
