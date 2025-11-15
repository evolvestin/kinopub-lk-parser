import logging

from django.apps import apps


class DatabaseLogHandler(logging.Handler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._log_entry_model = None

    @property
    def log_entry_model(self):
        if self._log_entry_model is None:
            self._log_entry_model = apps.get_model('app', 'LogEntry')
        return self._log_entry_model

    def emit(self, record):
        try:
            self.log_entry_model.objects.create(
                level=record.levelname,
                module=record.module,
                message=record.getMessage()
            )
        except Exception:
            pass
