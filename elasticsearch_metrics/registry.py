from django.apps import apps
from collections import defaultdict, OrderedDict


class Registry(object):
    """Registry that keeps track of Metric classes (similar to how
    django.apps.registry.Apps keeps track of Model classes).
    """

    def __init__(self):
        # Mapping of app labels => metric names => metric classes
        # Every time a metric is imported, MetricMeta.__new__
        # calls registry.register which creates
        # an entry in all_metrics.
        self.all_metrics = defaultdict(OrderedDict)

    # similar to apps.register_model
    def register(self, app_label, metric_cls):
        """Add a Metric to the registry."""
        app_metrics = self.all_metrics[app_label]
        metric_name = metric_cls.__name__.lower()
        if metric_name in app_metrics:
            # Raise an error for conflicting metrics (same behavior as apps.register_model)
            raise RuntimeError(
                "Conflicting '{}' metrics in application '{}': {} and {}.".format(
                    metric_name, app_label, app_metrics[metric_name], metric_cls
                )
            )
        app_metrics[metric_name] = metric_cls

    # similar to apps.get_model
    def get_metric(self, app_label, metric_name=None):
        """Return the metric matching the given app_label and model_name.

        As a shortcut, app_label may be in the form <app_label>.<model_name>.

        model_name is case-insensitive.

        Raise LookupError if no application exists with this label, or no
        metric exists with this name in the application. Raise ValueError if
        called with a single argument that doesn't contain exactly one dot.
        """
        self.check_apps_ready()

        if metric_name is None:
            app_label, metric_name = app_label.split(".")

        if app_label not in self.all_metrics:
            raise LookupError(
                "No metrics found in app with label '{}'.".format(app_label)
            )
        app_metrics = self.all_metrics[app_label]
        try:
            return app_metrics[metric_name.lower()]
        except KeyError:
            raise LookupError(
                "App '{}' doesn't have a '{}' metric.".format(app_label, metric_name)
            )

    def get_metrics(self, app_label=None):
        """Return list of registered metric classes, optionally filtered on an app_label."""
        if app_label:
            if app_label not in self.all_metrics:
                raise LookupError(
                    "No metrics found in app with label '{}'.".format(app_label)
                )
            app_labels = [app_label]
        else:
            app_labels = self.all_metrics.keys()
        result = []
        for app_label in app_labels:
            result.extend(list(self.all_metrics[app_label].values()))
        return result

    def check_apps_ready(self):
        return apps.check_apps_ready()


registry = Registry()
