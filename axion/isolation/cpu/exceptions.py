from ...core.exceptions import EngineError


class IsolationBackendError(EngineError):
    """
    Isolation Backend Hataları

    Isolation için gerekli systemd işlemleri sırasında oluşan hatalar.
    """
    pass


class IsolationUnsupportedError(EngineError):
    """
    Isolation Destek Hataları

    Isolation için gereken desteklemeye sahip olunmadığında oluşan hatalar.
    """
    pass


class IsolationPermissionError(EngineError):
    """
    Isolation Yetki Hataları

    Isolation için gerekli yetkilerin bulunmaması durumunda oluşan hatalar.
    """
    pass
