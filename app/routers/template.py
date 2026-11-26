from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas, services
from ..db import get_db

router = APIRouter(prefix="/template", tags=["template"])


@router.get("", response_model=list[schemas.TemplateFieldOut])
def list_template(db: Session = Depends(get_db)):
    return services.template_fields(db)


@router.post("", response_model=schemas.TemplateFieldOut, status_code=201)
def add_template_field(
    payload: schemas.TemplateFieldCreate, db: Session = Depends(get_db)
):
    return services.create_template_field(db, payload)


@router.post("/reorder", response_model=list[schemas.TemplateFieldOut])
def reorder_template(payload: schemas.TemplateReorder, db: Session = Depends(get_db)):
    return services.reorder_template(db, payload.ids)


@router.patch("/{field_id}", response_model=schemas.TemplateFieldOut)
def edit_template_field(
    field_id: int, payload: schemas.TemplateFieldUpdate, db: Session = Depends(get_db)
):
    field = db.get(models.TemplateField, field_id)
    if field is None:
        raise HTTPException(status_code=404, detail="Поле шаблона не найдено")
    return services.update_template_field(db, field, payload)


@router.delete("/{field_id}", status_code=204)
def remove_template_field(field_id: int, db: Session = Depends(get_db)):
    field = db.get(models.TemplateField, field_id)
    if field is None:
        raise HTTPException(status_code=404, detail="Поле шаблона не найдено")
    services.delete_template_field(db, field)
