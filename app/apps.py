from pathlib import Path

from django.apps import AppConfig
from django.conf import settings
from django.dispatch import receiver
from django.utils.autoreload import autoreload_started


@receiver(autoreload_started)
def ignore_frontend_in_autoreload(sender, **kwargs):
    try:
        frontend_dir = settings.BASE_DIR / 'frontend_webapp'
        for directory in list(sender.directory_globs.keys()):
            if Path(directory).is_relative_to(frontend_dir):
                del sender.directory_globs[directory]
        for file_path in list(sender.extra_files):
            if Path(file_path).is_relative_to(frontend_dir):
                sender.extra_files.discard(file_path)
    except Exception:
        pass


class AppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'

    def ready(self):
        pass