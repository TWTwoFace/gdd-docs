from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import models, schemas, services
from ..db import get_db

router = APIRouter(tags=["entities"])


def _list(db: Session, model, page: int, limit: int, search: str | None):
    query = select(model).order_by(model.updated_at.desc())
    if search:
        pattern = f"%{search.strip().casefold()}%"
        query = query.where(
            or_(
                func.casefold(model.name).like(pattern),
                func.casefold(model.description).like(pattern),
            )
        )
    total = len(db.scalars(query).all())
    rows = db.scalars(query.offset((page - 1) * limit).limit(limit)).all()
    return rows, total


@router.get("/breakages", response_model=schemas.Page[schemas.BreakageOut])
def list_breakages(
    page: int = 1,
    limit: int = 20,
    search: str | None = None,
    db: Session = Depends(get_db),
):
    rows, total = _list(db, models.Breakage, page, limit, search)
    return {"items": rows, "total": total, "page": page, "limit": limit}


@router.get("/breakages/{entity_id}", response_model=schemas.BreakageOut)
def get_breakage(entity_id: int, db: Session = Depends(get_db)):
    obj = db.get(models.Breakage, entity_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Поломка не найдена")
    return obj


@router.post("/breakages", response_model=schemas.BreakageOut, status_code=201)
def add_breakage(payload: schemas.BreakageCreate, db: Session = Depends(get_db)):
    return services.create_simple(db, models.Breakage, payload)


@router.patch("/breakages/{entity_id}", response_model=schemas.BreakageOut)
def edit_breakage(
    entity_id: int, payload: schemas.BreakageUpdate, db: Session = Depends(get_db)
):
    obj = db.get(models.Breakage, entity_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Поломка не найдена")
    return services.update_simple(db, obj, payload)


@router.delete("/breakages/{entity_id}", status_code=204)
def remove_breakage(entity_id: int, db: Session = Depends(get_db)):
    obj = db.get(models.Breakage, entity_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Поломка не найдена")
    services.delete_entity(db, obj, "breakage")


@router.get("/levels", response_model=schemas.Page[schemas.LevelOut])
def list_levels(
    page: int = 1,
    limit: int = 20,
    search: str | None = None,
    db: Session = Depends(get_db),
):
    rows, total = _list(db, models.Level, page, limit, search)
    return {"items": rows, "total": total, "page": page, "limit": limit}


@router.get("/levels/{entity_id}", response_model=schemas.LevelOut)
def get_level(entity_id: int, db: Session = Depends(get_db)):
    obj = db.get(models.Level, entity_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Локация не найдена")
    return obj


@router.post("/levels", response_model=schemas.LevelOut, status_code=201)
def add_level(payload: schemas.LevelCreate, db: Session = Depends(get_db)):
    return services.create_simple(db, models.Level, payload)


@router.patch("/levels/{entity_id}", response_model=schemas.LevelOut)
def edit_level(
    entity_id: int, payload: schemas.LevelUpdate, db: Session = Depends(get_db)
):
    obj = db.get(models.Level, entity_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Локация не найдена")
    return services.update_simple(db, obj, payload)


@router.delete("/levels/{entity_id}", status_code=204)
def remove_level(entity_id: int, db: Session = Depends(get_db)):
    obj = db.get(models.Level, entity_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Локация не найдена")
    services.delete_entity(db, obj, "level")
