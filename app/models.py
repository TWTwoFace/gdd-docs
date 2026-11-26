from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BaseEntity(Base):
    __abstract__ = True

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author: Mapped[str] = mapped_column(String(80), default="Аноним")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Versioned(BaseEntity):
    __abstract__ = True
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class Item(Versioned):
    __tablename__ = "items"

    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(40), default="other")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    color: Mapped[str] = mapped_column(String(16), default="#5b8cff")
    icon: Mapped[str] = mapped_column(String(32), default="")
    notes: Mapped[str] = mapped_column(Text, default="")

    slot_size: Mapped[int] = mapped_column(Integer, default=1)
    stackable: Mapped[bool] = mapped_column(Boolean, default=False)
    max_stack: Mapped[int] = mapped_column(Integer, default=1)

    usage_mode: Mapped[str] = mapped_column(String(20), default="simple")
    target_kinds: Mapped[list[str]] = mapped_column(JSON, default=list)
    effect: Mapped[str] = mapped_column(Text, default="")
    consumed_on_use: Mapped[bool] = mapped_column(Boolean, default=False)
    charges: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=0)
    requirements: Mapped[str] = mapped_column(Text, default="")
    data: Mapped[dict] = mapped_column(JSON, default=dict)

    sources: Mapped[list["Source"]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )
    repairs: Mapped[list["Repair"]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )
    relations: Mapped[list["ItemRelation"]] = relationship(
        back_populates="item",
        foreign_keys="ItemRelation.item_id",
        cascade="all, delete-orphan",
    )


class Breakage(Versioned):
    __tablename__ = "breakages"

    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    symptoms: Mapped[str] = mapped_column(Text, default="")
    difficulty: Mapped[int] = mapped_column(Integer, default=1)
    repair_seconds: Mapped[int] = mapped_column(Integer, default=0)
    required_tools: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")

    repairs: Mapped[list["Repair"]] = relationship(
        back_populates="breakage", cascade="all, delete-orphan"
    )


class Level(Versioned):
    __tablename__ = "levels"

    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    biome: Mapped[str] = mapped_column(String(80), default="")
    generation_rules: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")

    sources: Mapped[list["Source"]] = relationship(
        back_populates="level", cascade="all, delete-orphan"
    )


class Source(BaseEntity):
    __tablename__ = "sources"

    item_id: Mapped[int] = mapped_column(
        ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(20), default="ground")
    level_id: Mapped[int | None] = mapped_column(
        ForeignKey("levels.id", ondelete="SET NULL"), nullable=True
    )
    chance: Mapped[float | None] = mapped_column(Float, nullable=True)
    conditions: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")

    item: Mapped["Item"] = relationship(back_populates="sources")
    level: Mapped["Level | None"] = relationship(back_populates="sources")


class Repair(BaseEntity):
    __tablename__ = "repairs"
    __table_args__ = (UniqueConstraint("item_id", "breakage_id", name="uq_repair"),)

    item_id: Mapped[int] = mapped_column(
        ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    breakage_id: Mapped[int] = mapped_column(
        ForeignKey("breakages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    method: Mapped[str] = mapped_column(String(20), default="targeted")
    target: Mapped[str] = mapped_column(Text, default="")
    steps: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")

    item: Mapped["Item"] = relationship(back_populates="repairs")
    breakage: Mapped["Breakage"] = relationship(back_populates="repairs")


class ItemRelation(BaseEntity):
    __tablename__ = "item_relations"
    __table_args__ = (
        UniqueConstraint("item_id", "related_item_id", "kind", name="uq_item_relation"),
    )

    item_id: Mapped[int] = mapped_column(
        ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    related_item_id: Mapped[int] = mapped_column(
        ForeignKey("items.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(30), default="requires")
    notes: Mapped[str] = mapped_column(Text, default="")

    item: Mapped["Item"] = relationship(
        back_populates="relations", foreign_keys=[item_id]
    )
    related_item: Mapped["Item"] = relationship(foreign_keys=[related_item_id])


class TemplateField(Versioned):
    __tablename__ = "template_fields"
    __table_args__ = (UniqueConstraint("key", name="uq_template_field"),)

    key: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    options: Mapped[list[str]] = mapped_column(JSON, default=list)
    default_value: Mapped[object] = mapped_column(JSON, default=None)
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    multiple: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    system: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[int] = mapped_column(Integer, default=0)


class Activity(Base):
    __tablename__ = "activity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    entity_name: Mapped[str] = mapped_column(String(160), default="")
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    author: Mapped[str] = mapped_column(String(80), default="Аноним")
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
