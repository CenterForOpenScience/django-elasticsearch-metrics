"""elasticsearch_metrics.util.timeseries_naming

for naming timeseries indexes with lexical time coverage
(so an index-name wildcard can be used to query several indexes)
"""

from __future__ import annotations

__all__ = (
    "TimeseriesIndexNaming",
    "TimeseriesRangePattern",
    "format_namepart",
    "format_template_name",
)

import collections.abc as cabc
import dataclasses
import datetime
import typing

from elasticsearch_metrics.util.timeparts import (
    TIMEPART_DELIMITER,
    TimepartStrat,
    Timeparts,
    AbstractTimeparts,
    serialize_timeparts,
)

_DELIMITER: str = "_"
_TEMPLATE_NAME_SUFFIX = "_template"


@dataclasses.dataclass(frozen=True)
class TimeseriesIndexNaming:
    """dataclass for naming an index in a timeseries

    >>> TimeseriesIndexNaming('a', 'rt', (9999, 22), GregorianTime(2))
    TimeseriesIndexNaming(app_label='a',
        recordtype='rt',
        given_timeparts=(9999, 22),
        timepart_strat=GregorianTime(default_timedepth=2, tz=datetime.timezone.utc),
        prefix='')
    >>> str(_)
    'a_rt_9999.22.'
    >>> str(TimeseriesIndexNaming('a', 'rt', (9999, 22, 1), GregorianTime(3)))
    'a_rt_9999.22.1.'

    given timepart strategy handles truncating or padding timeparts of unexpected length
    >>> str(TimeseriesIndexNaming('a', 'rt', (1, 2, 3, 4, 5), GregorianTime(3)))
    'a_rt_1.2.3.'
    >>> str(TimeseriesIndexNaming('a', 'rt', (1, 2, 3), GregorianTime(5)))
    'a_rt_1.2.3.0.0.'

    can give an index name `prefix`
    >>> str(TimeseriesIndexNaming('a', 'rt', (9999,22,1,0), GregorianTime(2), prefix='prefix-'))
    'prefix-a_rt_9999.22.'

    use `.to_str(wildcard=True)` to get a pattern matching all indexes within the given timeparts
    >>> TimeseriesIndexNaming('a', 'rt', (1, 2, 3, 4, 5), GregorianTime(5)).to_str(wildcard=True)
    'a_rt_1.2.3.4.5.*'

    can also give a date
    >>> TimeseriesIndexNaming('ap', 'rt', datetime.date(9876,5,4), GregorianTime(2)).to_str()
    'ap_rt_9876.5.'

    or a semver-like timepart string
    >>> TimeseriesIndexNaming('a', 'rt', '5.6.7.8', GregorianTime(3), prefix='hello_').to_str(wildcard=True)
    'hello_a_rt_5.6.7.*'
    """

    app_label: str
    recordtype: str
    given_timeparts: AbstractTimeparts | datetime.date | str
    timepart_strat: TimepartStrat
    prefix: str = ""

    @classmethod
    def parse(
        cls,
        index_name: str,
        timepart_strat: TimepartStrat,
        *,
        prefix: str = "",
    ) -> typing.Self:
        """construct a TimeseriesIndexNaming by parsing an index name

        >>> TimeseriesIndexNaming.parse('myapp_myrecord_2000.12.1.', GregorianTime(3))
        TimeseriesIndexNaming(app_label='myapp',
            recordtype='myrecord',
            given_timeparts='2000.12.1.',
            timepart_strat=GregorianTime(default_timedepth=3, tz=datetime.timezone.utc),
            prefix='')
        >>> _.timeparts
        (2000, 12, 1)

        can also give an expected `prefix` to remove
        >>> TimeseriesIndexNaming.parse(
        ...     'prefixmyapp_myrecord_2000.12.2.',
        ...     GregorianTime(3),
        ...     prefix='prefix',
        ... )
        TimeseriesIndexNaming(app_label='myapp',
            recordtype='myrecord',
            given_timeparts='2000.12.2.',
            timepart_strat=GregorianTime(default_timedepth=3, tz=datetime.timezone.utc),
            prefix='prefix')
        >>> _.timeparts
        (2000, 12, 2)
        """
        if not index_name.startswith(prefix):
            raise ValueError(f"expected prefix {prefix!r} on index name {index_name!r}")
        _trimmed_name = index_name.removeprefix(prefix)
        try:
            _app_label, _recordtype, _timeparts = _trimmed_name.split(_DELIMITER)
        except ValueError as _err:
            raise ValueError(
                "expected index name format applabel_recordtype_timeparts",
                _trimmed_name,
            ) from _err
        return cls(
            _app_label,
            _recordtype,
            _timeparts,
            timepart_strat,
            prefix=prefix,
        )

    @property
    def timeparts(self) -> Timeparts:
        # neither truncate nor pad, just parse as given
        return self.timepart_strat.get_timeparts(
            self.given_timeparts, pad=False, truncate=False
        )

    @property
    def timeparts_for_naming(self) -> Timeparts:
        # when naming an index, truncate or pad to the default timedepth
        return self.timepart_strat.get_timeparts(self.given_timeparts)

    @property
    def timeparts_for_wildcard(self) -> Timeparts:
        # for wildcards, do truncate but do not pad
        return self.timepart_strat.get_timeparts(self.given_timeparts, pad=False)

    def __str__(self) -> str:
        """get the name of a specific index, no wildcard"""
        return self.to_str()

    def to_str(self, *, wildcard: bool = False) -> str:
        """get the name of an index or a wildcard pattern"""
        _parts = [
            format_namepart(self.app_label),
            format_namepart(self.recordtype),
        ]
        _timeparts = (
            self.timeparts_for_wildcard if wildcard else self.timeparts_for_naming
        )
        if _timeparts:
            _parts.append(_format_timename(_timeparts))
        else:
            _parts.append("")  # add trailing delimiter for unambiguous pattern matching
        _base_name = _DELIMITER.join(_parts)
        _suffix = "*" if wildcard else ""
        return f"{self.prefix}{_base_name}{_suffix}"


@dataclasses.dataclass(frozen=True)
class TimeseriesRangePattern:
    """dataclass for a wildcard pattern matching all index names within a time range

    >>> TimeseriesRangePattern(
    ...     app_label='ap',
    ...     recordtype='rt',
    ...     from_when=(5020, 2, 2),
    ...     until_when=(5020, 12, 20),
    ...     timepart_strat=GregorianTime(2),
    ... )
    TimeseriesRangePattern(app_label='ap', recordtype='rt',
        from_when=(5020, 2, 2), until_when=(5020, 12, 20),
        timepart_strat=GregorianTime(default_timedepth=2, tz=datetime.timezone.utc),
        index_name_prefix='', max_fanout=3)

    use `.to_str()` to get the full pattern -- may be a simple wildcard with shared timeparts
    >>> TimeseriesRangePattern('ap', 'rt',
    ...     (5020, 2, 2), (5020, 12, 20), GregorianTime(2)).to_str()
    'ap_rt_5020.*'
    >>> TimeseriesRangePattern('ap', 'rt',
    ...     (5020, 2, 2), (5020, 2, 20), GregorianTime(2)).to_str()
    'ap_rt_5020.2.*'

    or, if unshared timeparts close enough, enumerate possibilities to narrow the wildcard
    >>> TimeseriesRangePattern('ap', 'rt',
    ...     (5020, 2, 2), (5020, 3, 3), GregorianTime(3)).to_str()
    'ap_rt_5020.2.*,ap_rt_5020.3.1.*,ap_rt_5020.3.2.*'

    `max_fanout` controls what's "close enough" to enumerate
    >>> _fanout_example = TimeseriesRangePattern('ap', 'rt',
    ...     (5020, 2, 2), (5020, 3, 5), GregorianTime(3), max_fanout=0)
    >>> _fanout_example.to_str()
    'ap_rt_5020.*'
    >>> dataclasses.replace(_fanout_example, max_fanout=1).to_str()
    'ap_rt_5020.2.*,ap_rt_5020.3.*'
    >>> dataclasses.replace(_fanout_example, max_fanout=7).to_str()
    'ap_rt_5020.2.*,ap_rt_5020.3.1.*,ap_rt_5020.3.2.*,ap_rt_5020.3.3.*,ap_rt_5020.3.4.*'

    with `.to_str(include_less_timedepth=True)`, include patterns for indexes created with lower timedepths
    >>> TimeseriesRangePattern('ap', 'rt',
    ...     (5020, 2, 2), (5020, 2, 20), GregorianTime(2)).to_str(include_less_timedepth=True)
    'ap_rt_5020.2.*,ap_rt_,ap_rt_5020.'

    can also give dates
    >>> TimeseriesRangePattern('ap', 'rt',
    ...     datetime.date(2050, 5, 5), datetime.date(2050, 5, 7),
    ...     GregorianTime(2)).to_str()
    'ap_rt_2050.5.*'

    can give `index_name_prefix` to add a prefix to each part
    >>> TimeseriesRangePattern('ap', 'rt',
    ...     datetime.date(2050, 5, 5), datetime.date(2050, 5, 7),
    ...     GregorianTime(3), index_name_prefix='blarg_').to_str()
    'blarg_ap_rt_2050.5.5.*,blarg_ap_rt_2050.5.6.*'
    """

    app_label: str
    recordtype: str
    from_when: AbstractTimeparts | datetime.date
    until_when: AbstractTimeparts | datetime.date
    timepart_strat: TimepartStrat
    index_name_prefix: str = ""
    max_fanout: int = 3

    @property
    def from_timeparts(self) -> Timeparts:
        return self.timepart_strat.get_timeparts(self.from_when)

    @property
    def until_timeparts(self) -> Timeparts:
        return self.timepart_strat.get_timeparts(self.until_when)

    def __str__(self) -> str:
        """get the pattern as a string (no index-name prefix)"""
        return self.to_str()

    def to_str(self, *, include_less_timedepth: bool = False) -> str:
        """get the pattern as a string, with optional index-name prefix"""
        return ",".join(
            self.each_name_in_timerange(include_less_timedepth=include_less_timedepth)
        )

    def each_name_in_timerange(
        self, *, include_less_timedepth: bool = False
    ) -> cabc.Iterator[str]:
        _lesser_timepartsen: set[Timeparts] = set()
        for _timeparts in self.timepart_strat.each_timeparts_in_timerange(
            self.from_timeparts,
            self.until_timeparts,
            max_fanout=self.max_fanout,
        ):
            yield self._get_naming(_timeparts).to_str(wildcard=True)
            if include_less_timedepth:
                _lesser_timepartsen.update(
                    _timeparts[:_i] for _i in range(len(_timeparts))
                )
        for _lesser_timeparts in sorted(_lesser_timepartsen):
            # non-wildcards, to include indexes created with less timedepth
            yield str(self._get_naming(_lesser_timeparts, exact_timedepth=True))

    def _get_naming(
        self,
        timeparts: Timeparts,
        *,
        exact_timedepth: bool = False,
    ) -> TimeseriesIndexNaming:
        return TimeseriesIndexNaming(
            self.app_label,
            self.recordtype,
            timeparts,
            timepart_strat=(
                self.timepart_strat.with_default_timedepth(len(timeparts))
                if exact_timedepth
                else self.timepart_strat
            ),
            prefix=self.index_name_prefix,
        )


def format_template_name(
    app_label: str,
    recordtype: str,
) -> str:
    """
    >>> format_template_name('blah', 'fleh')
    'blah_fleh__template'
    """
    return _DELIMITER.join(
        (format_namepart(app_label), format_namepart(recordtype), _TEMPLATE_NAME_SUFFIX)
    )


def format_namepart(namepart: str) -> str:
    return namepart.replace(_DELIMITER, "").lower()


def _format_timename(timeparts: AbstractTimeparts) -> str:
    """
    >>> _format_timename((1999,))
    '1999.'
    >>> _format_timename((2345,))
    '2345.'

    use with any series of integers
    >>> _format_timename((1234, 5, 6, 7))
    '1234.5.6.7.'
    >>> _format_timename((2345, 6, 2, 17, 4200))
    '2345.6.2.17.4200.'
    >>> _format_timename((6, 1, 8, 2))
    '6.1.8.2.'
    >>> _format_timename((2345, 0))
    '2345.0.'
    """
    return f"{serialize_timeparts(timeparts)}{TIMEPART_DELIMITER}"


if __debug__:
    from elasticsearch_metrics.util.timeparts import (  # noqa: F401 (for use in doctests)
        GregorianTime,
    )

    __test__ = {
        "more name formatting combinations": """
>>> TimeseriesIndexNaming('app', 'type', '500.2.3', GregorianTime(3)).to_str()
'app_type_500.2.3.'
>>> TimeseriesIndexNaming('app', 'type', (), GregorianTime(0)).to_str()
'app_type_'
>>> TimeseriesIndexNaming('a', 'rt', (1, 2, 3, 4, 5), GregorianTime(3)).to_str(wildcard=True)
'a_rt_1.2.3.*'
>>> TimeseriesIndexNaming('a', 'rt', (), GregorianTime(2)).to_str(wildcard=True)
'a_rt_*'
""",
        "more pattern formatting combinations": """
>>> TimeseriesRangePattern('ap', 'rt',
...     (5020, 2, 1), (5020, 3), GregorianTime(2)).to_str()
'ap_rt_5020.2.*'
>>> TimeseriesRangePattern('ap', 'rt',
...     (5020, 2, 2), (5020, 2, 3), GregorianTime(3), index_name_prefix='blarg').to_str()
'blargap_rt_5020.2.2.*'
>>> TimeseriesRangePattern('a', 'b', (1999,), (2002,), GregorianTime(2)).to_str()
'a_b_1999.*,a_b_2000.*,a_b_2001.*'
>>> TimeseriesRangePattern('a', 'b',
...     (1999, 27, 17, 0, 3), (1999, 27, 17, 0, 223,), GregorianTime(5)).to_str()
'a_b_1999.27.17.0.*'
>>> TimeseriesRangePattern('a', 'b',
...     (1999, 27, 17, 0, 3), (2002, 117, 17, 0, 3), GregorianTime(5)).to_str()
'a_b_1999.*,a_b_2000.*,a_b_2001.*,a_b_2002.*'
>>> TimeseriesRangePattern('ap', 'rt',
...     datetime.date(2050, 5, 5), datetime.date(2050, 5, 8),
...     GregorianTime(2), index_name_prefix='blag-').to_str(include_less_timedepth=True)
'blag-ap_rt_2050.5.*,blag-ap_rt_,blag-ap_rt_2050.'
>>> TimeseriesRangePattern('ap', 'rt',
...     datetime.date(2050, 5, 5), (2050, 5, 8, 10),
...     GregorianTime(3)).to_str()
'ap_rt_2050.5.5.*,ap_rt_2050.5.6.*,ap_rt_2050.5.7.*'
>>> TimeseriesRangePattern('ap', 'rt',
...     (2050, 5, 5, 3), datetime.date(2050, 5, 8),
...     GregorianTime(3)).to_str(include_less_timedepth=True)
'ap_rt_2050.5.5.*,ap_rt_2050.5.6.*,ap_rt_2050.5.7.*,ap_rt_,ap_rt_2050.,ap_rt_2050.5.'
>>> TimeseriesRangePattern('ap', 'rt',
...     (200, 5), datetime.date(200, 5, 8),
...     GregorianTime(3)).to_str()
'ap_rt_200.5.*'
""",
    }
