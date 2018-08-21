import pytest
import mock

from elasticsearch_metrics.management.commands.sync_metrics import Command
from elasticsearch_metrics import metrics
from elasticsearch_metrics.registry import registry


@pytest.fixture()
def mock_create_index_template():
    patch = mock.patch("elasticsearch_metrics.metrics.Metric.create_index_template")
    return patch.start()


def test_without_args(run_mgmt_command, mock_create_index_template):
    out, err = run_mgmt_command(Command, ["sync_metrics"])
    assert mock_create_index_template.call_count == len(registry.get_metrics())
    assert "Synchronized metrics." in out


def test_with_invalid_app(capsys, run_mgmt_command, mock_create_index_template):
    with pytest.raises(SystemExit):
        run_mgmt_command(Command, ["sync_metrics", "notanapp"])
    out, err = capsys.readouterr()
    assert "No metrics found for app 'notanapp'" in err


def test_with_app_label(run_mgmt_command, mock_create_index_template):
    class DummyMetric2(metrics.Metric):
        class Meta:
            app_label = "dummyapp2"

    out, err = run_mgmt_command(Command, ["sync_metrics", "dummyapp2"])
    assert mock_create_index_template.call_count == 1
