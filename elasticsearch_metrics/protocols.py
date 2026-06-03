from __future__ import annotations
import collections
import datetime
import typing

from elasticsearch_metrics.util.index_status import DjelmeIndexStatus

__all__ = (
    "ProtoDjelmeBackend",
    "ProtoDjelmeImp",
)


@typing.runtime_checkable
class ProtoDjelmeImp(typing.Protocol):
    """ProtoDjelmeImp: required functions in a djelme imp(lamentation) module"""

    @staticmethod
    def djelme_backend(
        backend_name: str,
        imp_kwargs: dict[str, str],
    ) -> ProtoDjelmeBackend:
        """djelme_backend: impstantiate a djelme backend"""

    @staticmethod
    def djelme_when_ready(
        backends: collections.abc.Iterable[ProtoDjelmeBackend],
    ) -> None:
        """djelme_when_ready: called after all recordtypes are defined

        given each backend configured to use this imp"""


class ProtoDjelmeBackend(typing.Protocol):
    def djelme_backend_name(self) -> str: ...
    def djelme_imp_kwargs(self) -> dict[str, str]: ...
    def djelme_setup(self, recordtypes: collections.abc.Iterable[type]) -> None: ...
    def djelme_teardown(self, recordtypes: collections.abc.Iterable[type]) -> None: ...

    # def show_timeseries_indexes(self): ...
    # def record_timeseries_record(self, record_doc: ProtoDjelmeRecord) -> ...: ...
    # def check_timeseries_indexes(self): ...


class ProtoDjelmeRecord(typing.Protocol):
    @classmethod
    def record(
        cls, *, using: str | None = None, **kwargs: typing.Any
    ) -> "typing.Self":  # typing.Self added in py 3.11 -- str annotation until 3.10 eol
        ...

    @classmethod
    def check_djelme_setup(cls, using: str | None = None) -> None:
        """Check backend setup for this record type; raise helpful exceptions"""

    @classmethod
    def search_timeseries_range(
        cls,
        from_when: tuple[int, ...] | datetime.date,
        until_when: tuple[int, ...] | datetime.date,
        **kwargs: typing.Any,
    ) -> typing.Any: ...

    @classmethod
    def each_existing_index(
        cls, using: str | None = None
    ) -> collections.abc.Iterator[DjelmeIndexStatus]: ...

    # @classmethod
    # def each_timeseries_index_status(cls) -> collections.abc.Iterable[str]: ...

    def djelme_index_name(self) -> str: ...


###
# counter?


class ProtoCountedUsage(typing.Protocol):
    """
    fields correspond to defined terms from COUNTER
    https://cop5.projectcounter.org/en/5.0.2/appendices/a-glossary-of-terms.html
    """

    platform_iri: str  # counter:Platform
    database_iri: str  # counter:Database
    sessionhour_id: str  # counter:Session
    item_iri: str  # counter:Item

    # within_iris corresponds roughly to counter:Title, but as a more
    # inclusive within/part-of/contained-by relationship
    within_iris: list[str]
