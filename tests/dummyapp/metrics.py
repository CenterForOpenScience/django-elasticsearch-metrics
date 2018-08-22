from elasticsearch_metrics import metrics


class DummyMetric(metrics.Metric):
    my_int = metrics.Integer()


class DummyMetricWithExplicitTemplateName(metrics.Metric):
    class Meta:
        template_name = "dummymetric"


class DummyMetricWithExplicitTemplatePattern(metrics.Metric):
    class Meta:
        template = "dummymetric-*"
