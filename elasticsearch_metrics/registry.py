import collections
import dataclasses
import functools
import importlib
import typing
import weakref

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from elasticsearch_metrics.protocols import (
    ProtoDjelmeBackend,
    ProtoDjelmeRecord,
    ProtoDjelmeImp,
)
from elasticsearch_metrics.util.django import find_app_label_for_module
from elasticsearch_metrics.util.timeseries_naming import format_namepart

__all__ = ("djelme_registry",)

_BACKENDS_SETTING = "DJELME_BACKENDS"


@dataclasses.dataclass
class _DjelmeRegistry:
    """_DjelmeRegistry keeps track of configured backends and record types (similar to how
    django.apps.registry.Apps keeps track of Model classes).

    Meant to be treated as a singleton -- use the instance at `djelme_registry`.

    Imps should call `djelme_registry.register_recordtype` whenever a non-abstract
    record-type class is defined.

    `djelme_registry.register_backend` should be called based on settings
    """

    # nested mapping from app labels => record-type names => record classes
    # (using weakref so if the class is destroyed, no longer registered)
    _all_recordtypes: collections.abc.MutableMapping[
        str, collections.abc.MutableMapping[str, type[ProtoDjelmeRecord]]
    ] = dataclasses.field(
        default_factory=lambda: collections.defaultdict(
            lambda: weakref.WeakValueDictionary[str, type]()
        )
    )
    _imp_by_recordtype: collections.abc.MutableMapping[type, str] = dataclasses.field(
        default_factory=lambda: weakref.WeakKeyDictionary[type, str]()
    )
    _default_backend_name_by_recordtype: collections.abc.MutableMapping[type, str] = (
        dataclasses.field(
            default_factory=lambda: weakref.WeakKeyDictionary[type, str]()
        )
    )

    # nested mapping from backend_name => imp_module_name => imp backend config dictionary
    # (note, only one imp module allowed per backend (for now))
    @functools.cached_property
    def all_backends(self) -> dict[str, dict[str, dict[str, str]]]:
        _backends_setting = getattr(settings, _BACKENDS_SETTING, {})
        _validate_backends_setting(_backends_setting)
        return _backends_setting

    ###
    # `register` methods: for adding items to the registry

    def register_recordtype(
        self,
        recordtype: type[ProtoDjelmeRecord],
        *,
        imp_module_name: str,
        app_label: str = "",
        default_backend: str = "",
    ) -> None:
        """Add a record type to the registry."""
        _app_label = app_label or find_app_label_for_module(recordtype.__module__)
        app_recordtypes = self._all_recordtypes[_app_label]
        recordtype_name = format_namepart(recordtype.__name__)
        if recordtype_name in app_recordtypes:
            # Raise an error for conflicting recordtype names (same behavior as apps.register_model)
            raise RuntimeError(
                f"Conflicting '{recordtype_name}' recordtypes in application "
                f"'{_app_label}': {app_recordtypes[recordtype_name]} and {recordtype}."
            )
        app_recordtypes[recordtype_name] = recordtype
        self._imp_by_recordtype[recordtype] = imp_module_name
        if default_backend and (default_backend != "default"):
            self._default_backend_name_by_recordtype[recordtype] = default_backend

    ###
    # `get` methods: for accessing specific items in the registry

    def get_recordtype(
        self, app_label: str, recordtype_name: str | None = None
    ) -> type:
        """Return the metric matching the given app_label and model_name.

        As a shortcut, app_label may be in the form <app_label>.<model_name>.

        model_name is case-insensitive.

        Raise LookupError if no application exists with this label, or no
        metric exists with this name in the application. Raise ValueError if
        called with a single argument that doesn't contain exactly one dot.
        """
        apps.check_apps_ready()

        if recordtype_name is None:
            app_label, recordtype_name = app_label.split(".")

        app_recordtypes = self._get_recordtypes_for_app(app_label)
        try:
            return app_recordtypes[format_namepart(recordtype_name)]
        except KeyError as e:
            raise LookupError(
                f"App '{app_label}' doesn't have a '{recordtype_name}' metric."
            ) from e

    def get_recordtype_app_label(self, recordtype: type) -> str | None:
        _each_matching_app_label = (
            _app_label
            for _app_label, _types in self._all_recordtypes.items()
            if _types.get(format_namepart(recordtype.__name__)) is recordtype
        )
        return next(_each_matching_app_label, None)

    def get_backend(self, backend_name: str) -> ProtoDjelmeBackend:
        _imp_module, _imp_kwargs = self._lookup_imp_module(backend_name)
        return _imp_module.djelme_backend(backend_name, _imp_kwargs)

    def get_imp_module(
        self, imp_module_name: str = "", *, backend_name: str = ""
    ) -> ProtoDjelmeImp:
        _to_import = imp_module_name
        if backend_name:
            assert not imp_module_name  # one or the other
            _registered_module_name, _ = self._lookup_backend(backend_name)
            _to_import = _registered_module_name
        return _import_imp_module(_to_import)

    def get_backend_for_recordtype(
        self, recordtype: type[ProtoDjelmeRecord]
    ) -> ProtoDjelmeBackend:
        return self.get_backend(self.get_backend_name_for_recordtype(recordtype))

    def get_backend_name_for_recordtype(
        self, recordtype: type[ProtoDjelmeRecord]
    ) -> str:
        _backend_name = self._default_backend_name_by_recordtype.get(recordtype)
        if _backend_name:
            return _backend_name
        _imp_name = self._imp_by_recordtype.get(recordtype)
        if not _imp_name:
            raise LookupError(f"no imp for recordtype {recordtype!r}?")
        _each_backend_name = self.each_backend_name(imp_module_name=_imp_name)
        try:
            (_backend_name,) = _each_backend_name
        except StopIteration as _e:  # no backends
            raise LookupError(f"no backends for recordtype {recordtype!r}") from _e
        except ValueError as _e:  # too many backends
            raise LookupError(
                f"more than one backend for recordtype {recordtype!r}, must be set explicitly"
            ) from _e
        return _backend_name

    ###
    # `each` methods: for iterating over each registered

    def each_recordtype(
        self,
        *,
        app_label: str = "",
    ) -> collections.abc.Iterator[type[ProtoDjelmeRecord]]:
        """Iterate registered metric classes, optionally filtered on an app_label"""
        apps.check_apps_ready()  # ensure django setup done
        _app_labels = [app_label] if app_label else self._all_recordtypes.keys()
        for _app_label in _app_labels:
            yield from self._get_recordtypes_for_app(_app_label).values()

    def each_backend_settings(
        self,
    ) -> collections.abc.Iterator[tuple[str, str, dict[str, typing.Any]]]:
        for _backend_name, _imp_config in self.all_backends.items():
            if _imp_config:
                _imp_module_name, _imp_kwargs = next(iter(_imp_config.items()))
                yield (_backend_name, _imp_module_name, _imp_kwargs)

    def each_backend_name(
        self,
        *,
        imp_module_name: str = "",
    ) -> collections.abc.Iterator[str]:
        for _backend_name, _imp_config in self.all_backends.items():
            if (not imp_module_name) or (imp_module_name in _imp_config):
                yield _backend_name

    def each_backend(
        self,
        *,
        imp_module_name: str = "",
    ) -> collections.abc.Iterator[ProtoDjelmeBackend]:
        for _backend_name in self.each_backend_name(imp_module_name=imp_module_name):
            yield self.get_backend(_backend_name)

    def each_app_label(self) -> collections.abc.Iterable[str]:
        yield from self._all_recordtypes.keys()

    def recordtypes_by_backend(
        self, app_label: str = ""
    ) -> dict[str, collections.abc.Iterable[type[ProtoDjelmeRecord]]]:
        apps.check_apps_ready()  # ensure django setup done
        _by_backend_name: dict[str, list[type[ProtoDjelmeRecord]]] = {}
        _app_labels = [app_label] if app_label else self._all_recordtypes.keys()
        for _app_label in _app_labels:
            for _recordtype in self._get_recordtypes_for_app(_app_label).values():
                _backend_name = self.get_backend_name_for_recordtype(_recordtype)
                _by_backend_name.setdefault(_backend_name, []).append(_recordtype)
        return _by_backend_name

    ###
    # private methods

    def _lookup_backend(self, backend_name: str) -> tuple[str, dict[str, str]]:
        try:
            _backend_settings = self.all_backends[backend_name]
        except KeyError as _e:
            raise LookupError(f"unknown imp {backend_name!r}") from _e
        assert len(_backend_settings) == 1
        ((_imp_module_name, _imp_kwargs),) = _backend_settings.items()
        return (_imp_module_name, _imp_kwargs)

    def _lookup_imp_module(
        self, backend_name: str
    ) -> tuple[ProtoDjelmeImp, dict[str, str]]:
        _imp_module_name, _imp_kwargs = self._lookup_backend(backend_name)
        return (_import_imp_module(_imp_module_name), _imp_kwargs)

    def _get_recordtypes_for_app(
        self, app_label: str
    ) -> collections.abc.Mapping[str, type]:
        if app_label not in self._all_recordtypes:
            raise LookupError(f"No recordtypes found in app with label '{app_label}'.")
        return self._all_recordtypes[app_label]


def _import_imp_module(imp_module_name: str) -> ProtoDjelmeImp:
    try:
        _imp_module = importlib.import_module(imp_module_name)
    except ImportError as _error:
        raise ValueError(f"could not import {imp_module_name!r}") from _error
    assert isinstance(_imp_module, ProtoDjelmeImp)
    return _imp_module


def _validate_backends_setting(backends_setting):
    for _backend_name, _backend_imps in getattr(
        settings, _BACKENDS_SETTING, {}
    ).items():
        if len(_backend_imps) > 1:
            raise ImproperlyConfigured(
                _BACKENDS_SETTING, "only one imp per backend, at the moment"
            )
        for _imp_module_name, _imp_kwargs in _backend_imps.items():
            if not (
                isinstance(_imp_module_name, str)
                and isinstance(_imp_kwargs, dict)
                and all(isinstance(_k, str) for _k in _imp_kwargs.keys())
            ):
                raise ImproperlyConfigured(
                    _BACKENDS_SETTING,
                    'expected {"mybackend": {"imp.path": {"imp_config": "..."}}}',
                )


###
# module public api

djelme_registry = _DjelmeRegistry()
registry = djelme_registry  # back-compat synonym?
