from django.utils import timezone
from django.utils.six import add_metaclass
from elasticsearch_dsl import Document, Date, IndexTemplate
from elasticsearch_dsl.document import IndexMeta, MetaField


class MetricMeta(IndexMeta):
    """Metaclass for the base `Metric` class."""

    def __new__(mcls, name, bases, attrs):  # noqa: B902
        meta = attrs.get("Meta", None)
        new_cls = type.__new__(mcls, name, bases, attrs)
        # TODO: Automatically compute template_name and template instead of defaulting to None
        new_cls._template_name = getattr(meta, "template_name", None)
        new_cls._template = getattr(meta, "template", None)
        return new_cls


@add_metaclass(MetricMeta)
class Metric(Document):
    timestamp = Date(doc_values=True)

    class Meta:
        dynamic_templates = MetaField(
            [
                {
                    "strings": {
                        "match": "*",
                        "match_mapping_type": "string",
                        "mapping": {
                            "type": "string",
                            "fielddata": {"format": "doc_values"},
                            "doc_values": True,
                            "index": "not_analyzed",
                        },
                    }
                }
            ]
        )
        all = MetaField(enabled=False)
        source = MetaField(enabled=False)

    @classmethod
    def create_index_template(cls):
        index_template = cls.get_index_template()
        index_template.settings(refresh_interval="5s")
        index_template.document(cls)
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
