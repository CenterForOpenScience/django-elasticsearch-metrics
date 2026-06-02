import collections.abc as cabc
import dataclasses
import datetime
import itertools
import typing

__all__ = (
    "serialize_timeparts",
    "parse_timeparts",
    "Timeparts",
    "AbstractTimeparts",
    "TimepartStrat",
    "GregorianTime",
    "TIMEPART_DELIMITER",
)

TIMEPART_DELIMITER: str = "."

Timeparts = tuple[int, ...]
AbstractTimeparts = cabc.Sequence[int]


###
# strategy-agnostic timepart functios


def serialize_timeparts(
    when: AbstractTimeparts, max_timedepth: int | None = None
) -> str:
    """
    >>> serialize_timeparts((3000, 2))
    '3000.2'
    >>> serialize_timeparts((3000, 7, 12))
    '3000.7.12'
    >>> serialize_timeparts((3000, 9, 1, 0, 0, 0))
    '3000.9.1.0.0.0'

    truncates to max_timedepth
    >>> serialize_timeparts((3000, 9, 1, 0, 0, 0), max_timedepth=3)
    '3000.9.1'

    does not pad
    >>> serialize_timeparts((3000,), max_timedepth=5)
    '3000'

    >>> serialize_timeparts(())
    ''
    """
    assert all(isinstance(_part, int) for _part in when)
    _each_part: cabc.Iterator[str] = map(str, when)
    if max_timedepth is not None:
        _each_part = itertools.islice(_each_part, max_timedepth)
    return TIMEPART_DELIMITER.join(_each_part)


def parse_timeparts(timepart_str: str, max_timedepth: int | None = None) -> Timeparts:
    """
    >>> parse_timeparts('1.2.3')
    (1, 2, 3)
    >>> parse_timeparts('1999.12.7.9')
    (1999, 12, 7, 9)
    >>> parse_timeparts('1999.12.7.9', max_timedepth=2)
    (1999, 12)
    >>> parse_timeparts('')
    ()
    >>> parse_timeparts('100.200.')
    (100, 200)
    """
    _split_parts = timepart_str.split(TIMEPART_DELIMITER)
    if not any(_split_parts):
        return ()
    _parsed = tuple(int(_part) for _part in _split_parts if _part)
    return _parsed if max_timedepth is None else _parsed[:max_timedepth]


def _each_timeparts_in_timerange(
    from_timeparts: AbstractTimeparts,
    until_timeparts: AbstractTimeparts,
    *,
    timedepth: int,
    max_fanout: int,
) -> cabc.Generator[Timeparts]:
    """
    yield timeparts
    """
    if timedepth <= 0:
        yield ()  # reached timedepth
        return
    _from_part, *_from_rest = from_timeparts or [0]
    _until_part, *_until_rest = until_timeparts or [0]
    if _from_part == _until_part:
        for _rest_parts in _each_timeparts_in_timerange(
            _from_rest,
            _until_rest,
            timedepth=timedepth - 1,
            max_fanout=max_fanout,
        ):
            yield (_from_part, *_rest_parts)
    elif 0 < (_until_part - _from_part) <= max_fanout:  # not too far apart
        for _parallel_part in range(_from_part, _until_part):
            yield (_parallel_part,)
        if any(_until_rest):  # some of the "until" bucket is included
            _from_zero = tuple(itertools.repeat(0, len(_until_rest)))
            for _rest_parts in _each_timeparts_in_timerange(
                _from_zero,
                _until_rest,
                timedepth=timedepth - 1,
                max_fanout=max_fanout,
            ):
                yield (_until_part, *_rest_parts)
    else:  # too far apart
        yield ()


###
# protocol for timepart strategies


class TimepartStrat(typing.Protocol):
    def get_timeparts(
        self,
        when: AbstractTimeparts | datetime.date | str,
        pad: bool = True,
        truncate: bool = True,
    ) -> Timeparts: ...

    def each_timeparts_in_timerange(
        self,
        from_timeparts: AbstractTimeparts,
        until_timeparts: AbstractTimeparts,
        *,
        max_fanout: int,
    ) -> cabc.Iterator[Timeparts]: ...

    def with_default_timedepth(self, new_default_timedepth: int) -> "TimepartStrat": ...


###
# default TimepartStrat implementation


@dataclasses.dataclass
class GregorianTime(TimepartStrat):
    default_timedepth: int
    tz: datetime.tzinfo = datetime.timezone.utc

    def get_timeparts(
        self,
        when: AbstractTimeparts | datetime.date | str,
        pad: bool = True,
        truncate: bool = True,
    ) -> Timeparts:
        """
        >>> GregorianTime(2).get_timeparts(datetime.date(3456, 7, 8))
        (3456, 7)
        >>> GregorianTime(4).get_timeparts((3456,))
        (3456, 1, 1, 0)
        >>> GregorianTime(4).get_timeparts((3456,), pad=False)
        (3456,)
        >>> GregorianTime(4).get_timeparts(datetime.date(3456, 7, 8))
        (3456, 7, 8, 0)
        >>> GregorianTime(4).get_timeparts((3456, 7, 8, 9, 10, 11))
        (3456, 7, 8, 9)
        >>> GregorianTime(4).get_timeparts((3456, 7, 8, 9, 10, 11), truncate=False)
        (3456, 7, 8, 9, 10, 11)
        >>> GregorianTime(2).get_timeparts('3456.7.8.9')
        (3456, 7)
        >>> GregorianTime(2).get_timeparts('3456.7.8.9', pad=False, truncate=False)
        (3456, 7, 8, 9)
        >>> GregorianTime(4).get_timeparts('3456-07-08T09:10:11+00:00')
        (3456, 7, 8, 9)
        """
        _parts: Timeparts
        if isinstance(when, datetime.date):
            _parts = tuple(self._each_timepart_from_date(when))
        elif isinstance(when, str):
            _parts = tuple(self._each_timepart_from_str(when))
        elif isinstance(when, cabc.Sequence) and not isinstance(when, str):
            _parts = tuple(when)
        else:
            raise ValueError("expected tuple, list, date, datetime, or str", when)
        if pad and len(_parts) < self.default_timedepth:
            _parts = tuple(
                itertools.islice(
                    self._each_timepart_with_defaults(_parts), self.default_timedepth
                )
            )
        return _parts[: self.default_timedepth] if truncate else _parts

    def each_timeparts_in_timerange(
        self,
        from_timeparts: AbstractTimeparts,
        until_timeparts: AbstractTimeparts,
        *,
        max_fanout: int,
    ) -> cabc.Iterator[Timeparts]:
        """
        yield timeparts that cover the given timerange

        >>> list(GregorianTime(2).each_timeparts_in_timerange(
        ...     (5020, 2, 2), (5020, 12, 20), max_fanout=3))
        [(5020,)]
        >>> list(GregorianTime(2).each_timeparts_in_timerange(
        ...     (5020, 2, 2), (5020, 2, 20), max_fanout=3))
        [(5020, 2)]

        >>> list(GregorianTime(2).each_timeparts_in_timerange(
        ...     (5020, 2, 2), (5020, 3, 20), max_fanout=3))
        [(5020, 2), (5020, 3)]

        >>> list(GregorianTime(2).each_timeparts_in_timerange(
        ...     (5020, 2, 2), (6020, 12, 20), max_fanout=3))
        [()]

        >>> list(GregorianTime(3).each_timeparts_in_timerange(
        ...     (5020, 2, 2), (5020, 3, 3), max_fanout=3))
        [(5020, 2), (5020, 3, 1), (5020, 3, 2)]

        >>> list(GregorianTime(3).each_timeparts_in_timerange(
        ...     (5020, 2, 2), (5021, 3, 3), max_fanout=3))
        [(5020,), (5021, 1), (5021, 2), (5021, 3, 1), (5021, 3, 2)]

        >>> list(GregorianTime(3).each_timeparts_in_timerange(
        ...     (5020, 2, 2), (5021, 3, 3), max_fanout=2))
        [(5020,), (5021,)]

        >>> list(GregorianTime(3).each_timeparts_in_timerange(
        ...     (5020, 2, 2), (5021, 7, 3), max_fanout=3))
        [(5020,), (5021,)]
        """
        for _timeparts in _each_timeparts_in_timerange(
            from_timeparts,
            until_timeparts,
            timedepth=self.default_timedepth,
            max_fanout=max_fanout,
        ):
            if 0 in _timeparts[1:3]:
                continue  # skip month zero and day zero
            yield _timeparts

    def _each_timepart_from_str(self, given: str) -> cabc.Iterable[int]:
        try:  # iso-formatted date, e.g. "YYYY-MM-DD"
            _parsed_date = datetime.date.fromisoformat(given)
        except ValueError:
            pass
        else:
            return self._each_timepart_from_date(_parsed_date)
        try:  # iso-formatted datetime, e.g. "YYYY-MM-DDTHH:MM:SSZ"
            _parsed_datetime = datetime.datetime.fromisoformat(given)
        except ValueError:
            pass
        else:
            return self._each_timepart_from_date(_parsed_datetime.astimezone(self.tz))
        # if not iso-formatted date(time), assume semverlike "X.Y.Z"
        return parse_timeparts(given)

    def _each_timepart_from_date(self, given_date: datetime.date) -> cabc.Iterator[int]:
        yield given_date.year
        yield given_date.month
        yield given_date.day
        if isinstance(given_date, datetime.datetime):
            yield given_date.hour
            yield given_date.minute
            yield given_date.second

    def _each_timepart_with_defaults(
        self, timeparts: AbstractTimeparts
    ) -> cabc.Iterator[int]:
        for _i in range(3):  # guarantee at least year/month/day
            try:
                yield timeparts[_i]
            except IndexError:
                yield 1  # default 1 for year/month/day
        # if present, hour/minute/second/microsecond
        yield from timeparts[3:7]
        # zero-pad forever
        yield from itertools.repeat(0)

    def with_default_timedepth(self, new_default_timedepth: int) -> TimepartStrat:
        return dataclasses.replace(self, default_timedepth=new_default_timedepth)


if __debug__:
    __test__ = {
        "serialize_timeparts": """
>>> serialize_timeparts((3000, 2, 7, 9), max_timedepth=2)
'3000.2'
>>> serialize_timeparts((3000, 2), max_timedepth=1)
'3000'
>>> serialize_timeparts((3000, 2, 7, 9), max_timedepth=5)
'3000.2.7.9'
""",
        "get_timeparts": """
>>> GregorianTime(6).get_timeparts(datetime.datetime(3000, 9, 1, 5, 2))
(3000, 9, 1, 5, 2, 0)
>>> GregorianTime(3).get_timeparts(datetime.datetime(3000, 9, 1, 5, 2))
(3000, 9, 1)
>>> GregorianTime(3).get_timeparts(datetime.datetime(3000, 9, 1, 5, 2), truncate=False)
(3000, 9, 1, 5, 2, 0)
>>> GregorianTime(6).get_timeparts(datetime.date(3000, 9, 1))
(3000, 9, 1, 0, 0, 0)
>>> GregorianTime(6).get_timeparts(datetime.date(3000, 9, 1), pad=False)
(3000, 9, 1)
>>> GregorianTime(3).get_timeparts('3000.2.7.9')
(3000, 2, 7)
>>> GregorianTime(5).get_timeparts('3000.2.7.9')
(3000, 2, 7, 9, 0)
>>> GregorianTime(5).get_timeparts('3000.2.7.9', pad=False)
(3000, 2, 7, 9)
""",
    }
