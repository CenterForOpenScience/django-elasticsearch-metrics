# Changelog

## 4.0.3 (2018-10-15)

Bug fixes:

* Fix `check_metrics` exiting with an error when "number_of_shards"  or
    "number_of_replicas" is set on a metric.

## 4.0.2 (2018-10-08)

Bug fixes:

* Don't set `_all` on mappings. This prevents a DeprecationWarning in
    Elasticsearch 6.

## 4.0.1 (2018-10-05)

Bug fixes:

* Fix inheritance of `Index` settings.

## 4.0.0 (2018-09-04)

Features:

* Add `Metric.check_index_template`, which checks that the state of the
    metric is in sync with the index template in Elasticsearch.
* *Backwards-incompatible*: Remove `Metric.check_index_template_exists`.
    Use `Metric.check_index_template` instead.

Bug fixes:

* Fix bug where different `Metric` subclasses were sharing the same
    index settings (incl. mappings).

Other changes:

* *Backwards-incompatible*: Rename `Metric.create_index_template` to
    `Metric.sync_index_template`.

## 3.2.0 (2018-08-30)

Features:

* Add `check_metrics` command.

## 3.1.0 (2018-08-29)

Features:

* Make `Metric.timestamp` required.

## 3.0.0 (2018-08-29)

Features:

* Add `Metric.record`.

Other changes:

* *Backwards-incompatible*: Remove `date` parameter from `Metric.save`.

## 2.1.0 (2018-08-23)

Features:

* Add `post_index_template_create` signal.
* Add `--connection` argument to `sync_metrics`.
* Make `show_metrics` output more consistent with `sync_metrics`.

## 2.0.0 (2018-08-22)

Features:

* *Backwards-incompatible*: By default, `Metric.search`, `Metric.get`, and `Metric.mget` will use
    the metric's template pattern as the default index (e.g.  `myapp_mymetric-*`).
* Add `date` parameter to `Metric.save`.
* Add optional factory_boy integration in `elasticsearch_metrics.factory`.

## 1.0.1 (2018-08-22)

Bug fixes:

* Include management/ folder in distribution.

## 1.0.0 (2018-08-21)

* First release.
