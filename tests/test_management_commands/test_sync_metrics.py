import pytest
import mock

from elasticsearch_metrics.management.commands.sync_metrics import Command
from elasticsearch_metrics import metrics
from elasticsearch_metrics.registry import registry


@pytest.fixture()
def mock_create_index_template():
    with mock.patch(
        "elasticsearch_metrics.metrics.Metric.create_index_template"
    ) as patch:
        yield patch


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


def test_with_connection(run_mgmt_command, mock_create_index_template, settings):
    settings.ELASTICSEARCH_DSL = {
        "default": {"hosts": "localhost:9201"},
        "alternate": {"hosts": "localhost:9202"},
    }
    out, err = run_mgmt_command(Command, ["sync_metrics", "--connection", "alternate"])
    call_kwargs = mock_create_index_template.call_args[1]
    assert call_kwargs["using"] == "alternate"
    assert "Using connection: 'alternate'" in out
