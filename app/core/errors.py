class JarvisError(Exception):
    pass


class NotFoundError(JarvisError, LookupError):
    pass


class ValidationError(JarvisError, ValueError):
    pass


class BackupError(JarvisError):
    pass
