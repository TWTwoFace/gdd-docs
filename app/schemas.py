import re
from datetime import datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

CATEGORIES = ["tool", "consumable", "key", "material", "weapon", "junk", "other"]
USAGE_MODES = ["none", "simple", "targeted", "both"]
SOURCE_KINDS = ["ground", "other"]
REPAIR_METHODS = ["simple", "targeted"]
RELATION_KINDS = ["requires", "combines_with", "upgrade_of"]
TARGET_KINDS = ["breakage", "surface", "machine", "player", "item", "any"]
FIELD_TYPES = [
    "text", "textarea", "enum", "number", "checkbox",
    "sources", "repairs", "relations",
]


def clean_text(value: Any) -> str:
    return " ".join(str(value).split())


def clean_author(value: Any) -> str:
    result = clean_text(value or "")
    return result[:80] or "Аноним"


def clean_tags(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [part for part in value.split(",")]
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for tag in value:
        text = clean_text(tag)
        if text and text not in result:
            result.append(text[:60])
    return result[:24]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Authored(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    author: str = Field(default="Аноним", max_length=80)

    @field_validator("author", mode="before")
    @classmethod
    def _author(cls, value: Any) -> str:
        return clean_author(value)


class Named(Authored):
    name: str = Field(min_length=1, max_length=160)

    @field_validator("name", mode="before")
    @classmethod
    def _name(cls, value: Any) -> str:
        result = clean_text(value or "")
        if not result:
            raise ValueError("Название не может быть пустым")
        return result


class SourceBase(ORMModel):
    kind: Literal["ground", "other"] = "ground"
    level_id: int | None = None
    chance: float | None = Field(default=None, ge=0, le=1)
    conditions: str = ""
    notes: str = ""


class SourceCreate(SourceBase):
    pass


class SourceOut(SourceBase):
    id: int
    item_id: int
    author: str
    created_at: datetime
    updated_at: datetime


class RepairBase(ORMModel):
    breakage_id: int
    method: Literal["simple", "targeted"] = "targeted"
    target: str = ""
    steps: str = ""
    notes: str = ""

    @field_validator("breakage_id")
    @classmethod
    def _positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("Выберите поломку")
        return value


class RepairCreate(RepairBase):
    pass


class RepairOut(RepairBase):
    id: int
    item_id: int
    author: str
    created_at: datetime
    updated_at: datetime


class RelationBase(ORMModel):
    related_item_id: int
    kind: Literal["requires", "combines_with", "upgrade_of"] = "requires"
    notes: str = ""


class RelationCreate(RelationBase):
    pass


class RelationOut(RelationBase):
    id: int
    item_id: int
    author: str
    created_at: datetime
    updated_at: datetime


class TemplateFieldBase(ORMModel):
    key: str = Field(min_length=1, max_length=60)
    label: str = Field(min_length=1, max_length=160)
    type: Literal[
        "text", "textarea", "enum", "number", "checkbox",
        "sources", "repairs", "relations",
    ]
    options: list[str] = Field(default_factory=list)
    default_value: Any | None = None
    required: bool = False
    multiple: bool = False
    active: bool = True
    position: int = 0

    @field_validator("key", mode="before")
    @classmethod
    def _key(cls, value: Any) -> str:
        result = clean_text(value or "").lower().replace("-", "_").replace(" ", "_")
        if not re.fullmatch(r"[a-z][a-z0-9_]*", result):
            raise ValueError("Ключ: только латиница, цифры и подчёркивание")
        return result

    @field_validator("label", mode="before")
    @classmethod
    def _label(cls, value: Any) -> str:
        result = clean_text(value or "")
        if not result:
            raise ValueError("Укажите название поля")
        return result

    @field_validator("options", mode="before")
    @classmethod
    def _options(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            value = value.split(",")
        if not isinstance(value, list):
            return []
        result = []
        for option in value:
            text = clean_text(option)
            if text and text not in result:
                result.append(text[:120])
        return result[:60]


class TemplateFieldCreate(TemplateFieldBase):
    pass


class TemplateFieldUpdate(Authored):
    version: int
    label: str | None = Field(default=None, min_length=1, max_length=160)
    options: list[str] | None = None
    default_value: Any | None = None
    required: bool | None = None
    multiple: bool | None = None
    active: bool | None = None
    position: int | None = None

    @field_validator("label", mode="before")
    @classmethod
    def _label(cls, value: Any) -> Any:
        if value is None:
            return None
        result = clean_text(value)
        if not result:
            raise ValueError("Укажите название поля")
        return result

    @field_validator("options", mode="before")
    @classmethod
    def _options(cls, value: Any) -> Any:
        return None if value is None else TemplateFieldBase._options(value)


class TemplateFieldOut(TemplateFieldBase):
    id: int
    system: bool
    version: int
    author: str
    created_at: datetime
    updated_at: datetime


class TemplateReorder(BaseModel):
    ids: list[int]


class ItemCreate(Authored):
    values: dict[str, Any] = Field(default_factory=dict)
    sources: list[SourceCreate] = Field(default_factory=list)
    repairs: list[RepairCreate] = Field(default_factory=list)
    relations: list[RelationCreate] = Field(default_factory=list)


class ItemUpdate(Authored):
    version: int
    values: dict[str, Any] | None = None
    sources: list[SourceCreate] | None = None
    repairs: list[RepairCreate] | None = None
    relations: list[RelationCreate] | None = None


BUILTIN_COLUMNS = [
    "name", "description", "category", "tags", "color", "icon", "notes",
    "slot_size", "stackable", "max_stack", "usage_mode", "target_kinds",
    "effect", "consumed_on_use", "charges", "cooldown_seconds", "requirements",
]


class ItemOut(Authored):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    category: str
    tags: list[str]
    color: str
    icon: str
    notes: str
    slot_size: int
    stackable: bool
    max_stack: int
    usage_mode: str
    target_kinds: list[str]
    effect: str
    consumed_on_use: bool
    charges: int | None
    cooldown_seconds: int
    requirements: str
    data: dict[str, Any] = Field(default_factory=dict)
    values: dict[str, Any] = Field(default_factory=dict)
    version: int
    created_at: datetime
    updated_at: datetime
    sources: list[SourceOut] = Field(default_factory=list)
    repairs: list[RepairOut] = Field(default_factory=list)
    relations: list[RelationOut] = Field(default_factory=list)


class BreakageFields(Named):
    description: str = ""
    symptoms: str = ""
    difficulty: int = Field(default=1, ge=1, le=5)
    repair_seconds: int = Field(default=0, ge=0)
    required_tools: str = ""
    notes: str = ""


class BreakageCreate(BreakageFields):
    pass


class BreakageUpdate(Authored):
    version: int
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None
    symptoms: str | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    repair_seconds: int | None = Field(default=None, ge=0)
    required_tools: str | None = None
    notes: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def _name(cls, value: Any) -> Any:
        if value is None:
            return None
        result = clean_text(value)
        if not result:
            raise ValueError("Название не может быть пустым")
        return result


class BreakageOut(BreakageFields):
    id: int
    version: int
    created_at: datetime
    updated_at: datetime


class LevelFields(Named):
    description: str = ""
    biome: str = ""
    generation_rules: str = ""
    notes: str = ""


class LevelCreate(LevelFields):
    pass


class LevelUpdate(Authored):
    version: int
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None
    biome: str | None = None
    generation_rules: str | None = None
    notes: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def _name(cls, value: Any) -> Any:
        if value is None:
            return None
        result = clean_text(value)
        if not result:
            raise ValueError("Название не может быть пустым")
        return result


class LevelOut(LevelFields):
    id: int
    version: int
    created_at: datetime
    updated_at: datetime


class ActivityOut(ORMModel):
    id: int
    entity_type: str
    entity_id: int
    entity_name: str
    action: str
    author: str
    details: str
    created_at: datetime


class MetaOut(BaseModel):
    categories: list[str]
    usage_modes: list[str]
    source_kinds: list[str]
    repair_methods: list[str]
    relation_kinds: list[str]
    target_kinds: list[str]
    tags: list[str]
    counts: dict[str, int]


class ExportPayload(BaseModel):
    format: str = "itemdatabase"
    version: int = 2
    exported_at: datetime
    items: list[dict[str, Any]]
    breakages: list[dict[str, Any]]
    levels: list[dict[str, Any]]
    template: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    repairs: list[dict[str, Any]]
    relations: list[dict[str, Any]]


class ImportPayload(BaseModel):
    replace: bool = False
    data: dict[str, Any]


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    limit: int
