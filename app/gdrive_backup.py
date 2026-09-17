"""Backward-compatible import for callers that still use the old module name.

Backups are stored in Telegram; this shim deliberately contains no Google
Drive code so legacy imports cannot bring the removed integration back.
"""

from .telegram_backup_manager import BackupManager

__all__ = ['BackupManager']
