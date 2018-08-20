import os

SECRET_KEY = "not so secret in tests"
DEBUG = True
ALLOWED_HOSTS = []
INSTALLED_APPS = ["elasticsearch_metrics", "tests.dummyapp"]
MIDDLEWARE_CLASSES = []
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3"}}
TIME_ZONE = "UTC"
ELASTICSEARCH_DSL = {
    "default": {"hosts": os.environ.get("ELASTICSEARCH_HOST", "localhost:9201")}
}
