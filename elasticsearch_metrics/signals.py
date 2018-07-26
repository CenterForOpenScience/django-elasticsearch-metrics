from django.dispatch import Signal

# Sent before index template is created in elastic search
# TODO document in README
pre_index_template_create = Signal(providing_args=["index_template"])
