from django.apps import AppConfig
from django.conf import settings
from elasticsearch_dsl.connections import connections

__version__ = "0.0.0"

default_app_config = "elasticsearch_metrics.ElasticsearchMetricsConfig"


class ElasticsearchMetricsConfig(AppConfig):
    name = "elasticsearch_metrics"

    def ready(self):
        connections.configure(**settings.ELASTICSEARCH_DSL)
