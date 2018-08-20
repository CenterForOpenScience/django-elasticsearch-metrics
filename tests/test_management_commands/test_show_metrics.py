from elasticsearch_metrics.management.commands.show_metrics import Command


def test_without_args(run_mgmt_command):
    out, err = run_mgmt_command(Command, ["show_metrics"])
    assert "DummyMetric" in out
    assert "dummyapp_dummymetric-*" in out
