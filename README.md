# django-elasticsearch-metrics

[![pypi](https://badge.fury.io/py/django-elasticsearch-metrics.svg)](https://badge.fury.io/py/django-elasticsearch-metrics)
[![Build Status](https://travis-ci.org/sloria/django-elasticsearch-metrics.svg?branch=master)](https://travis-ci.org/sloria/django-elasticsearch-metrics)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)

Django app for storing time-series metrics in Elasticsearch.

## Pre-requisites

* Python 2.7 or >=3.6
* Django 1.11 or 2.0
* Elasticsearch 6

## Install

```
pip install django-elasticsearch-metrics
```

## Quickstart

Add `"elasticseach_metrics"` to `INSTALLED_APPS`.

```python
INSTALLED_APPS += ["elasticsearch_metrics"]
```

Define the `ELASTICSEARCH_DSL` setting.

```python
ELASTICSEARCH_DSL = {"default": {"hosts": "localhost:9200"}}
```

This setting is passed to [`elasticsearch_dsl.connections.configure`](http://elasticsearch-dsl.readthedocs.io/en/stable/configuration.html#multiple-clusters) so
it takes the same parameters.


In one of your apps, define a new metric in `metrics.py`.

A `Metric` is a subclass of [`elasticsearch_dsl.Document`](https://elasticsearch-dsl.readthedocs.io/en/stable/api.html#document).


```python
# myapp/metrics.py

from elasticsearch_metrics import metrics


class PageView(metrics.Metric):
    user_id = metrics.Integer()
```

Use the `sync_metrics` management command to ensure that the [index template](https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-templates.html)
for your metric is created in Elasticsearch.

```shell
# This will create an index template called myapp_pageview
python manage.py sync_metrics
```

Now add some data:

```python
from myapp.metrics import PageView

user = User.objects.latest()

# By default we create an index for each day.
# Therefore, this will persist the document
# to an index called, e.g. "myapp_pageview-2020.02.04"
PageView.record(user_id=user.id)
```

Go forth and search!

```python
# perform a search across all page views
PageView.search()
```

## Per-month or per-year indices

By default, an index is created for every day that a metric is saved.
You can change this to create an index per month or per year by changing
the `ELASTICSEARCH_METRICS_DATE_FORMAT` setting.


```python
# settings.py

# Monthly:
ELASTICSEARCH_METRICS_DATE_FORMAT = "%Y.%m"

# Yearly:
ELASTICSEARCH_METRICS_DATE_FORMAT = "%Y"
```

## Index settings

You can configure the index template settings by setting
`Metric.Index.settings`.

```python
class PageView(metrics.Metric):
    user_id = metrics.Integer()

    class Index:
        settings = {"number_of_shards": 2, "refresh_interval": "5s"}
```

## Index templates

Each `Metric` will have its own [index template](https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-templates.html).
The index template name and glob pattern are computed from the app label
for the containing app and the class's name. For example, a `PageView`
class defined in `myapp/metrics.py` will have an index template with the
name `myapp_pageview` and a template glob pattern of `myapp_pageview-*`.

If you declare a `Metric` outside of an app, you will need to set
`app_label`.


```python
class PageView(metrics.Metric):
    class Meta:
        app_label = "myapp"
```

Alternatively, you can set `template_name` and/or `template` explicitly.

```python
class PageView(metrics.Metric):
    user_id = metrics.Integer()

    class Meta:
        template_name = "myapp_pviews"
        template = "myapp_pviews-*"
```

## Abstract metrics

```python
from elasticsearch_metrics import metrics


class MyBaseMetric(metrics.Metric):
    user_id = metrics.Integer()

    class Meta:
        abstract = True


class PageView(MyBaseMetric):
    class Meta:
        app_label = "myapp"
```

## Optional factory_boy integration

```python
import factory
from elasticsearch_metrics.factory import MetricFactory

from ..myapp.metrics import MyMetric


class MyMetricFactory(MetricFactory):
    my_int = factory.Faker("pyint")

    class Meta:
        model = MyMetric


def test_something():
    metric = MyMetricFactory()  # index metric in ES
    assert isinstance(metric.my_int, int)
```

## Configuration

* `ELASTICSEARCH_DSL`: Required. Connection settings passed to
  [`elasticsearch_dsl.connections.configure`](http://elasticsearch-dsl.readthedocs.io/en/stable/configuration.html#multiple-clusters).
* `ELASTICSEARCH_METRICS_DATE_FORMAT`: Date format to use when creating
    indexes. Default: `%Y.%m.%d` (same date format Elasticsearch uses for
    [date math](https://www.elastic.co/guide/en/elasticsearch/reference/current/date-math-index-names.html))

## Management commands

* `sync_metrics`: Ensure that index templates have been created for
    your metrics.

```
python manage.py sync_metrics
```

* `show_metrics`: Pretty-print a listing of all registered metrics.

```
python manage.py show_metrics
```

<!-- * `clean_metrics` : Clean old data using [curator](https://curator.readthedocs.io/en/latest/). -->
<!--  -->
<!-- ``` -->
<!-- python manage.py clean_metrics myapp.PageView --older-than 45 --time-unit days -->
<!-- ``` -->

## Signals

Signals are located in the `elasticsearch_metrics.signals` module.

* `pre_index_template_create(Metric, index_template, using)`: Sent before `PUT`ting a new index
    template into Elasticsearch.
* `post_index_template_create(Metric, index_template, using)`: Sent after `PUT`ting a new index
    template into Elasticsearch.
* `pre_save(Metric, instance, using, index)`: Sent at the beginning of a
    Metric's `save()` method.
* `post_save(Metric, instance, using, index)`: Sent at the end of a
    Metric's `save()` method.

## Caveats

* `_source` and `_all` are disabled by default on metric indices in order to save
    disk space. For most metrics use cases, Users will not need to retrieve the source
    JSON documents. Be sure to understand the consequences of
    this: https://www.elastic.co/guide/en/elasticsearch/reference/current/mapping-source-field.html#_disabling_source .
    To enable `_source`, you can override it in `class Meta`.

```python
class MyMetric(metrics.Metric):
    class Meta:
        source = metrics.MetaField(enabled=True)
```

## Resources

* [Elasticsearch as a Time Series Data Store](https://www.elastic.co/blog/elasticsearch-as-a-time-series-data-store)
* [Pythonic Analytics with Elasticsearch](https://www.elastic.co/blog/pythonic-analytics-with-elasticsearch)
* [In Search of Agile Time Series Database](https://taowen.gitbooks.io/tsdb/content/index.html)

## License

MIT Licensed.
