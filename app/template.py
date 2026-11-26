from sqlalchemy import func, select

from . import models, schemas
from .db import SessionLocal

DEFAULT_FIELDS: list[dict] = [
    {"key": "name", "label": "Название", "type": "text", "required": True},
    {"key": "category", "label": "Категория", "type": "enum", "options": schemas.CATEGORIES, "default_value": "other"},
    {"key": "tags", "label": "Теги (через запятую)", "type": "text", "default_value": ""},
    {"key": "description", "label": "Описание", "type": "textarea", "default_value": ""},
    {"key": "color", "label": "Цвет карточки", "type": "text", "default_value": "#5b8cff"},
    {"key": "icon", "label": "Иконка / короткий знак", "type": "text", "default_value": ""},
    {"key": "notes", "label": "Заметки дизайнера", "type": "textarea", "default_value": ""},
    {"key": "slot_size", "label": "Слотов занимает", "type": "number", "default_value": 1},
    {"key": "stackable", "label": "Стакается", "type": "checkbox", "default_value": False},
    {"key": "max_stack", "label": "Максимум в стаке", "type": "number", "default_value": 1},
    {"key": "usage_mode", "label": "Как применяется", "type": "enum", "options": schemas.USAGE_MODES, "default_value": "simple"},
    {"key": "target_kinds", "label": "Куда можно наводиться", "type": "enum", "options": schemas.TARGET_KINDS, "default_value": [], "multiple": True},
    {"key": "effect", "label": "Эффект", "type": "textarea", "default_value": ""},
    {"key": "consumed_on_use", "label": "Тратится при применении", "type": "checkbox", "default_value": False},
    {"key": "charges", "label": "Заряды (пусто = бесконечно)", "type": "number", "default_value": None},
    {"key": "cooldown_seconds", "label": "Перезарядка, сек", "type": "number", "default_value": 0},
    {"key": "requirements", "label": "Что нужно для применения", "type": "text", "default_value": ""},
    {"key": "sources", "label": "Где можно найти", "type": "sources"},
    {"key": "repairs", "label": "Какие поломки чинит", "type": "repairs"},
    {"key": "relations", "label": "Связи с другими предметами", "type": "relations"},
]


def seed_template() -> None:
    with SessionLocal() as db:
        count = db.scalar(select(func.count(models.TemplateField.id))) or 0
        if count:
            return
        for position, definition in enumerate(DEFAULT_FIELDS):
            values = dict(definition)
            values.setdefault("options", [])
            values.setdefault("default_value", None)
            values.setdefault("required", False)
            values.setdefault("multiple", False)
            values.setdefault("active", True)
            values["system"] = True
            values["position"] = position
            values["author"] = "система"
            db.add(models.TemplateField(**values))
        db.commit()
