import datetime as dt

from django.conf import settings
from django.utils import timezone
from django.utils.six import add_metaclass
from elasticsearch_dsl import Document, Date
from elasticsearch_dsl.document import IndexMeta, MetaField, Index
from elasticsearch_metrics.signals import pre_index_template_create


class MetricMeta(IndexMeta):
    """Metaclass for the base `Metric` class."""

    def __new__(mcls, name, bases, attrs):  # noqa: B902
        meta = attrs.get("Meta", None)
        new_cls = super(MetricMeta, mcls).__new__(mcls, name, bases, attrs)
        # TODO: Automatically compute template_name and template instead of defaulting to None
        new_cls._template_name = getattr(meta, "template_name", None)
        new_cls._template = getattr(meta, "template", None)
        return new_cls


# We need this intermediate BaseMetric class so that
# we can run MetricMeta ahead of IndexMeta
@add_metaclass(MetricMeta)
class BaseMetric(object):
    """Base metric class with which to define custom metric classes.

    Example usage:

    .. code-block:: python

        from elasticsearch_metrics import Metric

        class PageView(Metric):
            user_id = Integer()

            class Index:
                settings = {
                    "number_of_shards": 2,
                    "refresh_interval": "5s",
                }
    """

    timestamp = Date(doc_values=True)

    class Meta:
        all = MetaField(enabled=False)
        source = MetaField(enabled=False)

    @classmethod
    def create_index_template(cls):
        """Create an index template for this metric in Elasticsearch."""
        index_template = cls.get_index_template()
        index_template.document(cls)
        pre_index_template_create.send(cls, index_template=index_template)
        index_template.save()
        return index_template

    @classmethod
    def create_index(cls):
        index_name = cls.get_index_name()
        index = Index(index_name)
        index.create()
        return index

    @classmethod
    def get_index_template(cls):
        """Return an `IndexTemplate <elasticsearch_dsl.IndexTemplate>` for this metric."""
        return cls._index.as_template(
            template_name=cls._template_name, pattern=cls._template
        )

    @classmethod
    def get_index_name(cls, date=None):
        date = date or timezone.now().date()
        dateformat = settings.DATE_FORMAT
        date_formatted = date.strftime(dateformat)
        return "{}-{}".format(cls._template_name, date_formatted)


class Metric(Document, BaseMetric):
    __doc__ = BaseMetric.__doc__

    def save(self, using=None, index=None, validate=True, **kwargs):
        self.timestamp = dt.datetime.now()
        if not index:
            index = self.get_index_name()

        return super(Metric, self).save(
            using=using, index=index, validate=validate, **kwargs
        )
