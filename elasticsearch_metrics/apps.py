from django.apps import AppConfig
from django.conf import settings
from elasticsearch6_dsl.connections import connections
from django.utils.module_loading import autodiscover_modules


class ElasticsearchMetricsConfig(AppConfig):
    name = "elasticsearch_metrics"

    def ready(self):
        connections.configure(**settings.ELASTICSEARCH_DSL)
        autodiscover_modules("metrics")
