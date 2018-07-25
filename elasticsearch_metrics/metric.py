from django.utils import timezone
from django.utils.six import add_metaclass
from elasticsearch_dsl import Document, Date, IndexTemplate
from elasticsearch_dsl.document import DocumentMeta, DocumentOptions


class MetricOptions(DocumentOptions):
    """Adds template_name and template to
    available options.
    """

    def __init__(self, name, bases, attrs):
        meta = attrs.get("Meta", None)
        super(MetricOptions, self).__init__(name, bases, attrs)
        # TODO: Automatically comput template_name and template intead of defaulting to None
        self.template_name = getattr(meta, "template_name", None)
        self.template = getattr(meta, "template", None)


class MetricMeta(DocumentMeta):
    """Metaclass for the base `Metric` class."""

    def __new__(cls, name, bases, attrs):
        attrs["_doc_type"] = MetricOptions(name, bases, attrs)
        # We can't call super because DocumentMeta.__new__ instantiates DocumentOptions,
        # which pops off Meta, which we want to read from in
        # MetricOptions.
        return type.__new__(cls, name, bases, attrs)


# Python only allows for one metaclass to be selected.
# Create a metaclass that is the subclass of both DocumentMeta and MetricMeta
# https://stackoverflow.com/questions/38403795/python-metaclass-conflict-type-error/38404006#38404006
MetricMeta = type("MetricMeta", (type(Document), MetricMeta), {})


@add_metaclass(MetricMeta)
class Metric(Document):
    timestamp = Date()

    @classmethod
    def create_index_template(cls):
        pass

    @classmethod
    def get_index_template(cls):
        # TODO: mapping
        return IndexTemplate(
            name=cls._doc_type.template_name, template=cls._doc_type.template
        )

    @classmethod
    def get_index_name(cls, date=None):
        date = date or timezone.now().date()
        # TODO: Make dateformat configurable
        dateformat = "%Y.%m.%d"
        date_formatted = date.strftime(dateformat)
        return "{}-{}".format(cls._doc_type.template_name, date_formatted)
