# django-elasticsearch-metrics

<!-- [![pypi](https://badge.fury.io/py/django-elasticsearch-metrics.svg)](https://badge.fury.io/py/django-elasticsearch-metrics) -->
[![Build Status](https://travis-ci.org/sloria/django-elasticsearch-metrics.svg?branch=master)](https://travis-ci.org/sloria/django-elasticsearch-metrics)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)

Django app for storing time-series metrics in Elasticsearch.

**[Work in progress]** Below is a sci-fi API. This isn't working yet!

## Pre-requisites

* Python 2.7 or >=3.6
* Django 1.11 or 2.0
* Elasticsearch 6

## Quickstart

Add `"elasticseach_metrics"` to `INSTALLED_APPS`.

```python
INSTALLED_APPS += [
    "elasticsearch_metrics",
]
```

Define the `ELASTICSEARCH_DSL` setting.

```python
ELASTICSEARCH_DSL = {
    "default": {"hosts": "localhost:9200"}
}
```

This setting is passed to [`elasticsearch_dsl.connections.configure`](http://elasticsearch-dsl.readthedocs.io/en/stable/configuration.html#multiple-clusters) so
it takes the same parameters.


In one of your apps, define a new metric in `metrics.py`.

A `Metric` is a subclass of [`elasticsearch_dsl.Document`](https://elasticsearch-dsl.readthedocs.io/en/stable/api.html#document).


```python
# myapp/metrics.py

from elasticsearch_metrics import Metric
from elasticsearch_dsl import Integer

class PageView(Metric):
    user_id = Integer()
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

view = PageView(user_id=user.id)
# By default we create an index for each day.
# Therefore, this will persist the document
# to an index called, e.g. "myapp_pageview-2020.02.04"
view.save()
```

Go forth and search!

```python
# perform a search across all page views
PageView.search()
```

## Index settings

You can configure the index template settings by setting
`Metric.Index.settings`.

```python
class PageView(Metric):
    user_id = Integer()

    class Index:
        settings = {
            "number_of_shards": 2
        }
```

You can even override the default template index name and glob pattern.

```python
class PageView(Metric):
    user_id = Integer()

    class Index:
        template_name = "myapp_pviews"
        template = "myapp_pviews-*"
        settings = {
            "number_of_shard": 2
        }
```


## Configuration

* `ELASTICSEARCH_DSL`: Required. Connection settings passed to
  [`elasticsearch_dsl.connections.configure`](http://elasticsearch-dsl.readthedocs.io/en/stable/configuration.html#multiple-clusters).
* `ELASTICSEARCH_METRICS_DATEFORMAT`: Dateformat to use when creating
    indexes. Default: `%Y.%m.%d` (same dateformat Elasticsearch uses for
    [date math](https://www.elastic.co/guide/en/elasticsearch/reference/current/date-math-index-names.html))

## Management commands

* `sync_metrics`: Ensure that all index templates have been created for
    your metrics.

```
python manage.py sync_metrics
```

* `clean_metrics` : Clean old data using [curator](https://curator.readthedocs.io/en/latest/).

```
python manage.py clean_metrics myapp.PageView --older-than 45 --time-unit days 
```

## License

MIT Licensed.
