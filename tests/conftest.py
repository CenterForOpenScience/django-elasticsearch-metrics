import mock
import pytest

from elasticsearch_dsl import connections


@pytest.fixture(scope="function")
def client():
    return connections.get_connection()


@pytest.fixture(scope="function", autouse=True)
def _es_marker(request, client):
    """Clear out all indices and index templates before and after
    tests marked with ``es``.
    """
    marker = request.node.get_closest_marker("es")
    if marker:

        def teardown_es():
            client.indices.delete(index="*")
            client.indices.delete_template("*")

        teardown_es()
        yield
        teardown_es()
    else:
        yield


@pytest.fixture()
def mock_save():
    with mock.patch("elasticsearch_metrics.metrics.Document.save") as patch:
        yield patch


@pytest.fixture()
def run_mgmt_command(capsys):
    """Function fixture that runs a python manage.py with arguments
    and returns the stdout and stderr as a tuple.
    """

    def f(cmd_class, argv=None):
        argv = argv or []
        cmd = cmd_class()
        cmd.run_from_argv(["manage.py"] + argv)
        out, err = capsys.readouterr()
        return out, err

    return f
