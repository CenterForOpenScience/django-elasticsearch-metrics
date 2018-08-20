from django.conf import settings
from elasticsearch_dsl import field as edsl_field

__all__ = ["Date"]
# Expose all fields from elasticsearch_dsl.field
# We do this instead of 'from elasticsearch_dsl.field import *' because elasticsearch_metrics
# has its own subclass of Date
for each in (
    field_name
    for field_name in dir(edsl_field)
    if field_name != "Date" and not field_name.startswith("_")
):
    field = getattr(edsl_field, each)
    is_field_subclass = isinstance(field, type) and issubclass(field, edsl_field.Field)
    if field is edsl_field.Field or is_field_subclass:
        globals()[each] = field
        field.__module__ = __name__
        __all__.append(each)


class Date(edsl_field.Date):
    """Same as `elasticsearch_dsl.field.Date` except that this respects
    the TIMEZONE Django setting.
    """

    def __init__(self, default_timezone=None, *args, **kwargs):
        default_timezone = default_timezone or getattr(settings, "TIMEZONE", None)
        super(Date, self).__init__(default_timezone=default_timezone, *args, **kwargs)
