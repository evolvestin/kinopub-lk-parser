import os


class URLStore:
    _instance = None
    _file_path = '/app/shared/tunnel_url.txt'

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def set_url(self, url: str):
        url = url.rstrip('/')
        try:
            os.makedirs(os.path.dirname(self._file_path), exist_ok=True)
            with open(self._file_path, 'w', encoding='utf-8') as f:
                f.write(url)
        except Exception:
            pass

    def get_url(self) -> str | None:
        if os.path.exists(self._file_path):
            try:
                with open(self._file_path, encoding='utf-8') as f:
                    return f.read().strip()
            except Exception:
                pass
        return None
