def test_health_meta_and_default_template(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    meta = client.get("/api/meta").json()
    assert "tool" in meta["categories"]
    assert meta["counts"]["items"] == 0
    assert meta["counts"]["fields"] == 20
    fields = client.get("/api/template").json()
    assert [field["key"] for field in fields][:2] == ["name", "category"]
    assert all(field["system"] for field in fields)


def _create_dependencies(client):
    level = client.post("/api/levels", json={"name": "Завод", "author": "Маша"}).json()
    breakage = client.post(
        "/api/breakages", json={"name": "Сломанный вентиль", "author": "Петя"}
    ).json()
    return level, breakage


def test_item_values_defaults_and_custom_fields(client):
    created_field = client.post(
        "/api/template",
        json={
            "key": "rarity", "label": "Редкость", "type": "enum",
            "options": ["common", "rare"], "default_value": "common",
            "position": 20, "author": "Аня"
        },
    )
    assert created_field.status_code == 201, created_field.text

    created = client.post(
        "/api/items",
        json={
            "author": "Вася",
            "values": {
                "name": "Гаечный ключ", "category": "tool", "tags": "ремонт, металл",
                "usage_mode": "both", "target_kinds": ["breakage", "surface"],
                "slot_size": 2, "rarity": "rare"
            },
        },
    )
    assert created.status_code == 201, created.text
    item = created.json()
    assert item["values"]["rarity"] == "rare"
    assert item["values"]["tags"] == ["ремонт", "металл"]
    assert item["values"]["category"] == "tool"

    hidden = client.get("/api/template").json()
    rarity = next(field for field in hidden if field["key"] == "rarity")
    changed = client.patch(
        f"/api/template/{rarity['id']}",
        json={"version": rarity["version"], "active": False, "author": "Аня"},
    )
    assert changed.status_code == 200, changed.text

    second = client.post(
        "/api/items",
        json={"author": "Вася", "values": {"name": "Отвёртка"}},
    )
    assert second.status_code == 201, second.text
    assert second.json()["values"]["rarity"] == "common"
    assert second.json()["values"]["category"] == "other"


def test_item_with_relations_and_filters(client):
    level, breakage = _create_dependencies(client)
    payload = {
        "author": "Вася",
        "values": {
            "name": "Гаечный ключ", "category": "tool", "tags": ["ремонт", "металл"],
            "usage_mode": "both", "target_kinds": ["breakage", "surface"], "slot_size": 2
        },
        "sources": [
            {"kind": "ground", "level_id": level["id"], "chance": 0.3},
            {"kind": "other", "conditions": "за.success"},
        ],
        "repairs": [{"breakage_id": breakage["id"], "method": "targeted", "target": "вентиль"}],
    }
    created = client.post("/api/items", json=payload)
    assert created.status_code == 201, created.text
    item = created.json()
    assert item["version"] == 1
    assert len(item["sources"]) == 2
    assert item["repairs"][0]["breakage_id"] == breakage["id"]

    assert client.get("/api/items", params={"category": "tool"}).json()["total"] == 1
    assert client.get("/api/items", params={"source_kind": "other"}).json()["total"] == 1
    assert client.get("/api/items", params={"level_id": level["id"]}).json()["total"] == 1
    assert client.get("/api/items", params={"breakage_id": breakage["id"]}).json()["total"] == 1
    assert client.get("/api/items", params={"search": "гаечный"}).json()["total"] == 1
    assert client.get("/api/items", params={"tag": "металл"}).json()["total"] == 1


def test_optimistic_lock_and_activity(client):
    created = client.post(
        "/api/items", json={"author": "Вася", "values": {"name": "Фонарик"}}
    ).json()
    stale = client.patch(
        f"/api/items/{created['id']}",
        json={"version": 0, "values": {"description": "старая версия"}, "author": "Петя"},
    )
    assert stale.status_code == 409

    updated = client.patch(
        f"/api/items/{created['id']}",
        json={
            "version": created["version"],
            "values": {"description": "новое"},
            "author": "Петя",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == 2
    assert updated.json()["values"]["description"] == "новое"

    activity = client.get("/api/activity").json()
    assert [row["action"] for row in activity] == ["update", "create"]
    assert activity[0]["author"] == "Петя"


def test_template_crud_and_reorder(client):
    fields = client.get("/api/template").json()
    system = next(field for field in fields if field["key"] == "name")
    denied = client.delete(f"/api/template/{system['id']}")
    assert denied.status_code == 400

    updated = client.patch(
        f"/api/template/{system['id']}",
        json={"version": system["version"], "label": "Имя предмета", "author": "Аня"},
    )
    assert updated.status_code == 200
    assert updated.json()["label"] == "Имя предмета"

    added = client.post(
        "/api/template",
        json={"key": "condition", "label": "Состояние", "type": "text", "position": 20},
    )
    assert added.status_code == 201
    field_id = added.json()["id"]
    assert client.delete(f"/api/template/{field_id}").status_code == 204

    ids = [field["id"] for field in client.get("/api/template").json()]
    ids.reverse()
    reordered = client.post("/api/template/reorder", json={"ids": ids})
    assert reordered.status_code == 200
    assert [field["id"] for field in reordered.json()] == ids


def test_export_import_replace(client):
    item = client.post(
        "/api/items", json={"author": "Вася", "values": {"name": "Ключ"}}
    ).json()
    exported = client.get("/api/export").json()
    assert len(exported["items"]) == 1
    assert len(exported["template"]) == 20

    assert client.post("/api/import", json={"data": exported}).status_code == 400
    restored = client.post("/api/import", json={"replace": True, "data": exported})
    assert restored.status_code == 200, restored.text
    assert restored.json()["imported"]["items"] == 1

    items = client.get("/api/items").json()
    assert items["total"] == 1
    assert items["items"][0]["id"] == item["id"]
    assert items["items"][0]["name"] == "Ключ"
    assert len(client.get("/api/template").json()) == 20


def test_validation_and_not_found(client):
    assert client.post("/api/items", json={"author": "Вася", "values": {"name": "   "}}).status_code == 400
    assert client.post("/api/template", json={"key": "Плохой ключ", "label": "Поле", "type": "text"}).status_code == 422
    assert client.get("/api/items/999").status_code == 404
    created = client.post(
        "/api/items",
        json={"author": "Вася", "values": {"name": "Предмет"}, "repairs": [{"breakage_id": 123}]},
    )
    assert created.status_code == 400, created.text
