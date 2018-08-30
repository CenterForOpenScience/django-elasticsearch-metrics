from django.apps import AppConfig
from django.conf import settings
from elasticsearch_dsl.connections import connections
from django.utils.module_loading import autodiscover_modules

__version__ = "3.2.0"

default_app_config = "elasticsearch_metrics.ElasticsearchMetricsConfig"


class ElasticsearchMetricsConfig(AppConfig):
    name = "elasticsearch_metrics"

    def ready(self):
        connections.configure(**settings.ELASTICSEARCH_DSL)
        autodiscover_modules("metrics")
