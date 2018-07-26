from django.utils import timezone
from django.utils.six import add_metaclass
from elasticsearch_dsl import Document, Date, IndexTemplate
from elasticsearch_dsl.document import IndexMeta, MetaField
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


@add_metaclass(MetricMeta)
class BaseMetric(object):
    timestamp = Date(doc_values=True)

    class Meta:
        all = MetaField(enabled=False)
        source = MetaField(enabled=False)

    @classmethod
    def create_index_template(cls):
        index_template = cls.get_index_template()
        index_template.document(cls)
        pre_index_template_create.send(cls, index_template=index_template)
        index_template.save()
        return index_template

    @classmethod
    def get_index_template(cls):
        # TODO: mapping
        return IndexTemplate(name=cls._template_name, template=cls._template)

    @classmethod
    def get_index_name(cls, date=None):
        date = date or timezone.now().date()
        # TODO: Make dateformat configurable
        dateformat = "%Y.%m.%d"
        date_formatted = date.strftime(dateformat)
        return "{}-{}".format(cls._template_name, date_formatted)


class Metric(Document, BaseMetric):
    pass
