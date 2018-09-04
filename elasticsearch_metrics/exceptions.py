class ElasticsearchMetricsError(Exception):
    """Base class from which all elasticsearch-metrics-related excpetions inherit."""


class IndexTemplateNotFoundError(ElasticsearchMetricsError):
    def __init__(self, message, client_error):
        self.client_error = client_error
        super(IndexTemplateNotFoundError, self).__init__(message)


class IndexTemplateOutOfSyncError(ElasticsearchMetricsError):
    def __init__(self, message, mappings_in_sync, patterns_in_sync, settings_in_sync):
        self.mappings_in_sync = mappings_in_sync
        self.patterns_in_sync = patterns_in_sync
        self.settings_in_sync = settings_in_sync
        super(IndexTemplateOutOfSyncError, self).__init__(message)
