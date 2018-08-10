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
