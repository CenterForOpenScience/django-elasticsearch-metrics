from elasticsearch_metrics.management.commands.sync_metrics import Command


def test_without_args(capsys):
    cmd = Command()
    cmd.run_from_argv(['manage.py', 'sync_data'])
    out, err = capsys.readouterr()
    assert 'Synchronized metrics.' in out


def test_synchronizes_all_metrics():
    assert 0, 'todo'
