class PlatformError(Exception):
    pass


class NotFoundError(PlatformError):
    pass


class ChatStateError(PlatformError):
    pass


class ValidationError(PlatformError):
    pass


class DuplicateError(PlatformError):
    pass
