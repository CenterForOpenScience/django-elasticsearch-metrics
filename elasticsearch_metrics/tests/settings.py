import os

SECRET_KEY = "not so secret in tests"
DEBUG = True
USE_TZ = True
TIMEZONE = "UTC"
ALLOWED_HOSTS = []
INSTALLED_APPS = [
    "elasticsearch_metrics.apps.ElasticsearchMetricsConfig",
    "elasticsearch_metrics.tests.dummy6app",
    "elasticsearch_metrics.tests.dummy8app",
]
MIDDLEWARE_CLASSES = []
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": "test_djelme"}}

DJELME_BACKENDS = {
    "my_elastic6": {
        "elasticsearch_metrics.imps.elastic6": {
            "hosts": os.environ.get("ELASTICSEARCH6_URL", ""),
        },
    },
    "my_elastic8": {
        "elasticsearch_metrics.imps.elastic8": {
            "hosts": os.environ.get("ELASTICSEARCH8_URL", ""),
        },
    },
}
