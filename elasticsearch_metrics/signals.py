from django.dispatch import Signal

# Sent before index template is created in elasticsearch
pre_index_template_create = Signal()
# Sent after index template is created in elasticsearch
post_index_template_create = Signal()
# Sent at the beginning of Metric's save()
pre_save = Signal()
# Like pre_save, but sent at the end of the save() method
post_save = Signal()
