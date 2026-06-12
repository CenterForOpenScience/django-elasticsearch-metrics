"""elasticsearch_metrics.imps.elastic6: store events and reports in elasticsearch 6

consider this code frozen/deprecated -- will be removed once no longer needed
"""

from __future__ import annotations
import collections
from collections.abc import Iterator
import dataclasses
import datetime
import functools
import logging

from django.apps import apps
from django.conf import settings
from django.utils import timezone
from elasticsearch6.exceptions import NotFoundError
from elasticsearch6_dsl import Document, connections, Date
from elasticsearch6_dsl.document import IndexMeta, MetaField
from elasticsearch6_dsl.index import Index

# re-export all fields, for back-compat convenience
from elasticsearch6_dsl.field import *  # noqa: F40

from elasticsearch_metrics import signals
from elasticsearch_metrics import exceptions
from elasticsearch_metrics.protocols import ProtoDjelmeBackend
from elasticsearch_metrics.registry import djelme_registry

DEFAULT_DATE_FORMAT = "%Y.%m.%d"

logger = logging.getLogger(__name__)


class ReadonlyAttrMap:
    def __init__(self, inner_obj):
        self.__inner_obj = inner_obj

    def __getitem__(self, key):
        try:
            return getattr(self.__inner_obj, key)
        except AttributeError as e:
            raise KeyError(key) from e

    def __contains__(self, key):
        return hasattr(self.__inner_obj, key)

    def __setitem__(self, key, value):
        """implement __setitem__ to appease MutableMapping type on ChainMap -- does nothing"""


def _get_default_using():
    """get the elasticsearch-dsl connection name to use"""
    _available_backends = djelme_registry.each_backend_name(imp_module_name=__name__)
    try:
        (_backend_name,) = _available_backends
    except ValueError:
        logger.warning(f"no djelme backends configured using imp module {__name__!r}!")
        return None
    return _backend_name


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
        assert isinstance(app_label, str)

        if not template_name:
            metric_name = new_cls.__name__.lower()
            # If template_name not specified in class Meta,
            # compute it as <app label>_<lowercased class name>
            template_name = f"{app_label}_{metric_name}"

        new_cls.__template_name = template_name
        new_cls.__template_pattern = f"{template_name}_*"  # template pattern
        # Abstract base metrics can't be instantiated and don't appear in
        # the list of metrics for an app.
        if not abstract:
            djelme_registry.register_recordtype(
                new_cls,
                imp_module_name=__name__,
                app_label=app_label,
                default_backend=new_cls._index._using or "",
            )
        return new_cls

    # Override IndexMeta.construct_index so that
    # a new Index is created for every metric class
    # and Index attrs are inherited
    @classmethod
    def construct_index(cls, opts, bases):
        parent_configs = [
            base._index.to_dict() for base in bases if hasattr(base, "_index")
        ]
        if opts:
            index_config = collections.ChainMap(ReadonlyAttrMap(opts), *parent_configs)  # type: ignore[arg-type]
        else:
            index_config = collections.ChainMap(*parent_configs)

        i = Index(
            index_config.get("name", "*"),
            using=index_config.get("using", _get_default_using()),
        )
        i.settings(**index_config.get("settings", {}))
        i.aliases(**index_config.get("aliases", {}))
        for a in index_config.get("analyzers", ()):
            i.analyzer(a)
        return i

    @property
    def _template_name(self):
        _prefix = self.get_index_name_prefix()
        return f"{_prefix}{self.__template_name}"

    @property
    def _template_pattern(self):
        _prefix = self.get_index_name_prefix()
        return f"{_prefix}{self.__template_pattern}"


# We need this intermediate BaseMetric class so that
# we can run MetricMeta ahead of IndexMeta
class BaseMetric(metaclass=MetricMeta):
    """Base metric class with which to define custom metric classes.

    Example usage:

    .. code-block:: python

        from elasticsearch_metrics import metrics


        class PageView(metrics.Metric):
            page_id = metrics.Integer(index=True, doc_values=True)

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
        index_template = cls.get_timeseries_index_template()
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
    def check_index_template(cls, using: str | None = None) -> None:
        """Check if class is in sync with index template in Elasticsearch.

        :raise: IndexTemplateNotFoundError if index template does not exist.
        :raise: IndexTemplateOutOfSyncError if mappings, settings, or index patterns
            are out of sync.
        :return: True if index template exsits and mappings, settings, and index patterns
            are in sync.
        """
        client = cls._get_connection(using=using)
        try:
            template = client.indices.get_template(cls._template_name)
        except NotFoundError as client_error:
            template_name = cls._template_name
            metric_name = cls.__name__
            raise exceptions.IndexTemplateNotFoundError(
                f"Index template {template_name!r} does not exist for {metric_name}",
                client_error=client_error,
            ) from client_error
        else:
            current_data = list(template.values())[0]
            template_data = cls.get_timeseries_index_template().to_dict()

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
                    f"Index template {template_name!r} is out of sync with {metric_name} ({out_of_sync})",
                    mappings_in_sync=mappings_in_sync,
                    patterns_in_sync=patterns_in_sync,
                    settings_in_sync=settings_in_sync,
                )

    @classmethod
    def check_djelme_setup(cls, using: str | None = None) -> None:
        cls.check_index_template(using)

    @classmethod
    @functools.cache
    def require_been_setup(cls, using: str | None = None) -> None:
        """check setup once -- raise on failure, remember success"""
        cls.check_djelme_setup(using)

    @classmethod
    def get_timeseries_index_template(cls):
        """Return an `IndexTemplate <elasticsearch_dsl.IndexTemplate>` for this metric."""
        return cls._index.as_template(
            template_name=cls._template_name, pattern=cls._template_pattern
        )

    @classmethod
    def get_index_name_prefix(cls) -> str:
        return ""

    @classmethod
    def get_index_name(cls, date: datetime.date | None = None) -> str:
        date = date or timezone.now().date()
        dateformat = getattr(
            settings, "ELASTICSEARCH_METRICS_DATE_FORMAT", DEFAULT_DATE_FORMAT
        )
        date_formatted = date.strftime(dateformat)
        return f"{cls._template_name}_{date_formatted}"


class Metric(Document, BaseMetric):
    __doc__ = BaseMetric.__doc__

    @classmethod
    def record(cls, timestamp=None, **kwargs):
        """Persist a metric in Elasticsearch.

        :param datetime timestamp: Timestamp for the metric.
        """
        instance = cls(timestamp=timestamp, **kwargs)
        index = cls.get_index_name(timestamp)
        instance.save(index=index)
        return instance

    @classmethod
    def init(cls, index=None, using=None):
        """Create the index and populate the mappings in elasticsearch.

        override Document.init to choose an index name
        """
        cls.sync_index_template(using=using)
        return super().init(index=index or cls.get_index_name(), using=using)

    def save(self, using=None, index=None, validate=True, **kwargs):
        """Same as `Document.save`, except will save into the index determined
        by the metric's timestamp field.
        """
        self.require_been_setup(using=using)  # prevent automapped indexes
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

    def djelme_index_name(self) -> str:  # for ProtoDjelmeRecord
        assert self.timestamp is not None
        return self.get_index_name(self.timestamp)

    @classmethod
    def _default_index(cls, index=None):
        """Overrides Document._default_index so that .search, .get, etc.
        use the metric's template pattern as the default index
        """
        return index or cls._template_pattern

    @classmethod
    def _get_using(cls, using=None):
        """get the elasticsearch6_dsl connection name to use

        overrides elasticsearch6.Document._get_using to allow
        getting connection name from a djelme imp and default
        to the first configured imp that uses this imp module
        """
        _backend = None
        if using in (None, "default"):
            return _get_default_using()
        elif isinstance(using, str) and (using in djelme_registry.all_backends):
            _backend = djelme_registry.get_backend(using)
            assert isinstance(_backend, DjelmeElastic6Backend)
            return _backend.backend_name
        return super()._get_using(using)


@dataclasses.dataclass
class DjelmeElastic6Backend:
    """DjelmeElastic6Backend: the elastic6 implementation of djelme (for use by generic djelme code)"""

    backend_name: str
    imp_kwargs: dict[str, str]

    @property
    def elastic_client(self):
        # assumes `connections.configure` was already called
        return connections.get_connection(self.backend_name)

    def djelme_backend_name(self) -> str:  # for ProtoDjelmeBackend
        return self.backend_name

    def djelme_imp_kwargs(self) -> dict[str, str]:  # for ProtoDjelmeBackend
        return self.imp_kwargs

    def djelme_setup(self, recordtypes: collections.abc.Iterable[type]) -> None:
        for _metric_type in recordtypes:
            assert issubclass(_metric_type, Metric)
            logger.info("setting up %r", _metric_type)
            _metric_type.init(using=self.backend_name)

    def djelme_teardown(self, recordtypes: collections.abc.Iterable[type]) -> None:
        for _metric_type in recordtypes:
            assert issubclass(_metric_type, Metric)
            logger.info("tearing down %r", _metric_type)
            _indexname_wildcard = _metric_type._template_pattern
            _templatename = _metric_type._template_name
            _client = self.elastic_client
            _client.indices.delete(index=_indexname_wildcard)
            try:
                _client.indices.delete_template(_templatename)
            except NotFoundError:
                pass


djelme_backend = DjelmeElastic6Backend  # for ProtoDjelmeImp


def djelme_when_ready(  # for ProtoDjelmeImp
    backends: Iterator[ProtoDjelmeBackend],
) -> None:
    connections.configure(
        **{
            _backend.djelme_backend_name(): _backend.djelme_imp_kwargs()
            for _backend in backends
        }
    )
