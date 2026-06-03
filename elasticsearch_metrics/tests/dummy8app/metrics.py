import datetime

from elasticsearch8 import dsl as esdsl
from elasticsearch_metrics.imps import elastic8 as djelme

dot_path_analyzer = esdsl.analyzer(
    "dot_path_analyzer",
    tokenizer=esdsl.tokenizer("dot_path_tokenizer", "path_hierarchy", delimiter="."),
)


class Dummy8Event(djelme.EventRecord):
    intensity: int


class Monthly8Event(djelme.EventRecord):
    intenzity: int

    class Meta:
        index_name_prefix = "dummy8evenz"
        timeseries_recordtype_name = "eventlog"
        timeseries_index_timedepth = 2


class ThingHappened(djelme.EventRecord):
    thing_id: str = ""
    happen_code: str | None = None
    dot_path: str | None = esdsl.mapped_field(
        esdsl.Text(analyzer=dot_path_analyzer), default=None
    )
    commentary: str | None = esdsl.mapped_field(esdsl.Text(), default=None)

    class Index:
        settings = {"refresh_interval": "-1"}

    class Meta:
        timeseries_recordtype_name = "happen"
        timeseries_index_timedepth = 2  # monthly timeseries indexes
        # keep ninety days of data
        timeseries_index_expiration = datetime.timedelta(days=90)


class ThingHappeningsReport(djelme.CyclicReport):
    CYCLE_TIMEDEPTH = 2
    UNIQUE_TOGETHER_FIELDS = ("cycle_coverage", "thing_id")

    thing_id: str
    happen_count: int

    class Meta:
        index_name_prefix = "blarg_"
        timeseries_index_timedepth = 1  # yearly timeseries indexes


class SimpleKV(djelme.SimpleRecord):
    UNIQUE_TOGETHER_FIELDS = ("key",)
    key: str
    val: int
