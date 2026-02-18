class URLStore:
    _instance = None
    _url: str | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def set_url(self, url: str):
        self._url = url.rstrip('/')

    def get_url(self) -> str | None:
        return self._url
