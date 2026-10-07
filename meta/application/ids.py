"""Порождение идентификаторов объектов метаданных."""

import uuid as _uuid


def new_uuid():
    return str(_uuid.uuid4())
