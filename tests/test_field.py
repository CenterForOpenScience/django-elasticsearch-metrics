import pytest
from dateutil import tz

from elasticsearch_metrics import metrics


class TestDate:
    @pytest.mark.parametrize("timezone", ["America/Chicago", "UTC"])
    def test_respects_timezone_setting(self, settings, timezone):
        settings.TIMEZONE = timezone
        field = metrics.Date()
        assert field._default_timezone == tz.gettz(timezone)
