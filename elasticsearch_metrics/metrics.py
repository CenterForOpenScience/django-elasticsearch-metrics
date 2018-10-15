from django.apps import apps
from django.conf import settings
from django.utils import timezone
from django.utils.six import add_metaclass
from elasticsearch.exceptions import NotFoundError
from elasticsearch_dsl import Document, connections, Index
from elasticsearch_dsl.document import IndexMeta, MetaField
from elasticsearch_dsl.index import DEFAULT_INDEX

from elasticsearch_metrics import signals
from elasticsearch_metrics import exceptions
from elasticsearch_metrics.registry import registry

# Fields should be imported from this module
from elasticsearch_metrics.field import *  # noqa: F40
from elasticsearch_metrics.field import Date

DEFAULT_DATE_FORMAT = "%Y.%m.%d"


class MetricMeta(IndexMeta):
    """Metaclass for the base `Metric` class."""

    def __new__(mcls, name, bases, attrs):  # noqa: B902

        meta = attrs.get("Meta", None)
        module = attrs.get("__module__")

        new_cls = super(MetricMeta, mcls).__new__(mcls, name, bases, attrs)
        # Also ensure initialization is only performed for subclasses of Metric
        # (excluding Metric class itself).
        if not any(
            b for b in bases if isinstance(b, MetricMeta) and b is not BaseMetric
        ):
            return new_cls

        template_name = getattr(meta, "template_name", None)
        template = getattr(meta, "template", None)
        abstract = getattr(meta, "abstract", False)

        app_label = getattr(meta, "app_label", None)
        # Look for an application configuration to attach the model to.
        app_config = apps.get_containing_app_config(module)
        if app_label is None:
            if app_config is None:
                if not abstract:
                    raise RuntimeError(
                        "Metric class %s.%s doesn't declare an explicit "
                        "app_label and isn't in an application in "
                        "INSTALLED_APPS." % (module, name)
                    )
            else:
                app_label = app_config.label

        if not template_name or not template:
            metric_name = new_cls.__name__.lower()
            # If template_name not specified in class Meta,
            # compute it as <app label>_<lowercased class name>
            if not template_name:
                template_name = "{}_{}".format(app_label, metric_name)
            # template is <app label>_<lowercased class name>-*
            template = template or "{}_{}-*".format(app_label, metric_name)

        new_cls._template_name = template_name
        new_cls._template = template
        # Abstract base metrics can't be instantiated and don't appear in
        # the list of metrics for an app.
        if not abstract:
            registry.register(app_label, new_cls)
        return new_cls

    # Override IndexMeta.construct_index so that
    # a new Index is created for every metric class
    @classmethod
    def construct_index(cls, opts, bases):
        i = None
        if opts is None:
            # Inherit Index from base classes
            for b in bases:
                if getattr(b, "_index", DEFAULT_INDEX) is not DEFAULT_INDEX:
                    parent_index = b._index
                    i = Index(
                        parent_index._name,
                        doc_type=parent_index._mapping.doc_type,
                        using=parent_index._using,
                    )
                    i._settings = parent_index._settings.copy()
                    i._aliases = parent_index._aliases.copy()
                    i._analysis = parent_index._analysis.copy()
                    i._doc_types = parent_index._doc_types[:]
                    break
        if i is None:
            i = Index(
                getattr(opts, "name", "*"),
                doc_type=getattr(opts, "doc_type", "doc"),
                using=getattr(opts, "using", "default"),
            )
        i.settings(**getattr(opts, "settings", {}))
        i.aliases(**getattr(opts, "aliases", {}))
        for a in getattr(opts, "analyzers", ()):
            i.analyzer(a)
        return i


# We need this intermediate BaseMetric class so that
# we can run MetricMeta ahead of IndexMeta
@add_metaclass(MetricMeta)
class BaseMetric(object):
    """Base metric class with which to define custom metric classes.

    Example usage:

    .. code-block:: python

        from elasticsearch_metrics import metrics

        class PageView(metrics.Metric):
            user_id = metrics.Integer()

            class Index:
                settings = {
                    "number_of_shards": 2,
                    "refresh_interval": "5s",
                }
    """

    timestamp = Date(doc_values=True, required=True)

    class Meta:
        source = MetaField(enabled=False)

    @classmethod
    def sync_index_template(cls, using=None):
        """Sync the index template for this metric in Elasticsearch."""
        index_template = cls.get_index_template()
        index_template.document(cls)
        signals.pre_index_template_create.send(
            cls, index_template=index_template, using=using
        )
        index_template.save(using=using)
        signals.post_index_template_create.send(
            cls, index_template=index_template, using=using
        )
        return index_template

    @classmethod
    def check_index_template(cls, using=None):
        """Check if class is in sync with index template in Elasticsearch.

        :raise: IndexTemplateNotFoundError if index template does not exist.
        :raise: IndexTemplateOutOfSyncError if mappings, settings, or index patterns
            are out of sync.
        :return: True if index template exsits and mappings, settings, and index patterns
            are in sync.
        """
        client = connections.get_connection(using or "default")
        try:
            template = client.indices.get_template(cls._template_name)
        except NotFoundError as client_error:
            template_name = cls._template_name
            metric_name = cls.__name__
            raise exceptions.IndexTemplateNotFoundError(
                "{template_name} does not exist for {metric_name}".format(**locals()),
                client_error=client_error,
            )
        else:
            current_data = list(template.values())[0]
            template_data = cls.get_index_template().to_dict()

            mappings_in_sync = current_data["mappings"] == template_data["mappings"]
            if "settings" in current_data and "index" in current_data["settings"]:
                current_settings = current_data["settings"]["index"]
                template_settings = template_data.get("settings", {})
                # ES automatically casts number_of_shards and number_of_replicas to a string
                # so we need to cast before we compare
                # TODO: Are there other settings that need to be handled?
                number_settings = {"number_of_shards", "number_of_replicas"}
                for setting in number_settings:
                    if setting in template_settings:
                        template_settings[setting] = str(template_settings[setting])
                settings_in_sync = current_settings == template_settings
            else:
                settings_in_sync = True
            patterns_in_sync = (
                current_data["index_patterns"] == template_data["index_patterns"]
            )

            if not all([mappings_in_sync, settings_in_sync, patterns_in_sync]):
                template_name = cls._template_name
                metric_name = cls.__name__
                word_map = {
                    "mappings": mappings_in_sync,
                    "patterns": patterns_in_sync,
                    "settings": settings_in_sync,
                }
                out_of_sync = ", ".join(
                    [key for key, value in word_map.items() if not value]
                )
                raise exceptions.IndexTemplateOutOfSyncError(
                    "{template_name} is out of sync with {metric_name} ({out_of_sync})".format(
                        **locals()
                    ),
                    mappings_in_sync=mappings_in_sync,
                    patterns_in_sync=patterns_in_sync,
                    settings_in_sync=settings_in_sync,
                )
            return True

    @classmethod
    def get_index_template(cls):
        """Return an `IndexTemplate <elasticsearch_dsl.IndexTemplate>` for this metric."""
        return cls._index.as_template(
            template_name=cls._template_name, pattern=cls._template
        )

    @classmethod
    def get_index_name(cls, date=None):
        date = date or timezone.now().date()
        dateformat = getattr(
            settings, "ELASTICSEARCH_METRICS_DATE_FORMAT", DEFAULT_DATE_FORMAT
        )
        date_formatted = date.strftime(dateformat)
        return "{}-{}".format(cls._template_name, date_formatted)

    @classmethod
    def record(cls, timestamp=None, **kwargs):
        """Persist a metric in Elasticsearch.

        :param datetime timestamp: Timestamp for the metric.
        """
        instance = cls(timestamp=timestamp, **kwargs)
        index = cls.get_index_name(timestamp)
        instance.save(index=index)
        return instance


class Metric(Document, BaseMetric):
    __doc__ = BaseMetric.__doc__

    @classmethod
    def init(cls, index=None, using=None):
        """Create the index and populate the mappings in elasticsearch."""
        return super(Metric, cls).init(index=index or cls.get_index_name(), using=using)

    def save(self, using=None, index=None, validate=True, **kwargs):
        """Same as `Document.save`, except will save into the index determined
        by the metric's timestamp field.
        """
        self.timestamp = self.timestamp or timezone.now()
        if not index:
            index = self.get_index_name(date=self.timestamp)

        cls = self.__class__
        signals.pre_save.send(cls, instance=self, using=using, index=index)
        ret = super(Metric, self).save(
            using=using, index=index, validate=validate, **kwargs
        )
        signals.post_save.send(cls, instance=self, using=using, index=index)
        return ret

    @classmethod
    def _default_index(cls, index=None):
        """Overrides Document._default_index so that .search, .get, etc.
        use the metric's template pattern as the default index
        """
        return index or cls._template
