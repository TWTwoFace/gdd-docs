from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from .. import models, schemas, services
from ..db import get_db

router = APIRouter(tags=["system"])


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/health")
def health():
    return {"status": "ok"}


def _template_options(db: Session, key: str, fallback: list[str]) -> list[str]:
    field = db.scalar(
        select(models.TemplateField).where(
            models.TemplateField.key == key, models.TemplateField.active.is_(True)
        )
    )
    return list(field.options) if field and field.options else fallback


@router.get("/meta", response_model=schemas.MetaOut)
def meta(db: Session = Depends(get_db)):
    tags: set[str] = set()
    for values in db.scalars(select(models.Item.tags)).all():
        tags.update(value for value in values if isinstance(value, str))
    counts = {
        "items": db.scalar(select(func.count(models.Item.id))) or 0,
        "breakages": db.scalar(select(func.count(models.Breakage.id))) or 0,
        "levels": db.scalar(select(func.count(models.Level.id))) or 0,
        "fields": db.scalar(select(func.count(models.TemplateField.id))) or 0,
        "activity": db.scalar(select(func.count(models.Activity.id))) or 0,
    }
    return schemas.MetaOut(
        categories=_template_options(db, "category", schemas.CATEGORIES),
        usage_modes=_template_options(db, "usage_mode", schemas.USAGE_MODES),
        source_kinds=schemas.SOURCE_KINDS,
        repair_methods=schemas.REPAIR_METHODS,
        relation_kinds=schemas.RELATION_KINDS,
        target_kinds=_template_options(db, "target_kinds", schemas.TARGET_KINDS),
        tags=sorted(tags),
        counts=counts,
    )


@router.get("/activity", response_model=list[schemas.ActivityOut])
def activity(
    limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)
):
    return db.scalars(
        select(models.Activity).order_by(models.Activity.id.desc()).limit(limit)
    ).all()


@router.get("/export")
def export_data(db: Session = Depends(get_db)):
    items = db.scalars(
        select(models.Item).options(
            selectinload(models.Item.sources),
            selectinload(models.Item.repairs),
            selectinload(models.Item.relations),
        )
    ).all()
    payload = schemas.ExportPayload(
        exported_at=utcnow(),
        items=[services.item_to_dict(db, i) for i in items],
        breakages=[
            schemas.BreakageOut.model_validate(o).model_dump(mode="json")
            for o in db.scalars(select(models.Breakage)).all()
        ],
        levels=[
            schemas.LevelOut.model_validate(o).model_dump(mode="json")
            for o in db.scalars(select(models.Level)).all()
        ],
        template=[
            schemas.TemplateFieldOut.model_validate(o).model_dump(mode="json")
            for o in services.template_fields(db)
        ],
        sources=[
            schemas.SourceOut.model_validate(o).model_dump(mode="json")
            for o in db.scalars(select(models.Source)).all()
        ],
        repairs=[
            schemas.RepairOut.model_validate(o).model_dump(mode="json")
            for o in db.scalars(select(models.Repair)).all()
        ],
        relations=[
            schemas.RelationOut.model_validate(o).model_dump(mode="json")
            for o in db.scalars(select(models.ItemRelation)).all()
        ],
    )
    return payload.model_dump(mode="json")


def _timestamps(raw: dict) -> dict:
    result = {}
    for key in ("created_at", "updated_at"):
        value = raw.get(key)
        if value:
            try:
                result[key] = datetime.fromisoformat(value)
            except (TypeError, ValueError):
                pass
    return result


def _rows(data: dict, key: str) -> list[dict]:
    value = data.get(key, [])
    if not isinstance(value, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Поле {key} должно быть списком",
        )
    return value


def _item_attrs(raw: dict) -> dict:
    attrs = {key: raw.get(key) for key in schemas.BUILTIN_COLUMNS if key in raw}
    data = dict(raw.get("data") or {})
    for key, value in (raw.get("values") or {}).items():
        if key in schemas.BUILTIN_COLUMNS:
            attrs[key] = value
        else:
            data[key] = value
    attrs["data"] = data
    attrs.setdefault("name", "")
    return attrs


@router.post("/import")
def import_data(payload: schemas.ImportPayload, db: Session = Depends(get_db)):
    if not payload.replace:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Импорт заменяет базу. Установите replace=true для подтверждения.",
        )
    data = payload.data
    if data.get("format") not in (None, "itemdatabase"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Неизвестный формат файла"
        )

    lists = {
        key: _rows(data, key)
        for key in (
            "items", "breakages", "levels", "template", "sources", "repairs", "relations"
        )
    }

    for model in (
        models.Activity,
        models.Source,
        models.Repair,
        models.ItemRelation,
        models.Item,
        models.TemplateField,
        models.Breakage,
        models.Level,
    ):
        db.execute(delete(model))
    db.flush()

    def add_rows(model, schema, rows, extra=lambda raw: {}):
        for raw in rows:
            parsed = schema.model_validate(raw)
            attrs = parsed.model_dump()
            for nested_key in ("sources", "repairs", "relations"):
                attrs.pop(nested_key, None)
            attrs.update(extra(raw))
            attrs.update(_timestamps(raw))
            if "id" in raw and isinstance(raw["id"], int):
                attrs["id"] = raw["id"]
            if "version" in raw and isinstance(raw["version"], int):
                attrs["version"] = raw["version"]
            elif hasattr(model, "version"):
                attrs["version"] = 1
            db.add(model(**attrs))

    add_rows(models.Level, schemas.LevelCreate, lists["levels"])
    add_rows(models.Breakage, schemas.BreakageCreate, lists["breakages"])
    for raw in lists["items"]:
        attrs = _item_attrs(raw)
        attrs.update(_timestamps(raw))
        if isinstance(raw.get("id"), int):
            attrs["id"] = raw["id"]
        attrs["version"] = raw.get("version") if isinstance(raw.get("version"), int) else 1
        db.add(models.Item(**attrs))
    if lists["template"]:
        for raw in lists["template"]:
            attrs = {
                key: raw[key]
                for key in (
                    "key", "label", "type", "options", "default_value", "required",
                    "multiple", "active", "position", "system", "author",
                )
                if key in raw
            }
            attrs.update(_timestamps(raw))
            db.add(models.TemplateField(**attrs))
    else:
        from ..template import DEFAULT_FIELDS

        for position, definition in enumerate(DEFAULT_FIELDS):
            attrs = dict(definition)
            attrs.setdefault("options", [])
            attrs.setdefault("default_value", None)
            attrs.setdefault("required", False)
            attrs.setdefault("multiple", False)
            attrs.setdefault("active", True)
            attrs["system"] = True
            attrs["position"] = position
            attrs["author"] = "система"
            db.add(models.TemplateField(**attrs))
    add_rows(
        models.Source,
        schemas.SourceCreate,
        lists["sources"],
        lambda raw: {"item_id": raw["item_id"]},
    )
    add_rows(
        models.Repair,
        schemas.RepairCreate,
        lists["repairs"],
        lambda raw: {"item_id": raw["item_id"]},
    )
    add_rows(
        models.ItemRelation,
        schemas.RelationCreate,
        lists["relations"],
        lambda raw: {"item_id": raw["item_id"]},
    )

    db.add(
        models.Activity(
            entity_type="system",
            entity_id=0,
            entity_name="База данных",
            action="import",
            author="Импорт",
            details=f"Восстановлено предметов: {len(lists['items'])}",
        )
    )
    db.commit()
    return {
        "ok": True,
        "imported": {key: len(value) for key, value in lists.items()},
    }
