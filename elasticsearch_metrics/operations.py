from django.db.migrations.operations.base import Operation

def _create_metric(metric):
    pass
    # TODO

class CreateMetric(Operation):
    reduces_to_sql = False  # Ignore in sqlmigrate
    reversible = True

    def __init__(self, metric):
        self.metric = metric

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        return _create_metric(self.metric)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        pass
        # TODO

    def describe(self):
        # This is used to describe what the operation does in console output.
        return "Creating Elasticsearch index template for {self.metric}".format(self=self)
