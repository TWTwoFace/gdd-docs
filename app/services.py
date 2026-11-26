from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models, schemas


def log_activity(
    db: Session,
    entity_type: str,
    entity_id: int,
    entity_name: str,
    action: str,
    author: str,
    details: str = "",
) -> None:
    db.add(
        models.Activity(
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            action=action,
            author=author,
            details=details[:500],
        )
    )
    db.flush()


def _ensure_exists(db: Session, model, entity_id: int | None, label: str) -> None:
    if entity_id is None:
        return
    if db.get(model, entity_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{label} с id={entity_id} не найден",
        )


def template_fields(db: Session) -> list[models.TemplateField]:
    return list(
        db.scalars(
            select(models.TemplateField).order_by(
                models.TemplateField.position, models.TemplateField.id
            )
        ).all()
    )


def item_values(db: Session, item: models.Item) -> dict:
    result = {}
    for field in template_fields(db):
        if field.type in ("sources", "repairs", "relations"):
            continue
        if field.key in schemas.BUILTIN_COLUMNS:
            result[field.key] = getattr(item, field.key)
        else:
            result[field.key] = (item.data or {}).get(field.key)
    return result


def item_to_dict(db: Session, item: models.Item) -> dict:
    return schemas.ItemOut.model_validate(item).model_dump() | {
        "values": item_values(db, item)
    }


def _coerce(field: models.TemplateField, value) -> object:
    kind = field.type
    if kind in ("text", "textarea"):
        if isinstance(value, dict):
            return ""
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value)
        return "" if value is None else str(value).strip()[:4000]
    if kind == "number":
        if value is None or value == "":
            return None
        try:
            text = str(value)
            return float(text) if "." in text else int(text)
        except (TypeError, ValueError):
            return None
    if kind == "checkbox":
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)
    if kind == "enum":
        if field.multiple:
            if isinstance(value, str):
                value = [part.strip() for part in value.split(",")]
            if not isinstance(value, list):
                value = []
            return [item for item in value if item in (field.options or [])]
        if value in (field.options or []):
            return value
        if field.default_value in (field.options or []):
            return field.default_value
        return (field.options or [""])[0]
    return value


def _normalize_builtin(key: str, value):
    if key in ("tags", "target_kinds"):
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()][:24]
        if not isinstance(value, list):
            return []
        return [str(part)[:60] for part in value][:24]
    if key in ("slot_size", "max_stack", "charges", "cooldown_seconds"):
        return None if value in (None, "") else int(value)
    if key in ("stackable", "consumed_on_use"):
        return bool(value)
    if key == "name":
        return str(value or "")[:160]
    return "" if value is None else str(value)


def _empty(value) -> bool:
    return value is None or value == "" or value == [] or value == {}


def apply_item_values(
    db: Session, item: models.Item, values: dict | None, creating: bool
) -> None:
    incoming = values or {}
    data = dict(item.data or {})
    for field in template_fields(db):
        if field.type in ("sources", "repairs", "relations"):
            continue
        if field.active and field.key in incoming:
            value = incoming[field.key]
        elif creating:
            value = field.default_value
        else:
            continue
        value = _coerce(field, value)
        if field.active and field.required and _empty(value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Поле «{field.label}» обязательно",
            )
        if field.key in schemas.BUILTIN_COLUMNS:
            setattr(item, field.key, _normalize_builtin(field.key, value))
        else:
            data[field.key] = value
    item.data = data


def _replace_nested(db: Session, item: models.Item, nested: dict) -> None:
    for key in ("sources", "repairs", "relations"):
        rows = nested.get(key)
        if rows is None:
            continue
        collection = getattr(item, key)
        collection.clear()
        db.flush()
        for row in rows:
            if key == "sources":
                _ensure_exists(db, models.Level, row.get("level_id"), "Локация")
                collection.append(models.Source(**row))
            elif key == "repairs":
                _ensure_exists(db, models.Breakage, row["breakage_id"], "Поломка")
                collection.append(models.Repair(**row))
            else:
                related_id = row["related_item_id"]
                if related_id == item.id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Предмет не может ссылаться на самого себя",
                    )
                _ensure_exists(db, models.Item, related_id, "Предмет")
                collection.append(models.ItemRelation(**row))
    db.flush()


def create_item(db: Session, payload) -> models.Item:
    data = payload.model_dump()
    nested = {key: data.pop(key) for key in ("sources", "repairs", "relations")}
    values = data.pop("values", {})
    item = models.Item(name="", author=payload.author, data={})
    db.add(item)
    apply_item_values(db, item, values, creating=True)
    _replace_nested(db, item, nested)
    log_activity(db, "item", item.id, item.name, "create", item.author, "Создан предмет")
    db.commit()
    db.refresh(item)
    return item


def update_item(db: Session, item: models.Item, payload) -> models.Item:
    if item.version != payload.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Предмет был изменён другим игроком. Обновите страницу и попробуйте снова.",
        )
    fields_set = payload.model_fields_set
    data = payload.model_dump(exclude_unset=True)
    nested = {}
    for key in ("sources", "repairs", "relations"):
        if key in data:
            nested[key] = data.pop(key)
    values = data.pop("values", None)
    apply_item_values(db, item, values, creating=False)
    if "author" in fields_set:
        item.author = payload.author
    item.version += 1
    _replace_nested(db, item, nested)
    author = payload.author if "author" in fields_set else "Аноним"
    log_activity(db, "item", item.id, item.name, "update", author, "Обновлён предмет")
    db.commit()
    db.refresh(item)
    return item


def create_simple(db: Session, model, payload: BaseModel):
    obj = model(**payload.model_dump())
    db.add(obj)
    db.flush()
    entity_type = model.__tablename__.rstrip("s")
    log_activity(db, entity_type, obj.id, obj.name, "create", obj.author, "Создана запись")
    db.commit()
    db.refresh(obj)
    return obj


def update_simple(db: Session, obj, payload: BaseModel):
    if obj.version != payload.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Запись была изменена другим игроком. Обновите страницу и попробуйте снова.",
        )
    fields_set = payload.model_fields_set
    data = payload.model_dump(exclude_unset=True)
    data.pop("version", None)
    for field, value in data.items():
        setattr(obj, field, value)
    if "author" in fields_set:
        obj.author = payload.author
    obj.version += 1
    entity_type = type(obj).__tablename__.rstrip("s")
    author = payload.author if "author" in fields_set else "Аноним"
    log_activity(db, entity_type, obj.id, obj.name, "update", author, "Обновлена запись")
    db.commit()
    db.refresh(obj)
    return obj


def delete_entity(db: Session, obj, entity_type: str) -> None:
    entity_id = obj.id
    name = getattr(obj, "name", "")
    author = getattr(obj, "author", "Аноним") or "Аноним"
    db.delete(obj)
    log_activity(db, entity_type, entity_id, name, "delete", author, "Запись удалена")
    db.commit()


def create_template_field(db: Session, payload) -> models.TemplateField:
    exists = db.scalar(
        select(models.TemplateField.id).where(models.TemplateField.key == payload.key)
    )
    if exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Такое поле уже есть"
        )
    obj = models.TemplateField(**payload.model_dump(), system=False)
    db.add(obj)
    db.flush()
    log_activity(
        db, "field", obj.id, obj.label, "create", obj.author, "Добавлено поле шаблона"
    )
    db.commit()
    db.refresh(obj)
    return obj


def update_template_field(db: Session, obj, payload) -> models.TemplateField:
    if obj.version != payload.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Шаблон изменился. Обновите страницу.",
        )
    data = payload.model_dump(exclude_unset=True)
    data.pop("version", None)
    for key, value in data.items():
        setattr(obj, key, value)
    obj.version += 1
    author = payload.author if "author" in payload.model_fields_set else "Аноним"
    log_activity(
        db, "field", obj.id, obj.label, "update", author, "Изменено поле шаблона"
    )
    db.commit()
    db.refresh(obj)
    return obj


def delete_template_field(db: Session, obj) -> None:
    if obj.system:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Встроенное поле можно только отключить",
        )
    name = obj.label
    author = obj.author
    db.delete(obj)
    log_activity(db, "field", obj.id, name, "delete", author, "Удалено поле шаблона")
    db.commit()


def reorder_template(db: Session, ids: list[int]) -> list[models.TemplateField]:
    fields = template_fields(db)
    known = {field.id: field for field in fields}
    position = 0
    for field_id in ids:
        if field_id in known:
            known[field_id].position = position
            known.pop(field_id)
            position += 1
    for field in known.values():
        field.position = position
        position += 1
    db.commit()
    return template_fields(db)
