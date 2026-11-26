from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Text, cast, func, or_, select
from sqlalchemy.orm import Session

from .. import models, schemas, services
from ..db import get_db

router = APIRouter(prefix="/items", tags=["items"])


@router.get("", response_model=schemas.Page[schemas.ItemOut])
def list_items(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=200),
    category: str | None = None,
    usage_mode: str | None = None,
    tag: str | None = None,
    level_id: int | None = None,
    breakage_id: int | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
):
    query = select(models.Item).order_by(models.Item.updated_at.desc())

    if category:
        query = query.where(models.Item.category == category)
    if usage_mode:
        query = query.where(models.Item.usage_mode == usage_mode)
    if level_id:
        query = query.join(models.Source).where(models.Source.level_id == level_id)
    if breakage_id:
        query = query.join(models.Repair).where(models.Repair.breakage_id == breakage_id)
    if tag:
        query = query.where(
            func.casefold(cast(models.Item.tags, Text)).contains(tag.strip().casefold())
        )
    if search:
        pattern = f"%{search.strip().casefold()}%"
        query = query.where(
            or_(
                func.casefold(models.Item.name).like(pattern),
                func.casefold(models.Item.tags).like(pattern),
                func.casefold(models.Item.description).like(pattern),
                func.casefold(models.Item.data).like(pattern),
            )
        )

    total = len(db.scalars(query).all())
    items = db.scalars(query.offset((page - 1) * limit).limit(limit)).all()
    return {
        "items": [services.item_to_dict(db, item) for item in items],
        "total": total,
        "page": page,
        "limit": limit,
    }


@router.get("/{item_id}", response_model=schemas.ItemOut)
def get_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(models.Item, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Предмет не найден")
    return services.item_to_dict(db, item)


@router.post("", response_model=schemas.ItemOut, status_code=status.HTTP_201_CREATED)
def add_item(payload: schemas.ItemCreate, db: Session = Depends(get_db)):
    return services.item_to_dict(db, services.create_item(db, payload))


@router.patch("/{item_id}", response_model=schemas.ItemOut)
def edit_item(
    item_id: int, payload: schemas.ItemUpdate, db: Session = Depends(get_db)
):
    item = db.get(models.Item, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Предмет не найден")
    return services.item_to_dict(db, services.update_item(db, item, payload))


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(models.Item, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Предмет не найден")
    services.delete_entity(db, item, "item")
