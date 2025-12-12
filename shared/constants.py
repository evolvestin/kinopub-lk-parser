from enum import StrEnum


class UserRole(StrEnum):
    GUEST = 'guest'
    VIEWER = 'viewer'
    ADMIN = 'admin'


RATING_VALUES = [float(i) for i in range(1, 11)]