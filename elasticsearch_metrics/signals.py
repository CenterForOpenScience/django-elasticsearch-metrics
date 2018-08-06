from django.dispatch import Signal

# TODO: Allow passing sender as string, a la ModelSignal?

# Sent before index template is created in elastic search
pre_index_template_create = Signal(providing_args=["index_template", "using"])
# Sent at the beginning of Metric's save()
pre_save = Signal(providing_args=["instance", "using", "index"])
# Like pre_save, but sent at the end of the save() method
post_save = Signal(providing_args=["instance", "using", "index"])
