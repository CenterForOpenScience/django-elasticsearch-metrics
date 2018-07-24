from django.apps import AppConfig
from django.conf import settings

from elasticsearch_metrics.metric import Metric
from elasticsearch_dsl.connections import connections

__version__ = "0.0.0"
__all__ = ("Metric",)

default_app_config = "elasticsearch_metrics.ElasticsearchMetricsConfig"


class ElasticsearchMetricsConfig(AppConfig):
    name = "elasticsearch_metrics"

    def ready(self):
        print("configuring connections")
        connections.configure(**settings.ELASTICSEARCH_DSL)
