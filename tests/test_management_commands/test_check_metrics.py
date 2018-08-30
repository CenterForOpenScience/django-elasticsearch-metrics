import pytest
import mock

from elasticsearch_metrics.management.commands.check_metrics import Command
from elasticsearch_metrics.registry import registry


@pytest.fixture()
def mock_check_index_template_exists():
    with mock.patch(
        "elasticsearch_metrics.metrics.Metric.check_index_template_exists"
    ) as patch:
        yield patch


def test_exits_with_error_if_out_of_sync(
    run_mgmt_command, mock_check_index_template_exists
):
    mock_check_index_template_exists.return_value = False
    with pytest.raises(SystemExit):
        run_mgmt_command(Command, ["check_metrics"])


def test_exits_with_success(run_mgmt_command, mock_check_index_template_exists):
    mock_check_index_template_exists.return_value = True
    run_mgmt_command(Command, ["check_metrics"])
    assert mock_check_index_template_exists.call_count == len(registry.get_metrics())
