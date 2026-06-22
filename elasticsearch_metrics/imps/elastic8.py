"""elasticsearch_metrics.elastic8: store events and reports in elasticsearch 8

>>> from elasticsearch_metrics.imps.elastic8 import EventRecord
>>> class TheThingHappened(EventRecord):
...     intensity: int
...
...     class Index:  # elasticsearch index settings
...         settings = {
...             "number_of_shards": 2,
...             "refresh_interval": "5s",
...         }
"""

__all__ = (
    "EventRecord",
    "CountedUsageRecord",
    "CyclicReport",
    # for ProtoDjelmeImp:
    "djelme_backend",
    "djelme_when_ready",
)
from collections import ChainMap
import collections.abc as cabc
import dataclasses
import datetime
import functools
import logging
import typing

from django.core.exceptions import ImproperlyConfigured
from django.conf import settings
from elasticsearch8.exceptions import NotFoundError
from elasticsearch8 import Elasticsearch as Elastic8Client
from elasticsearch8 import dsl as esdsl
from elasticsearch8.dsl._sync.document import IndexMeta

from elasticsearch_metrics import signals
from elasticsearch_metrics import exceptions
from elasticsearch_metrics.registry import djelme_registry
from elasticsearch_metrics.protocols import (
    ProtoDjelmeBackend,
    ProtoCountedUsage,
    ProtoDjelmeRecord,
)
from elasticsearch_metrics.util.timeseries_naming import (
    TimeseriesIndexNaming,
    TimeseriesRangePattern,
    format_template_name,
)
from elasticsearch_metrics.util.django import find_app_label_for_module
from elasticsearch_metrics.util.index_status import DjelmeIndexStatus
from elasticsearch_metrics.util.timeparts import (
    serialize_timeparts,
    TimepartStrat,
    GregorianTime,
    Timeparts,
    AbstractTimeparts,
)
from elasticsearch_metrics.util.anon_enough import opaque_key, opaque_sessionhour_id

logger = logging.getLogger(__name__)


_DEFAULT_TIMEDEPTH_SETTING = "DJELME_DEFAULT_TIMEDEPTH"
_DEFAULT_TIMEDEPTH = 3  # xxxx_xx_xx_ (daily)


def utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


###
# invasive hacky changes to elasticsearch8.dsl

# change default mapping for `str` annotations from Text to Keyword:
esdsl.document_base.DocumentOptions.type_annotation_map[str] = (esdsl.Keyword, {})
# change default timezone for `datetime` annotations from "local" to UTC:
esdsl.document_base.DocumentOptions.type_annotation_map[datetime.datetime] = (
    esdsl.Date,
    {"default_timezone": "UTC"},
)


# changes to document metaclass behavior
class _DjelmeRecordMetaclass(IndexMeta):
    """Metaclass for the base `BaseDjelmeRecord` class.

    extend elasticsearch-py's `IndexMeta` to:
    - belong to a django app (identified by `app_label` property)
    - register concrete types with elasticsearch_metrics.registry.djelme_registry
    - allow abstract record types (similar to django's abstract models, with `Meta.abstract`)
    """

    Meta: type

    def __new__(mcls, name, bases, attrs):  # noqa: B902
        """create a new BaseDjelmeRecord subclass

        extend elasticsearch-py's `IndexMeta.__new__` to:
        - register concrete types with elasticsearch_metrics.registry.djelme_registry
        - preserve a type's `class Meta` so it can hold additional custom config
        - inherit field defaults (bug workaround?)
        """
        # save `class Meta` to un-remove it later
        _cls_meta = attrs.get("Meta") or type("Meta", (), {})
        # call IndexMeta.__new__
        _cls = super().__new__(mcls, name, bases, attrs)
        assert isinstance(_cls, _DjelmeRecordMetaclass)
        # un-remove `class Meta` for later use
        if "Meta" in _cls.__dict__:
            for _attrname, _attrval in _cls_meta.__dict__.items():
                if not hasattr(_cls.Meta, _attrname):
                    setattr(_cls.Meta, _attrname, _attrval)
        else:  # guarantee non-inherited Meta
            _cls.Meta = _cls_meta
        # workaround elasticsearch8.dsl inheriting only fields, not defaults
        for _b in bases:
            for _fieldname, _default in getattr(_b, "_defaults", {}).items():
                _cls._defaults.setdefault(_fieldname, _default)
        # and register concrete record types with the djelme registry
        if not _cls.is_abstract:
            assert issubclass(_cls, BaseDjelmeRecord)
            _given_using = _cls._index._using
            _default_backend = (
                _given_using
                if isinstance(_given_using, str)
                and (_given_using in djelme_registry.all_backends)
                else ""
            )
            djelme_registry.register_recordtype(
                _cls,
                imp_module_name=__name__,
                app_label=_cls._get_meta_attr("app_label", None),
                default_backend=_default_backend,
            )
        return _cls

    @classmethod
    def construct_index(cls, opts, bases):
        """
        Extend IndexMeta.construct_index so a new Index is created for each class
        and Index.settings, Index.analyzers, and Index.using are inherited
        (but not Index.name or Index.aliases)
        """
        _base_index_configs = ChainMap(
            *(base._index.to_dict() for base in bases if hasattr(base, "_index"))
        )
        _index_opts: typing.Any = opts or type("Index", (), {})
        if not hasattr(_index_opts, "settings") and (
            _inherited_settings := _base_index_configs.get("settings")
        ):
            _index_opts.settings = _inherited_settings
        if not hasattr(_index_opts, "analyzers") and (
            _inherited_analyzers := _base_index_configs.get("analyzers")
        ):
            _index_opts.analyzers = _inherited_analyzers
        if not hasattr(_index_opts, "using"):
            _inherited_using = _base_index_configs.get("using")
            if _inherited_using and (_inherited_using != "default"):
                _index_opts.using = _inherited_using
        assert _index_opts is not None  # guarantee separate index per class
        return super().construct_index(_index_opts, bases)

    def _get_meta_attr(self, attr_name: str, default: typing.Any = None) -> typing.Any:
        _meta = getattr(self, "Meta", None)
        return getattr(_meta, attr_name, default)

    @property
    def is_abstract(self) -> bool:
        return bool(self._get_meta_attr("abstract", False))

    @property
    def app_label(self) -> str:
        _app_label = djelme_registry.get_recordtype_app_label(self)
        assert _app_label
        return _app_label


class BaseDjelmeRecord(esdsl.Document, metaclass=_DjelmeRecordMetaclass):
    """a subclass of elasticsearch8.dsl.Document, with conveniences

    >>> class MyAbstractRecord(BaseDjelmeRecord):
    ...     foo: int
    ...     class Meta:
    ...         abstract = True
    ...         blargl = 5
    >>> MyAbstractRecord.Meta.blargl
    5
    >>> MyAbstractRecord.Meta.abstract
    True
    >>> MyAbstractRecord.is_abstract
    True

    >>> class MyConcreteRecord(MyAbstractRecord):
    ...     bar: int
    ...     class Meta:
    ...         bleg = 7
    >>> MyConcreteRecord.Meta.bleg
    7
    >>> MyConcreteRecord.is_abstract
    False
    >>> MyConcreteRecord.app_label
    'elasticsearch_metrics'
    """

    UNIQUE_TOGETHER_FIELDS: typing.ClassVar[cabc.Iterable[str]] = ()

    class Meta:
        abstract = True

    @classmethod
    def check_djelme_setup(cls, using: str | None = None) -> None:
        raise NotImplementedError  # expected on subclasses

    @classmethod
    def do_teardown(cls, es_client):
        raise NotImplementedError  # expected on subclasses

    @classmethod
    def record(
        cls,
        *,
        using: str | typing.Literal[False] | None = None,
        **kwargs: typing.Any,
    ) -> "typing.Self":  # typing.Self added in py 3.11 -- str annotation until 3.10 eol
        """Construct a record instance and save it in Elasticsearch.

        Keyword args:
        using -- name of the djelme backend or elasticsearch8.dsl connection
            to use to save, or `False` to skip saving (e.g. for use in a bulk operation)
        all other kwargs passed thru to the class constructor
        """
        assert not cls.is_abstract
        _instance = cls(**kwargs)
        if using is not False:
            _instance.save(using=using)
        return _instance

    @classmethod
    @functools.cache
    def require_been_setup(cls, using: str | None = None) -> None:
        """check setup once -- raise on failure, remember success"""
        cls.check_djelme_setup(using)

    @classmethod
    def get_index_name_prefix(cls) -> str:
        _name_prefix = (
            cls._get_meta_attr("index_name_prefix")
            or cls._get_djelme_backend().default_index_name_prefix
            or ""
        )
        assert isinstance(_name_prefix, str)
        return _name_prefix

    @classmethod
    def each_existing_index(
        cls, using: str | Elastic8Client | None = None
    ) -> cabc.Iterator[DjelmeIndexStatus]:
        raise NotImplementedError

    @classmethod
    def _get_djelme_backend(cls) -> "DjelmeElastic8Backend":
        _backend = djelme_registry.get_backend_for_recordtype(cls)
        assert isinstance(_backend, DjelmeElastic8Backend)
        return _backend

    @classmethod
    def _get_using(
        cls, using: str | Elastic8Client | None = None
    ) -> str | Elastic8Client:
        """get the elasticsearch8 connection name to use

        extend `elasticsearch8.dsl.Document._get_using` to:
        - recognize djelme backend names in `using` (given or configured)
        - if no `using` given or configured, find a djelme backend by imp module
        """
        _backend: ProtoDjelmeBackend | None = None
        if using in (None, "default"):
            _backend = cls._get_djelme_backend()
        elif isinstance(using, str) and (using in djelme_registry.all_backends):
            _backend = djelme_registry.get_backend(using)
        if _backend is not None:
            assert isinstance(_backend, DjelmeElastic8Backend)
            return _backend._elastic8dsl_connection_name
        return super()._get_using(using)

    def _get_index(self, index: str | None = None, required: bool = True) -> str | None:
        """get the index name for this record

        extend elasticsearch8.dsl's DocumentBase._get_index to default to djelme_index_name()
        """
        return super()._get_index(index or self.djelme_index_name(), required)

    def clean(self) -> None:
        """fill fields based on other fields, before saving

        extend elasticsearch8.dsl's DocumentBase.clean to use the djelme index name

        subclasses that need to autofill or transform fields should further extend this method
        """
        self._populate_unique_id()
        super().clean()

    def save(
        self,
        *,
        using: str | Elastic8Client | None = None,
        index: str | None = None,
        **kwargs: typing.Any,
    ) -> typing.Any:
        """save the record

        extend `elasticsearch8.dsl.Document.save` to:
        - populate document id based on UNIQUE_TOGETHER_FIELDS
        - send pre_save/post_save signals
        """
        assert not self.__class__.is_abstract
        self.require_been_setup(using=using)  # prevent automapped indexes
        signals.pre_save.send(self.__class__, instance=self, using=using, index=index)
        _saved = super().save(using=using, index=index, **kwargs)
        signals.post_save.send(self.__class__, instance=self, using=using, index=index)
        return _saved

    def _populate_unique_id(self) -> None:
        """
        Set a unique document id by hashing values of "unique together"
        fields for "ON CONFLICT UPDATE" behavior -- if the document
        already exists, it will be replaced rather than duplicated.
        Cannot detect/avoid conflicts this way, but that's ok.
        """
        _unique_together = self._get_unique_together_values()
        assert _unique_together or not self.UNIQUE_TOGETHER_FIELDS
        if _unique_together:
            # make it unique by setting doc id in elasticsearch
            self.meta.id = opaque_key(_unique_together)

    def _get_unique_together_values(self) -> list[typing.Any]:
        return [
            getattr(self, _field_name)
            for _field_name in (self.UNIQUE_TOGETHER_FIELDS or ())
        ]


class _SimpleRecordMetaclass(_DjelmeRecordMetaclass):
    @property
    def _index(self):
        if self.is_abstract:
            return self.__index
        # return a copy with `name` and `using` freshly computed
        try:
            _backend = self._get_djelme_backend()
        except LookupError:
            _using = None  # may not be registered yet, is ok
            _index_name = ""
        else:
            _using = _backend._elastic8dsl_connection_name
            _index_name = self.djelme_index_name()
        return self.__index.clone(name=_index_name, using=_using)

    @_index.setter
    def _index(self, val):
        # stash in a private attr so only the property getter can reach it
        self.__index = val


class SimpleRecord(BaseDjelmeRecord, metaclass=_SimpleRecordMetaclass):
    class Meta:
        abstract = True

    @classmethod
    def djelme_index_name(cls) -> str:
        """the index name for this record type

        for ProtoDjelmeRecord
        """
        assert not cls.is_abstract
        _app_label = find_app_label_for_module(cls.__module__)
        _index_name = f"{_app_label.lower()}_{cls.__name__.lower()}"
        _prefix = cls.get_index_name_prefix()
        if not _index_name.startswith(_prefix):
            _index_name = f"{_prefix}{_index_name}"
        return _index_name

    @classmethod
    def check_djelme_setup(cls, using: str | None = None) -> None:
        """Check if class is in sync with index mappings in Elasticsearch.

        :raise: IndexNotFoundError if index does not exist.
        :raise: IndexOutOfSyncError if mappings are out of sync.
        :return: if index exists and mappings are in sync.
        """
        assert not cls.is_abstract
        _client = cls._get_connection(using)
        _index_name = cls.djelme_index_name()
        try:
            _index_response = _client.indices.get(index=_index_name)
        except NotFoundError as client_error:
            raise exceptions.IndexNotFoundError(
                f"Index {_index_name} does not exist for {cls.__name__}",
                client_error=client_error,
            ) from client_error
        else:
            _current_mappings = _index_response[_index_name]["mappings"]
            _expected_mappings = cls._index.to_dict()["mappings"]
            if _current_mappings != _expected_mappings:
                raise exceptions.IndexOutOfSyncError(
                    f"Index {_index_name} has mappings out of sync with {cls.__name__}",
                )

    @classmethod
    def do_teardown(cls, es_client):
        assert not cls.is_abstract
        cls._index.delete(using=es_client, ignore_unavailable=True)

    @classmethod
    def each_existing_index(
        cls, using: str | Elastic8Client | None = None
    ) -> cabc.Iterator[DjelmeIndexStatus]:
        """yield existing index name, if any

        implement BaseDjelmeRecord.each_existing_index
        """
        _resp = cls._get_connection(using).indices.get(
            index=cls.djelme_index_name(), features=",", ignore_unavailable=True
        )
        for _index_name in _resp.keys():
            yield DjelmeIndexStatus(_index_name)

    @classmethod
    def refresh(cls, using: str | None = None) -> None:
        assert not cls.is_abstract
        cls._index.refresh(using=using)


class TimeseriesRecord(BaseDjelmeRecord):
    # the 'version' field type allows range queries on semver-like strings
    # that fit perfectly with "timeparts" representation of a UTC datetime
    # as a sequence of integers -- helps to avoid time zones and date math
    # (e.g. '2000' < '2000.5.10' < '2000.5.20.20.20' < '2000.11' < '2001')
    timeseries_timeparts: str = esdsl.mapped_field(esdsl.Version())

    class Meta:
        abstract = True

    ###
    # class methods

    @classmethod
    def init(cls, index=None, using=None) -> None:
        """Create an index template with mappings for timeseries indexes

        override `elasticsearch8.dsl.Document.init` to create a template instead of an index
        """
        assert not cls.is_abstract
        cls.sync_index_template(using=using)

    @classmethod
    def search(
        cls,
        using: str | Elastic8Client | None = None,
        index: str | None = None,
    ) -> esdsl.Search[
        "typing.Self"
    ]:  # typing.Self added in py 3.11 -- str annotation until 3.10 eol
        assert not cls.is_abstract
        return super().search(
            using=using,
            index=(index or cls.timeseries_index_wildcard()),
        )

    @classmethod
    def search_timeseries_range(
        cls,
        from_when: tuple[int, ...] | datetime.date,
        until_when: tuple[int, ...] | datetime.date,
    ) -> typing.Any:
        _index_pattern = cls.timeseries_index_range_pattern(from_when, until_when)
        _timeseries_q = esdsl.query.Range(
            timeseries_timeparts={
                "gte": serialize_timeparts(
                    cls.get_timepart_strat().get_timeparts(
                        from_when, pad=False, truncate=False
                    )
                ),
                "lt": serialize_timeparts(
                    cls.get_timepart_strat().get_timeparts(
                        until_when, pad=False, truncate=False
                    )
                ),
            }
        )
        return cls.search(index=_index_pattern).filter(_timeseries_q)

    @classmethod
    def refresh(cls, using: str | None = None) -> None:
        assert not cls.is_abstract
        cls._get_connection(using).indices.refresh(
            index=cls.timeseries_index_wildcard()
        )

    @classmethod
    def each_existing_index(
        cls, using: str | Elastic8Client | None = None
    ) -> cabc.Iterator[DjelmeIndexStatus]:
        """yield status for each existing index

        implement BaseDjelmeRecord.each_existing_index
        """
        _resp = cls._get_connection(using).indices.get(
            index=cls.timeseries_index_wildcard(),
        )
        _expired_if_before = (
            cls.get_timepart_strat().get_timeparts(utcnow() - _expiration_delta)
            if (_expiration_delta := cls.get_timeseries_index_expiration()) is not None
            else None
        )
        for _index_name in sorted(_resp.keys()):
            if _expired_if_before is None:
                _is_expired = False
            else:
                _parsed = cls.parse_timeseries_index_name(_index_name)
                _is_expired = bool(
                    _parsed.timeparts and (_parsed.timeparts < _expired_if_before)
                )
            yield DjelmeIndexStatus(_index_name, _is_expired)

    @classmethod
    def do_teardown(
        cls,
        using: str | Elastic8Client | None = None,
        *,
        keep_templates: bool = False,
    ) -> None:
        assert not cls.is_abstract
        _client = cls._get_connection(using)
        for _index_status in cls.each_existing_index(using=_client):
            cls.delete_index(_index_status.index_name, using=_client)
        if not keep_templates:
            _templatename = cls.get_timeseries_template_name()
            try:
                _client.indices.delete_index_template(name=_templatename)
            except NotFoundError:
                pass

    @classmethod
    def get_timeseries_template(cls) -> esdsl.ComposableIndexTemplate:
        assert not cls.is_abstract
        return cls._index.as_composable_template(
            template_name=cls.get_timeseries_template_name(),
            pattern=cls.timeseries_index_wildcard(),
        )

    @classmethod
    def get_timeseries_template_name(cls) -> str:
        _template_name = format_template_name(
            cls.app_label, cls.get_timeseries_recordtype_name()
        )
        return "".join((cls.get_index_name_prefix(), _template_name))

    @classmethod
    def get_timeseries_recordtype_name(cls) -> str:
        _recordtype_name = cls._get_meta_attr(
            "timeseries_recordtype_name", cls.__name__
        )
        assert isinstance(_recordtype_name, str)
        return _recordtype_name

    @classmethod
    def timeseries_index_naming(
        cls, timeparts: AbstractTimeparts | datetime.date | str
    ) -> TimeseriesIndexNaming:
        return TimeseriesIndexNaming(
            cls.app_label,
            cls.get_timeseries_recordtype_name(),
            timeparts,
            cls.get_timepart_strat(),
            prefix=cls.get_index_name_prefix(),
        )

    @classmethod
    def parse_timeseries_index_name(cls, index_name: str) -> TimeseriesIndexNaming:
        _parsed = TimeseriesIndexNaming.parse(
            index_name,
            timepart_strat=cls.get_timepart_strat(),
            prefix=cls.get_index_name_prefix(),
        )
        if (
            _parsed.app_label.lower() != cls.app_label.lower()
            or _parsed.recordtype.lower()
            != cls.get_timeseries_recordtype_name().lower()
        ):
            raise ValueError(f"index {index_name!r} does not belong to {cls}")
        return _parsed

    @classmethod
    def timeseries_index_wildcard(cls, timeparts: tuple[int, ...] = ()) -> str:
        _naming = cls.timeseries_index_naming(timeparts)
        return _naming.to_str(wildcard=True)

    @classmethod
    def timeseries_index_range_pattern(
        cls,
        from_when: tuple[int, ...] | datetime.date,
        until_when: tuple[int, ...] | datetime.date | None,
    ) -> str:
        return str(
            TimeseriesRangePattern(
                cls.app_label,
                cls.get_timeseries_recordtype_name(),
                from_when,
                until_when or utcnow(),
                cls.get_timepart_strat(),
                index_name_prefix=cls.get_index_name_prefix(),
            )
        )

    @classmethod
    def get_timeseries_index_timedepth(cls) -> int:
        _default_timedepth = getattr(
            settings, _DEFAULT_TIMEDEPTH_SETTING, _DEFAULT_TIMEDEPTH
        )
        _timedepth = cls._get_meta_attr(
            "timeseries_index_timedepth", _default_timedepth
        )
        assert isinstance(_timedepth, int)
        return _timedepth

    @classmethod
    def get_timepart_strat(cls) -> TimepartStrat:
        return GregorianTime(cls.get_timeseries_index_timedepth())

    @classmethod
    def _default_index(cls, index=None):
        """Overrides Document._default_index so that .search, .get, etc.
        use the metric's template pattern as the default index
        """
        assert not cls.is_abstract
        return index or cls.timeseries_index_wildcard()

    @classmethod
    def sync_index_template(cls, using=None):  # -> ComposableIndexTemplate:
        """Sync the index template for this metric in Elasticsearch."""
        assert not cls.is_abstract
        _template = cls.get_timeseries_template()
        signals.pre_index_template_create.send(
            cls, index_template=_template, using=using
        )
        _template.save(using=cls._get_using(using))
        signals.post_index_template_create.send(
            cls, index_template=_template, using=using
        )
        return _template

    @classmethod
    def check_djelme_setup(cls, using: str | Elastic8Client | None = None) -> None:
        """Check if class is in sync with index template in Elasticsearch.

        :raise: IndexTemplateNotFoundError if index template does not exist.
        :raise: IndexTemplateOutOfSyncError if mappings, settings, or index patterns
            are out of sync.
        :return: True if index template exists and mappings, settings, and index patterns
            are in sync.
        """
        client = cls._get_connection(using)
        try:
            _template_response = client.indices.get_index_template(
                name=cls.get_timeseries_template_name()
            )
        except NotFoundError as client_error:
            raise exceptions.IndexTemplateNotFoundError(
                f"{cls.get_timeseries_template_name()} does not exist for {cls.__name__}",
                client_error=client_error,
            ) from client_error
        else:
            (_current_index_dict,) = _template_response["index_templates"]
            assert _current_index_dict["name"] == cls.get_timeseries_template_name()
            _current_template = _current_index_dict["index_template"]["template"]
            _current_patterns = _current_index_dict["index_template"]["index_patterns"]
            _current_mappings = _current_template["mappings"]
            _current_settings = _current_template.get("settings", {}).get("index")
            _expected_template_dict = cls.get_timeseries_template().to_dict()
            _expected_template = _expected_template_dict["template"]
            _expected_patterns = _expected_template_dict["index_patterns"]
            _expected_mappings = _expected_template["mappings"]
            _expected_settings = _expected_template.get("settings")
            if _expected_settings:
                # ES automatically casts integer settings to string
                for _name, _val in list(_expected_settings.items()):
                    if isinstance(_val, int):
                        _expected_settings[_name] = str(_val)
            mappings_in_sync = _current_mappings == _expected_mappings
            settings_in_sync = _current_settings == _expected_settings
            patterns_in_sync = _current_patterns == _expected_patterns

            if not all([mappings_in_sync, settings_in_sync, patterns_in_sync]):
                word_map = {
                    "mappings": mappings_in_sync,
                    "patterns": patterns_in_sync,
                    "settings": settings_in_sync,
                }
                out_of_sync = ", ".join(
                    [key for key, value in word_map.items() if not value]
                )
                raise exceptions.IndexTemplateOutOfSyncError(
                    f"{cls.get_timeseries_template_name()} is out of sync with {cls.__name__} ({out_of_sync})",
                    mappings_in_sync=mappings_in_sync,
                    patterns_in_sync=patterns_in_sync,
                    settings_in_sync=settings_in_sync,
                )

    @classmethod
    def get_timeseries_index_expiration(cls) -> datetime.timedelta | None:
        _val = cls._get_meta_attr("timeseries_index_expiration")
        if not (_val is None or isinstance(_val, datetime.timedelta)):
            raise ImproperlyConfigured(
                "timeseries_index_expiration must be a timedelta", _val
            )
        return _val

    @classmethod
    def delete_index(
        cls,
        index_name: str,
        using: str | Elastic8Client | None = None,
    ) -> None:
        _client = cls._get_connection(using)
        _client.indices.delete(index=index_name)

    ###
    # instance methods

    def get_timeseries_timeparts(self) -> Timeparts:
        """semverlike string of timeparts, used to choose a timeseries index and for range queries"""
        raise NotImplementedError(
            f"{self.__class__!r} must implement get_timeseries_timeparts"
        )

    def djelme_index_name(self) -> str:
        """the index name for this record instance

        for ProtoDjelmeRecord
        """
        return str(self.timeseries_index_naming(self.get_timeseries_timeparts()))

    def clean(self) -> None:
        """save the record to a timeseries index

        extend `elasticsearch8.dsl.Document.save` to choose a specific timeseries index
        """
        super().clean()
        self.timeseries_timeparts = serialize_timeparts(self.get_timeseries_timeparts())


# class EventRecord(TimeseriesRecord, ProtoExpirableRecord?):
class EventRecord(TimeseriesRecord):
    timestamp: datetime.datetime = esdsl.mapped_field(default_factory=lambda: utcnow())

    class Meta:
        abstract = True

    def get_timeseries_timeparts(self) -> Timeparts:
        """semverlike string of timeparts, used to choose a timeseries index and for range queries

        for TimeseriesRecord
        """
        return self.get_timepart_strat().get_timeparts(self.timestamp, truncate=False)


# class CountedUsageRecord(EventRecord, ProtoCountedUsage):
class CountedUsageRecord(EventRecord):
    """
    fields correspond to defined terms from COUNTER
    https://cop5.projectcounter.org/en/5.0.2/appendices/a-glossary-of-terms.html
    """

    # for ProtoCountedUsage:
    platform_iri: str = esdsl.mapped_field(required=True, default="")
    database_iri: str = esdsl.mapped_field(required=True, default="")
    item_iri: str = esdsl.mapped_field(required=True, default="")
    sessionhour_id: str = esdsl.mapped_field(esdsl.Keyword(), default="")
    within_iris: list[str] = esdsl.mapped_field(esdsl.Keyword(), default_factory=list)

    class Meta:
        abstract = True

    @classmethod
    def record(
        cls,
        *,
        # each usage record needs a sessionhour_id -- for migrating old data, can set explicitly...
        sessionhour_id: str = "",
        # ...but when saving new data, give the dirty identifying strings
        # (which won't be stored, but used to create an opaque sessionhour_id)
        user_id: str = "",
        client_session_id: str = "",
        request_host: str = "",
        request_useragent: str = "",
        # additional kwargs presumed to give field values
        **kwargs: typing.Any,
    ) -> "typing.Self":  # typing.Self added in py 3.11 -- str annotation until 3.10 eol
        """CountedUsageRecord.record(...): construct and save a record"""
        _sessionhour_id = sessionhour_id or opaque_sessionhour_id(
            client_session_id=client_session_id,
            user_id=user_id,
            request_host=request_host,
            request_useragent=request_useragent,
            timestamp=kwargs.get("timestamp"),
        )
        _new_record = super().record(**kwargs, sessionhour_id=_sessionhour_id)
        assert isinstance(_new_record, cls)
        return _new_record


class CyclicReport(TimeseriesRecord):
    """CyclicReport: for recording something on a regular cycle"""

    UNIQUE_TOGETHER_FIELDS: typing.ClassVar[cabc.Iterable[str]] = ("cycle_coverage",)

    CYCLE_TIMEDEPTH: typing.ClassVar[int]  # required on subclasses

    cycle_coverage: str = esdsl.mapped_field(esdsl.Version())
    created: datetime.datetime = esdsl.mapped_field(default_factory=lambda: utcnow())

    class Meta:
        abstract = True

    def __init_subclass__(cls, **kwargs: typing.Any) -> None:
        super().__init_subclass__(**kwargs)
        if not cls.is_abstract:
            _cycle_timedepth = getattr(cls, "CYCLE_TIMEDEPTH", None)
            if not isinstance(_cycle_timedepth, int):
                raise ImproperlyConfigured(
                    f"expected CYCLE_TIMEDEPTH integer on {cls.__module__}.{cls.__qualname__}"
                )
            if "cycle_coverage" not in cls.UNIQUE_TOGETHER_FIELDS:
                raise ImproperlyConfigured(
                    f'CyclicReport subclasses must have "cycle_coverage" in UNIQUE_TOGETHER_FIELDS ({cls!r})'
                )

    @classmethod
    def get_cycle_timepart_strat(cls) -> TimepartStrat:
        return GregorianTime(cls.CYCLE_TIMEDEPTH)

    def clean(self) -> None:
        self.cycle_coverage = serialize_timeparts(
            self.get_cycle_timepart_strat().get_timeparts(self.cycle_coverage)
        )
        super().clean()

    def get_timeseries_timeparts(self) -> Timeparts:
        """semverlike string of timeparts, used to choose a timeseries index and for range queries

        for TimeseriesRecord

        mirror `cycle_coverage`; index by the start of the covered timespan
        """
        return self.get_timepart_strat().get_timeparts(
            self.cycle_coverage, truncate=False, pad=False
        )


@dataclasses.dataclass
class DjelmeElastic8Backend:
    """DjelmeElastic8Backend: elastic8 backend for djelme (for use by generic djelme code)"""

    _NON_PASSTHRU_KWARGS: typing.ClassVar[cabc.Collection[str]] = {
        "djelme_default_index_name_prefix",
    }

    backend_name: str
    imp_kwargs: dict[str, str]  # pass-through to elasticsearch connection kwargs

    def djelme_backend_name(self) -> str:  # for ProtoDjelmeBackend
        return self.backend_name

    def djelme_imp_kwargs(self) -> dict[str, str]:  # for ProtoDjelmeBackend
        return self.imp_kwargs

    @property
    def default_index_name_prefix(self) -> str:
        return self.imp_kwargs.get("djelme_default_index_name_prefix", "")

    @property
    def elastic_client(self) -> Elastic8Client:
        # assumes `connections.configure` was already called
        return esdsl.connections.get_connection(self._elastic8dsl_connection_name)

    @property
    def _elastic8dsl_connection_name(self) -> str:
        return self.backend_name

    @property
    def _elastic8dsl_connection_kwargs(self) -> dict[str, typing.Any]:
        return {
            _key: _val
            for _key, _val in self.imp_kwargs.items()
            if _key not in self._NON_PASSTHRU_KWARGS
        }

    def djelme_setup(self, recordtypes: cabc.Iterable[type]) -> None:
        # for ProtoDjelmeBackend
        for _recordtype in recordtypes:
            # TODO: logger.info
            assert issubclass(_recordtype, BaseDjelmeRecord)
            _recordtype.init(using=self._elastic8dsl_connection_name)

    def djelme_teardown(self, recordtypes: cabc.Iterable[type]) -> None:
        # for ProtoDjelmeBackend
        for _recordtype in recordtypes:
            assert issubclass(_recordtype, BaseDjelmeRecord)
            _recordtype.do_teardown(self.elastic_client)


if __debug__ and typing.TYPE_CHECKING:
    # for static type-checking; verify intent
    _: type[ProtoCountedUsage] = CountedUsageRecord
    __: type[ProtoDjelmeBackend] = DjelmeElastic8Backend
    ___: type[ProtoDjelmeRecord] = BaseDjelmeRecord

###
# names expected by ProtoDjelmeImp

djelme_backend = DjelmeElastic8Backend  # for ProtoDjelmeImp


def djelme_when_ready(  # for ProtoDjelmeImp
    backends: cabc.Iterable[ProtoDjelmeBackend],
) -> None:
    esdsl.connections.configure(
        **{
            _backend._elastic8dsl_connection_name: _backend._elastic8dsl_connection_kwargs
            for _backend in backends
            if isinstance(_backend, DjelmeElastic8Backend)
        }
    )
