class DataProviderError(Exception):
    pass


class DataSourceUnavailableError(DataProviderError):
    pass


class CodeNormalizationError(DataProviderError):
    pass
