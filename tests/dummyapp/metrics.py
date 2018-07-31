from elasticsearch_metrics.metrics import Metric


class DummyMetric(Metric):
    pass


class DummyMetricWithExplicitTemplateName(Metric):
    class Meta:
        template_name = "dummymetric"


class DummyMetricWithExplicitTemplatePattern(Metric):
    class Meta:
        template = "dummymetric-*"
