from elasticsearch_dsl import Document, Date


class Metric(Document):
    timestamp = Date()

    @classmethod
    def get_index_template(cls):
        assert 0, "todo"
