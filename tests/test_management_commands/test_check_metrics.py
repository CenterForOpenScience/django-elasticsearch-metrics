import pytest
import mock

from elasticsearch_metrics import exceptions
from elasticsearch_metrics.management.commands.check_metrics import Command
from elasticsearch_metrics.registry import registry


@pytest.fixture()
def mock_check_index_template():
    with mock.patch(
        "elasticsearch_metrics.metrics.Metric.check_index_template"
    ) as patch:
        yield patch


def test_exits_with_error_if_out_of_sync(run_mgmt_command, mock_check_index_template):
    mock_check_index_template.side_effect = exceptions.IndexTemplateNotFoundError(
        "Index template does not exist", client_error=None
    )
    with pytest.raises(SystemExit):
        run_mgmt_command(Command, ["check_metrics"])


def test_exits_with_success(run_mgmt_command, mock_check_index_template):
    mock_check_index_template.return_value = True
    run_mgmt_command(Command, ["check_metrics"])
    assert mock_check_index_template.call_count == len(registry.get_metrics())
