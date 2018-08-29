# Changelog

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
