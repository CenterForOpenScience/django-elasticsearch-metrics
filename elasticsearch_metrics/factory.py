"""factory_boy extension for elasticsearch_metrics."""
from __future__ import absolute_import
from factory import base


class MetricFactory(base.Factory):
    """Factory for Metric objects."""

    class Meta:
        abstract = True

    @classmethod
    def _build(cls, model_class, *args, **kwargs):
        return model_class(*args, **kwargs)

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        instance = model_class(*args, **kwargs)
        instance.save()
        return instance
