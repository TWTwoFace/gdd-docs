(() => {
  "use strict";

  const STRUCTURAL = ["sources", "repairs", "relations"];
  const FIELD_TYPES = ["text", "textarea", "enum", "number", "checkbox"];
  const ALL_FIELD_TYPES = FIELD_TYPES.concat(STRUCTURAL);

  const LABELS = {
    categories: {
      tool: "Инструмент",
      consumable: "Расходник",
      key: "Ключ / доступ",
      material: "Материал",
      weapon: "Оружие",
      junk: "Мусор",
      other: "Прочее"
    },
    usage: {
      none: "Не применяется",
      simple: "Простое применение",
      targeted: "Наведение на место",
      both: "Оба варианта"
    },
    source: { ground: "Лежит на локации", other: "Другое" },
    repair: { simple: "Просто", targeted: "С наведением" },
    relation: {
      requires: "Требует",
      combines_with: "Комбинируется",
      upgrade_of: "Улучшает"
    },
    target: {
      breakage: "Поломка",
      surface: "Поверхность",
      machine: "Механизм",
      player: "Игрок",
      item: "Предмет",
      any: "Любая цель"
    },
    action: {
      create: "создал(а)",
      update: "обновил(а)",
      delete: "удалил(а)",
      import: "импортировал(а)"
    },
    entity: {
      item: "предмет",
      breakage: "поломку",
      level: "локацию",
      field: "поле шаблона",
      system: "базу"
    }
  };

  const SIMPLE = {
    breakages: {
      path: "breakages",
      title: "Поломки",
      entity: "breakage",
      fields: [
        { key: "name", label: "Название", required: true },
        { key: "description", label: "Описание", type: "textarea", full: true },
        { key: "symptoms", label: "Как проявляется", type: "textarea", full: true },
        { key: "difficulty", label: "Сложность (1-5)", type: "number", default: 1, min: 1, max: 5 },
        { key: "repair_seconds", label: "Время ремонта, сек", type: "number", default: 0, min: 0 },
        { key: "required_tools", label: "Нужные инструменты", type: "textarea", full: true },
        { key: "notes", label: "Заметки", type: "textarea", full: true }
      ]
    },
    levels: {
      path: "levels",
      title: "Локации",
      entity: "level",
      fields: [
        { key: "name", label: "Название", required: true },
        { key: "biome", label: "Биом / тип" },
        { key: "description", label: "Описание", type: "textarea", full: true },
        { key: "generation_rules", label: "Правила генерации", type: "textarea", full: true },
        { key: "notes", label: "Заметки", type: "textarea", full: true }
      ]
    }
  };

  const state = {
    author: "",
    meta: null,
    template: [],
    cache: { items: [], breakages: [], levels: [] },
    renderToken: 0
  };

  const view = () => document.getElementById("view");
  const activeFields = () => state.template.filter((field) => field.active);
  const scalarFields = () => activeFields().filter((field) => !STRUCTURAL.includes(field.type));

  function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;"
    })[char]);
  }

  function fmtDate(value) {
    if (!value) return "—";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString("ru-RU");
  }

  function normalizeBase(value) {
    return String(value || "")
      .replace(/\/+$/, "")
      .replace(/^(https?:\/\/)localhost(?=[:/]|$)/, "$1127.0.0.1");
  }

  function apiBase() {
    const saved = localStorage.getItem("itemdb.apiBase");
    const configured = (window.APP_CONFIG && window.APP_CONFIG.apiBase) || "";
    const base = normalizeBase(saved || configured);
    if (base) return base;
    if (location.protocol === "http:" || location.protocol === "https:") {
      if (location.hostname.endsWith(".github.io")) return "";
      const host = location.hostname === "localhost" ? "127.0.0.1" : location.hostname;
      return "http://" + host + (location.port ? ":" + location.port : "") + "/api";
    }
    return "";
  }

  async function api(path, options = {}) {
    const base = apiBase();
    if (!base) {
      const error = new Error("Укажите адрес API на вкладке «Настройки»");
      error.status = 0;
      throw error;
    }
    const headers = Object.assign({}, options.headers || {});
    if (options.body) headers["Content-Type"] = "application/json";
    let response;
    try {
      response = await fetch(encodeURI(base + path), Object.assign({}, options, { headers }));
    } catch (cause) {
      const error = new Error("Нет связи с сервером: " + cause.message);
      error.status = 0;
      throw error;
    }
    if (!response.ok) {
      let detail = "Ошибка " + response.status;
      try {
        const body = await response.json();
        if (body.detail) {
          detail = Array.isArray(body.detail)
            ? body.detail.map((item) => item.msg || String(item)).join("; ")
            : String(body.detail);
        }
      } catch (_) {}
      const error = new Error(detail);
      error.status = response.status;
      throw error;
    }
    if (response.status === 204) return null;
    return response.json();
  }

  let toastTimer = null;
  function toast(message, isError = false) {
    const box = document.getElementById("toast");
    box.textContent = message;
    box.className = "show" + (isError ? " error" : "");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { box.className = ""; }, 4500);
  }

  function optionsHtml(list, selected, emptyLabel) {
    const entries = emptyLabel ? [{ value: "", label: emptyLabel }].concat(list) : list;
    return entries.map((entry) => (
      '<option value="' + esc(entry.value) + '"' +
      (String(entry.value) === String(selected ?? "") ? " selected" : "") +
      ">" + esc(entry.label) + "</option>"
    )).join("");
  }

  function enumOptions(map, selected, emptyLabel) {
    return optionsHtml(
      Object.keys(map).map((key) => ({ value: key, label: map[key] })),
      selected,
      emptyLabel
    );
  }

  function optionLabel(field, value) {
    const maps = {
      category: LABELS.categories,
      usage_mode: LABELS.usage,
      target_kinds: LABELS.target,
      kind: LABELS.source,
      method: LABELS.repair
    };
    const map = maps[field ? field.key : ""] || {};
    return map[value] || value;
  }

  function parseHash() {
    const raw = location.hash.replace(/^#\/?/, "");
    const [section, id, mode] = raw.split("/");
    return { section: section || "items", id: id || null, mode: mode || null };
  }

  function renderNav(section) {
    const links = [
      ["items", "Предметы"],
      ["breakages", "Поломки"],
      ["levels", "Локации"],
      ["template", "Шаблон"],
      ["activity", "История"],
      ["settings", "Настройки"]
    ];
    document.getElementById("nav").innerHTML = links.map(([key, label]) => (
      '<a href="#/' + key + '"' + (key === section ? ' class="active"' : "") + ">" +
      esc(label) + "</a>"
    )).join("");
  }

  async function checkConnection() {
    const status = document.getElementById("connStatus");
    try {
      await api("/health");
      status.textContent = "связь есть";
      status.className = "status ok";
    } catch (error) {
      status.textContent = "нет связи";
      status.className = "status bad";
    }
  }

  async function refreshCaches() {
    const [meta, items, breakages, levels, fields] = await Promise.all([
      api("/meta"),
      api("/items?limit=200"),
      api("/breakages?limit=200"),
      api("/levels?limit=200"),
      api("/template")
    ]);
    state.meta = meta;
    state.template = fields;
    state.cache = {
      items: items.items,
      breakages: breakages.items,
      levels: levels.items
    };
  }

  function showError(error) {
    view().innerHTML =
      '<div class="panel"><h2>Не удалось загрузить данные</h2><p>' +
      esc(error.message) + '</p><a class="btn" href="#/settings">Настройки подключения</a></div>';
  }

  async function render() {
    const token = ++state.renderToken;
    const { section, id, mode } = parseHash();
    renderNav(section);
    view().innerHTML = '<div class="loading">Загрузка…</div>';
    try {
      if (section === "settings") {
        renderSettings();
        return;
      }
      await refreshCaches();
      if (token !== state.renderToken) return;
      if (section === "items") {
        if (id === "new") await renderItemEditor(null);
        else if (id && mode === "edit") await renderItemEditor(Number(id));
        else if (id) await renderItemDetail(Number(id));
        else renderItems();
      } else if (section === "template") {
        renderTemplate();
      } else if (section === "activity") {
        await renderActivity();
      } else if (SIMPLE[section]) {
        if (id === "new") await renderSimpleEditor(section, null);
        else if (id && mode === "edit") await renderSimpleEditor(section, Number(id));
        else if (id) await renderSimpleDetail(section, Number(id));
        else renderSimpleList(section);
      } else {
        location.hash = "#/items";
      }
    } catch (error) {
      if (token === state.renderToken) showError(error);
    }
  }

  function renderItems() {
    const filters = state.meta;
    view().innerHTML =
      '<h1>Предметы</h1>' +
      '<p class="subtitle">Общая база: всем, кто зайдёт на сайт, видны изменения других. Поля предметов задаются на вкладке «Шаблон».</p>' +
      '<div class="toolbar">' +
        '<input data-filter="search" placeholder="Поиск по полям предмета" style="flex:2">' +
        '<select data-filter="category">' + enumOptions(filters.categories, "", "Все категории") + '</select>' +
        '<select data-filter="usage">' + enumOptions(filters.usage_modes, "", "Любое применение") + '</select>' +
        '<select data-filter="source">' + enumOptions(filters.source_kinds, "", "Любой источник") + '</select>' +
        '<select data-filter="level">' + optionsHtml(state.cache.levels.map((l) => ({ value: l.id, label: l.name })), "", "Любая локация") + '</select>' +
        '<select data-filter="breakage">' + optionsHtml(state.cache.breakages.map((b) => ({ value: b.id, label: b.name })), "", "Любая поломка") + '</select>' +
        '<select data-filter="sort"><option value="updated">Сначала обновлённые</option><option value="name">По названию</option><option value="created">Сначала новые</option></select>' +
        '<a class="btn primary" href="#/items/new">+ Новый предмет</a>' +
      '</div>' +
      '<div id="itemsGrid"></div>';
    updateItemsGrid();
  }

  function updateItemsGrid() {
    const grid = document.getElementById("itemsGrid");
    if (!grid) return;
    const value = (name) => (document.querySelector('[data-filter="' + name + '"]') || {}).value || "";
    const search = value("search").trim().toLowerCase();
    const category = value("category");
    const usage = value("usage");
    const source = value("source");
    const level = value("level");
    const breakage = value("breakage");
    const sort = value("sort") || "updated";

    let list = state.cache.items.filter((item) => {
      if (search) {
        const values = Object.values(item.values || {}).map((v) => (Array.isArray(v) ? v.join(" ") : v));
        const haystack = [item.name, item.description, item.notes].concat(values).join(" ").toLowerCase();
        if (!haystack.includes(search)) return false;
      }
      if (category && item.category !== category) return false;
      if (usage && item.usage_mode !== usage) return false;
      if (source && !(item.sources || []).some((row) => row.kind === source)) return false;
      if (level && !(item.sources || []).some((row) => String(row.level_id) === String(level))) return false;
      if (breakage && !(item.repairs || []).some((row) => String(row.breakage_id) === String(breakage))) return false;
      return true;
    });

    if (sort === "name") list.sort((a, b) => a.name.localeCompare(b.name, "ru"));
    else if (sort === "created") list.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    else list.sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));

    if (!list.length) {
      grid.innerHTML = '<div class="empty">Ничего не найдено. Попробуйте изменить фильтры или добавьте предмет.</div>';
      return;
    }
    grid.innerHTML = '<div class="grid">' + list.map(itemCard).join("") + '</div>';
  }

  function itemCard(item) {
    const categoryField = state.template.find((field) => field.key === "category");
    const usageField = state.template.find((field) => field.key === "usage_mode");
    const badges = [
      '<span class="badge accent">' + esc(optionLabel(usageField, item.usage_mode)) + '</span>'
    ];
    (item.tags || []).slice(0, 3).forEach((tag) => badges.push('<span class="badge">' + esc(tag) + '</span>'));
    if ((item.repairs || []).length) badges.push('<span class="badge ok">Чинит: ' + item.repairs.length + '</span>');
    if ((item.sources || []).length) badges.push('<span class="badge">Источников: ' + item.sources.length + '</span>');
    return '<a class="card" href="#/items/' + item.id + '">' +
      '<div class="card-head"><div class="card-dot" style="background:' + esc(item.color) + '"></div>' +
      '<div><div class="card-title">' + esc(item.name) + '</div>' +
      '<div class="card-meta">' + esc(optionLabel(categoryField, item.category)) +
      ' · ' + esc(item.author) + ' · ' + esc(fmtDate(item.updated_at)) + '</div></div></div>' +
      '<div class="card-desc">' + esc(item.description || "Описание пока не заполнено") + '</div>' +
      '<div class="badges">' + badges.join("") + '</div></a>';
  }

  function kvRow(label, value) {
    return '<dt>' + esc(label) + '</dt><dd>' + esc(value === null || value === undefined || value === "" ? "—" : value) + '</dd>';
  }

  function displayValue(field, value) {
    if (Array.isArray(value)) return value.map((item) => optionLabel(field, item)).join(", ");
    if (field && field.type === "checkbox") return value ? "да" : "нет";
    if (value === null || value === undefined || value === "") return "—";
    return optionLabel(field, value);
  }

  function sourcesList(item) {
    return (item.sources || []).map((row) => {
      const parts = [LABELS.source[row.kind] || row.kind];
      if (row.level_id) {
        const level = state.cache.levels.find((l) => l.id === row.level_id);
        parts.push(level ? level.name : "локация #" + row.level_id);
      }
      if (row.chance !== null && row.chance !== undefined) parts.push("шанс " + row.chance);
      return '<div class="list-item"><span>' + esc(parts.join(" · ")) +
        (row.conditions ? '<div class="meta">' + esc(row.conditions) + '</div>' : "") +
        (row.notes ? '<div class="meta">' + esc(row.notes) + '</div>' : "") +
        '</span></div>';
    }).join("");
  }

  function repairsList(item) {
    return (item.repairs || []).map((row) => {
      const found = state.cache.breakages.find((b) => b.id === row.breakage_id);
      const breakage = found ? found.name : "поломка #" + row.breakage_id;
      return '<div class="list-item"><span><strong>' + esc(breakage) + '</strong> · ' +
        esc(LABELS.repair[row.method] || row.method) +
        (row.target ? '<div class="meta">Куда наводиться: ' + esc(row.target) + '</div>' : "") +
        (row.steps ? '<div class="meta">' + esc(row.steps) + '</div>' : "") +
        '</span></div>';
    }).join("");
  }

  function relationsList(item) {
    return (item.relations || []).map((row) => {
      const other = state.cache.items.find((i) => i.id === row.related_item_id);
      return '<div class="list-item"><span>' + esc(LABELS.relation[row.kind] || row.kind) + ': ' +
        esc(other ? other.name : "предмет #" + row.related_item_id) +
        (row.notes ? '<div class="meta">' + esc(row.notes) + '</div>' : "") +
        '</span></div>';
    }).join("");
  }

  async function renderItemDetail(id) {
    const item = await api("/items/" + id);
    const scalar = scalarFields().map((field) =>
      kvRow(field.label, displayValue(field, (item.values || {})[field.key]))
    ).join("");
    const structural = activeFields().filter((field) => STRUCTURAL.includes(field.type)).map((field) => {
      const content = field.type === "sources" ? sourcesList(item)
        : field.type === "repairs" ? repairsList(item) : relationsList(item);
      return '<h2>' + esc(field.label) + '</h2><div class="panel list">' +
        (content || '<div class="empty">Не заполнено</div>') + '</div>';
    }).join("");

    view().innerHTML =
      '<h1>' + esc(item.name) + '</h1>' +
      '<p class="subtitle">Обновил(а) ' + esc(item.author) + ' ' + esc(fmtDate(item.updated_at)) + '</p>' +
      '<div class="actions"><a class="btn" href="#/items">← К списку</a>' +
      '<a class="btn primary" href="#/items/' + item.id + '/edit">Редактировать</a>' +
      '<button type="button" class="btn danger" data-action="delete-item" data-id="' + item.id + '">Удалить</button></div>' +
      '<div class="panel"><h2>Значения полей</h2><dl class="kv">' +
        scalar +
        kvRow("Создал(а)", item.author) +
        kvRow("Создано", fmtDate(item.created_at)) +
      '</dl></div>' + structural;
  }

  function templateControl(field, values) {
    const name = "v_" + field.key;
    const value = values[field.key] ?? field.default_value ?? "";
    let control;
    if (field.type === "textarea") {
      control = '<textarea name="' + name + '"' + (field.required ? " required" : "") + '>' + esc(value) + '</textarea>';
    } else if (field.type === "enum") {
      if (field.multiple) {
        control = '<div class="badges">' + (field.options || []).map((option) => (
          '<label class="inline"><input type="checkbox" name="' + name + '" value="' + esc(option) + '"' +
          ((Array.isArray(value) && value.includes(option)) ? " checked" : "") +
          '><span>' + esc(optionLabel(field, option)) + '</span></label>'
        )).join("") + '</div>';
      } else {
        control = '<select name="' + name + '"' + (field.required ? " required" : "") + '>' +
          optionsHtml((field.options || []).map((option) => ({ value: option, label: optionLabel(field, option) })), value, field.required ? null : "Не выбрано") +
          '</select>';
      }
    } else if (field.type === "number") {
      control = '<input type="number" name="' + name + '" value="' + esc(value === null ? "" : value) + '"' +
        (field.required ? " required" : "") + '>';
    } else if (field.type === "checkbox") {
      control = '<input type="checkbox" name="' + name + '"' + (value ? " checked" : "") + '>';
    } else {
      control = '<input name="' + name + '" value="' + esc(value) + '"' + (field.required ? " required" : "") + '>';
    }
    return '<label' + ((field.type === "textarea" || field.type === "enum") ? ' class="full"' : "") +
      '><span>' + esc(field.label) + (field.required ? " *" : "") + '</span>' + control + '</label>';
  }

  function sourceRow(data = {}) {
    return '<div class="repeat-row">' +
      '<label><span>Источник</span><select name="s_kind">' + enumOptions(LABELS.source, data.kind || "ground") + '</select></label>' +
      '<label><span>Локация</span><select name="s_level">' + optionsHtml(state.cache.levels.map((l) => ({ value: l.id, label: l.name })), data.level_id, "Любая") + '</select></label>' +
      '<label><span>Шанс 0..1</span><input type="number" min="0" max="1" step="0.01" name="s_chance" value="' + esc(data.chance ?? "") + '"></label>' +
      '<label class="full"><span>Условия появления</span><input name="s_conditions" value="' + esc(data.conditions || "") + '"></label>' +
      '<label class="full"><span>Заметки</span><input name="s_notes" value="' + esc(data.notes || "") + '"></label>' +
      '<div class="row-actions"><button type="button" class="btn small danger" data-action="remove-row">Удалить</button></div></div>';
  }

  function repairRow(data = {}) {
    return '<div class="repeat-row">' +
      '<label><span>Поломка</span><select name="r_breakage">' + optionsHtml(state.cache.breakages.map((b) => ({ value: b.id, label: b.name })), data.breakage_id, "Выберите поломку") + '</select></label>' +
      '<label><span>Способ</span><select name="r_method">' + enumOptions(LABELS.repair, data.method || "targeted") + '</select></label>' +
      '<label class="full"><span>Куда именно наводиться</span><input name="r_target" value="' + esc(data.target || "") + '"></label>' +
      '<label class="full"><span>Шаги ремонта</span><input name="r_steps" value="' + esc(data.steps || "") + '"></label>' +
      '<label class="full"><span>Заметки</span><input name="r_notes" value="' + esc(data.notes || "") + '"></label>' +
      '<div class="row-actions"><button type="button" class="btn small danger" data-action="remove-row">Удалить</button></div></div>';
  }

  function relationRow(data = {}, currentId = null) {
    const others = state.cache.items.filter((item) => item.id !== currentId);
    return '<div class="repeat-row">' +
      '<label><span>Другой предмет</span><select name="l_item">' + optionsHtml(others.map((i) => ({ value: i.id, label: i.name })), data.related_item_id, "Выберите предмет") + '</select></label>' +
      '<label><span>Тип связи</span><select name="l_kind">' + enumOptions(LABELS.relation, data.kind || "requires") + '</select></label>' +
      '<label class="full"><span>Заметки</span><input name="l_notes" value="' + esc(data.notes || "") + '"></label>' +
      '<div class="row-actions"><button type="button" class="btn small danger" data-action="remove-row">Удалить</button></div></div>';
  }

  function structuralPanel(field, item) {
    const config = {
      sources: { title: "Где можно найти", box: "sourcesBox", add: "add-source", addLabel: "+ Источник", rows: (item.sources || []).map(sourceRow).join("") },
      repairs: { title: "Какие поломки чинит", box: "repairsBox", add: "add-repair", addLabel: "+ Поломка", rows: (item.repairs || []).map(repairRow).join("") },
      relations: { title: "Связи с другими предметами", box: "relationsBox", add: "add-relation", addLabel: "+ Связь", rows: (item.relations || []).map((row) => relationRow(row, item.id)).join("") }
    }[field.type];
    return '<div class="panel"><div class="repeat-heading"><h2>' + esc(field.label) + '</h2>' +
      '<button type="button" class="btn small" data-action="' + config.add + '">' + esc(config.addLabel) + '</button></div>' +
      '<div id="' + config.box + '">' + config.rows + '</div></div>';
  }

  async function renderItemEditor(id) {
    let item;
    if (id) {
      item = await api("/items/" + id);
    } else {
      const values = {};
      scalarFields().forEach((field) => { values[field.key] = field.default_value ?? ""; });
      item = { values, version: 0, id: null, sources: [], repairs: [], relations: [] };
    }

    const fields = scalarFields().map((field) => templateControl(field, item.values || {})).join("");
    const panels = activeFields().filter((field) => STRUCTURAL.includes(field.type))
      .map((field) => structuralPanel(field, item)).join("");

    view().innerHTML =
      '<h1>' + (id ? "Редактирование предмета" : "Новый предмет") + '</h1>' +
      '<p class="subtitle">Состав полей и значения по умолчанию задаются на вкладке «Шаблон».</p>' +
      '<form id="itemForm" data-id="' + esc(id || "") + '">' +
        '<input type="hidden" name="version" value="' + esc(item.version) + '">' +
        '<div class="panel"><h2>Поля предмета</h2><div class="form-grid">' + fields + '</div></div>' +
        panels +
        '<div class="panel"><label><span>Ваше имя (для истории изменений)</span>' +
          '<input id="formAuthor" maxlength="80" value="' + esc(state.author) + '" placeholder="Аноним"></label>' +
          '<div class="actions"><button type="button" class="btn primary" data-action="save-item">Сохранить</button>' +
          '<a class="btn" href="' + (id ? "#/items/" + id : "#/items") + '">Отмена</a></div></div>' +
      '</form>';
  }

  function rowValue(row, name) {
    const control = row.querySelector('[name="' + name + '"]');
    return control ? String(control.value || "").trim() : "";
  }

  function collectRows(boxId, make) {
    const box = document.getElementById(boxId);
    if (!box) return [];
    return Array.from(box.querySelectorAll(".repeat-row"))
      .map((row) => make(row))
      .filter((row) => row !== null);
  }

  function numberOrNull(value) {
    return value === "" ? null : Number(value);
  }

  function collectValues(form) {
    const values = {};
    scalarFields().forEach((field) => {
      const name = "v_" + field.key;
      if (field.type === "checkbox") {
        values[field.key] = Boolean(form.elements.namedItem(name)?.checked);
      } else if (field.type === "enum" && field.multiple) {
        values[field.key] = Array.from(form.querySelectorAll('[name="' + name + '"]:checked')).map((input) => input.value);
      } else {
        const control = form.elements.namedItem(name);
        let value = control ? control.value : "";
        if (field.type === "number") value = value === "" ? null : Number(value);
        values[field.key] = value;
      }
    });
    return values;
  }

  async function saveItem() {
    const form = document.getElementById("itemForm");
    if (!form) return;
    if (!form.reportValidity()) return;
    const id = form.dataset.id || null;
    const payload = {
      author: (document.getElementById("formAuthor").value || "").trim() || "Аноним",
      values: collectValues(form),
      sources: collectRows("sourcesBox", (row) => {
        const data = {
          kind: rowValue(row, "s_kind"),
          level_id: numberOrNull(rowValue(row, "s_level")),
          chance: numberOrNull(rowValue(row, "s_chance")),
          conditions: rowValue(row, "s_conditions"),
          notes: rowValue(row, "s_notes")
        };
        return data.kind ? data : null;
      }),
      repairs: collectRows("repairsBox", (row) => {
        const breakageId = numberOrNull(rowValue(row, "r_breakage"));
        if (!breakageId) return null;
        return {
          breakage_id: breakageId,
          method: rowValue(row, "r_method"),
          target: rowValue(row, "r_target"),
          steps: rowValue(row, "r_steps"),
          notes: rowValue(row, "r_notes")
        };
      }),
      relations: collectRows("relationsBox", (row) => {
        const relatedId = numberOrNull(rowValue(row, "l_item"));
        if (!relatedId) return null;
        return {
          related_item_id: relatedId,
          kind: rowValue(row, "l_kind"),
          notes: rowValue(row, "l_notes")
        };
      })
    };
    try {
      const body = id ? Object.assign({ version: Number(form.elements.namedItem("version").value) }, payload) : payload;
      const saved = id
        ? await api("/items/" + id, { method: "PATCH", body: JSON.stringify(body) })
        : await api("/items", { method: "POST", body: JSON.stringify(body) });
      state.author = payload.author;
      localStorage.setItem("itemdb.author", state.author);
      document.getElementById("authorInput").value = state.author;
      toast("Предмет сохранён");
      location.hash = "#/items/" + saved.id;
    } catch (error) {
      toast(error.message, true);
    }
  }

  function formatDefault(value) {
    if (value === null || value === undefined) return "";
    if (Array.isArray(value)) return value.join(", ");
    if (typeof value === "boolean") return value ? "true" : "false";
    return String(value);
  }

  function parseDefault(type, raw, multiple) {
    if (type === "checkbox") return raw.trim().toLowerCase() === "true";
    if (type === "number") return raw.trim() === "" ? null : Number(raw);
    if (type === "enum") {
      const list = raw.split(",").map((part) => part.trim()).filter(Boolean);
      return multiple ? list : (list[0] || "");
    }
    return raw;
  }

  function templateRow(field) {
    const type = field.type;
    return '<div class="repeat-row template-row" data-id="' + field.id + '">' +
      '<label><span>Ключ</span><input value="' + esc(field.key) + '" disabled></label>' +
      '<label><span>Название в форме</span><input name="t_label" value="' + esc(field.label) + '"></label>' +
      '<label><span>Тип</span><select name="t_type">' + optionsHtml(
        ALL_FIELD_TYPES.filter((item) => !STRUCTURAL.includes(item) || field.system).map((item) => ({ value: item, label: item })),
        type
      ) + '</select></label>' +
      '<label><span>Варианты (через запятую)</span><input name="t_options" value="' + esc((field.options || []).join(", ")) + '"' + (type === "enum" ? "" : " disabled") + '></label>' +
      '<label><span>По умолчанию</span><input name="t_default" value="' + esc(formatDefault(field.default_value)) + '"' + (STRUCTURAL.includes(type) ? " disabled" : "") + '></label>' +
      '<label class="inline"><input type="checkbox" name="t_required"' + (field.required ? " checked" : "") + '><span>Обязательное</span></label>' +
      '<label class="inline"><input type="checkbox" name="t_multiple"' + (field.multiple ? " checked" : "") + '><span>Множественный выбор</span></label>' +
      '<label class="inline"><input type="checkbox" name="t_active"' + (field.active ? " checked" : "") + '><span>Показывать</span></label>' +
      '<div class="row-actions">' +
        '<button type="button" class="btn small" data-action="template-up">↑</button>' +
        '<button type="button" class="btn small" data-action="template-down">↓</button>' +
        '<button type="button" class="btn small primary" data-action="template-save">Сохранить</button>' +
        (field.system ? "" : '<button type="button" class="btn small danger" data-action="template-delete">Удалить</button>') +
      '</div></div>';
  }

  function renderTemplate() {
    view().innerHTML =
      '<h1>Шаблон предмета</h1>' +
      '<p class="subtitle">Меняйте названия полей, типы, варианты enum и значения по умолчанию. Встроенные поля нельзя удалить, но можно скрыть — тогда при сохранении предмета подставится значение по умолчанию.</p>' +
      '<div class="panel"><h2>Новое поле</h2><div class="form-grid">' +
        '<label><span>Ключ (латиницей)</span><input id="newFieldKey" placeholder="my_field" maxlength="60"></label>' +
        '<label><span>Название</span><input id="newFieldLabel" placeholder="Моё поле" maxlength="160"></label>' +
        '<label><span>Тип</span><select id="newFieldType">' + FIELD_TYPES.map((type) => '<option value="' + type + '">' + type + '</option>').join("") + '</select></label>' +
        '<div class="row-actions"><button type="button" class="btn primary" data-action="template-add">Добавить поле</button></div>' +
      '</div></div>' +
      '<div class="panel"><div class="repeat-heading"><h2>Поля</h2><span class="meta">Порядок меняется стрелками</span></div>' +
        '<div id="templateRows">' + state.template.map(templateRow).join("") + '</div></div>';
  }

  async function templateSave(button) {
    const row = button.closest(".template-row");
    const field = state.template.find((item) => item.id === Number(row.dataset.id));
    const get = (name) => row.querySelector('[name="' + name + '"]');
    const type = get("t_type").value;
    const body = {
      version: field.version,
      author: state.author,
      label: get("t_label").value.trim(),
      options: get("t_options").value.split(",").map((part) => part.trim()).filter(Boolean),
      default_value: STRUCTURAL.includes(type) ? null : parseDefault(type, get("t_default").value, get("t_multiple").checked),
      required: get("t_required").checked,
      multiple: get("t_multiple").checked,
      active: get("t_active").checked,
      position: field.position
    };
    try {
      await api("/template/" + field.id, { method: "PATCH", body: JSON.stringify(body) });
      toast("Поле сохранено");
      await render();
    } catch (error) {
      toast(error.message, true);
    }
  }

  async function templateAdd() {
    const key = document.getElementById("newFieldKey").value.trim().toLowerCase().replace(/[-\s]+/g, "_");
    const label = document.getElementById("newFieldLabel").value.trim();
    const type = document.getElementById("newFieldType").value;
    if (!/^[a-z][a-z0-9_]*$/.test(key)) {
      toast("Ключ: латиница, цифры и подчёркивание", true);
      return;
    }
    if (!label) {
      toast("Укажите название поля", true);
      return;
    }
    try {
      await api("/template", {
        method: "POST",
        body: JSON.stringify({
          key, label, type, options: [], default_value: type === "checkbox" ? false : type === "number" ? null : "",
          required: false, multiple: false, active: true, position: state.template.length, author: state.author
        })
      });
      toast("Поле добавлено");
      await render();
    } catch (error) {
      toast(error.message, true);
    }
  }

  async function templateDelete(button) {
    const row = button.closest(".template-row");
    if (!confirm("Удалить поле шаблона?")) return;
    try {
      await api("/template/" + row.dataset.id, { method: "DELETE" });
      toast("Поле удалено");
      await render();
    } catch (error) {
      toast(error.message, true);
    }
  }

  async function templateMove(button, direction) {
    const row = button.closest(".template-row");
    const sibling = direction < 0 ? row.previousElementSibling : row.nextElementSibling;
    if (!sibling || !sibling.classList.contains("template-row")) return;
    if (direction < 0) row.parentNode.insertBefore(row, sibling);
    else row.parentNode.insertBefore(sibling, row);
    const ids = Array.from(document.querySelectorAll(".template-row")).map((item) => Number(item.dataset.id));
    try {
      await api("/template/reorder", { method: "POST", body: JSON.stringify({ ids }) });
      await render();
    } catch (error) {
      toast(error.message, true);
    }
  }

  function renderSimpleList(kind) {
    const config = SIMPLE[kind];
    const rows = state.cache[kind];
    view().innerHTML =
      '<h1>' + esc(config.title) + '</h1>' +
      '<p class="subtitle">Сущности, с которыми связаны предметы.</p>' +
      '<div class="actions" style="margin:0 0 18px"><a class="btn primary" href="#/' + kind + '/new">+ Добавить</a></div>' +
      (rows.length
        ? '<div class="list">' + rows.map((row) => (
            '<a class="list-item" href="#/' + kind + '/' + row.id + '">' +
            '<span><strong>' + esc(row.name) + '</strong></span>' +
            '<span class="meta">' + esc(row.author) + ' · ' + esc(fmtDate(row.updated_at)) + ' →</span></a>'
          )).join("") + '</div>'
        : '<div class="empty">Записей пока нет.</div>');
  }

  function simpleControl(field, row) {
    const value = row[field.key] ?? field.default ?? "";
    const id = "f_" + field.key;
    let control;
    if (field.type === "textarea") {
      control = '<textarea id="' + id + '">' + esc(value) + '</textarea>';
    } else if (field.type === "enum") {
      control = '<select id="' + id + '">' + enumOptions(field.values, value) + '</select>';
    } else if (field.type === "number") {
      control = '<input id="' + id + '" type="number" min="' + (field.min ?? 0) + '" max="' + (field.max ?? 999999) + '" value="' + esc(value) + '">';
    } else {
      control = '<input id="' + id + '" maxlength="160" value="' + esc(value) + '"' + (field.required ? " required" : "") + '>';
    }
    return '<label' + (field.full ? ' class="full"' : "") + '><span>' + esc(field.label) + '</span>' + control + '</label>';
  }

  async function renderSimpleEditor(kind, id) {
    const config = SIMPLE[kind];
    let row = { version: 0 };
    if (id) {
      try {
        row = await api("/" + config.path + "/" + id);
      } catch (error) {
        showError(error);
        return;
      }
    } else {
      config.fields.forEach((field) => { row[field.key] = field.default ?? ""; });
    }
    view().innerHTML =
      '<h1>' + (id ? "Редактирование" : "Новая запись") + ': ' + esc(config.title) + '</h1>' +
      '<div class="panel"><div class="form-grid">' +
        '<input type="hidden" id="f_version" value="' + esc(row.version || 0) + '">' +
        config.fields.map((field) => simpleControl(field, row)).join("") +
        '<label class="full"><span>Ваше имя</span><input id="formAuthor" maxlength="80" value="' + esc(state.author) + '" placeholder="Аноним"></label>' +
      '</div><div class="actions"><button type="button" class="btn primary" data-action="save-simple" data-kind="' + kind + '" data-id="' + esc(id || "") + '">Сохранить</button>' +
      '<a class="btn" href="#/' + kind + '">Отмена</a></div></div>';
  }

  async function renderSimpleDetail(kind, id) {
    const config = SIMPLE[kind];
    let row;
    try {
      row = await api("/" + config.path + "/" + id);
    } catch (error) {
      showError(error);
      return;
    }
    view().innerHTML =
      '<h1>' + esc(row.name) + '</h1>' +
      '<p class="subtitle">' + esc(row.author) + ' · ' + esc(fmtDate(row.updated_at)) + '</p>' +
      '<div class="actions"><a class="btn" href="#/' + kind + '">← К списку</a>' +
      '<a class="btn primary" href="#/' + kind + '/' + row.id + '/edit">Редактировать</a>' +
      '<button type="button" class="btn danger" data-action="delete-simple" data-kind="' + kind + '" data-id="' + row.id + '">Удалить</button></div>' +
      '<div class="panel"><dl class="kv">' +
        config.fields.map((field) => kvRow(field.label, row[field.key])).join("") +
      '</dl></div>';
  }

  async function saveSimple(kind, id) {
    const config = SIMPLE[kind];
    const payload = { author: (document.getElementById("formAuthor").value || "").trim() || "Аноним" };
    for (const field of config.fields) {
      const control = document.getElementById("f_" + field.key);
      let value = control.value;
      if (field.type === "number") value = value === "" ? 0 : Number(value);
      payload[field.key] = typeof value === "string" ? value.trim() : value;
    }
    if (!payload.name) {
      toast("Введите название", true);
      return;
    }
    try {
      const saved = id
        ? await api("/" + config.path + "/" + id, {
            method: "PATCH",
            body: JSON.stringify(Object.assign({ version: Number(document.getElementById("f_version").value) }, payload))
          })
        : await api("/" + config.path, { method: "POST", body: JSON.stringify(payload) });
      state.author = payload.author;
      localStorage.setItem("itemdb.author", state.author);
      document.getElementById("authorInput").value = state.author;
      toast("Сохранено");
      location.hash = "#/" + kind + "/" + saved.id;
    } catch (error) {
      toast(error.message, true);
    }
  }

  async function renderActivity() {
    const rows = await api("/activity?limit=100");
    view().innerHTML =
      '<h1>История изменений</h1>' +
      '<p class="subtitle">Кто и когда менял записи в общей базе.</p>' +
      (rows.length
        ? '<div class="list">' + rows.map((row) => (
            '<div class="list-item"><span><strong>' + esc(row.author) + '</strong> ' +
            esc(LABELS.action[row.action] || row.action) + ' ' +
            esc(LABELS.entity[row.entity_type] || row.entity_type) +
            (row.entity_name ? ' «' + esc(row.entity_name) + '»' : "") +
            (row.details ? '<div class="meta">' + esc(row.details) + '</div>' : "") +
            '</span><span class="meta">' + esc(fmtDate(row.created_at)) + '</span></div>'
          )).join("") + '</div>'
        : '<div class="empty">История пока пуста.</div>');
  }

  function renderSettings() {
    view().innerHTML =
      '<h1>Настройки</h1>' +
      '<div class="panel"><h2>Подключение к серверу</h2>' +
      '<p class="subtitle">Если сайт открыт с GitHub Pages, укажите адрес работающего бэкенда, например https://example.pythonanywhere.com/api</p>' +
      '<label><span>Адрес API</span><input id="apiBaseInput" value="' + esc(apiBase()) + '" placeholder="https://.../api"></label>' +
      '<div class="actions"><button type="button" class="btn primary" data-action="save-api">Сохранить адрес</button>' +
      '<button type="button" class="btn" data-action="check-api">Проверить связь</button></div></div>' +
      '<div class="panel"><h2>Резервная копия</h2>' +
      '<p class="subtitle">Экспорт скачивает JSON со всей базой, включая шаблон. Импорт полностью заменяет текущие данные.</p>' +
      '<div class="actions"><button type="button" class="btn" data-action="export-data">Скачать JSON</button>' +
      '<input id="importFile" type="file" accept="application/json,.json" style="max-width:300px">' +
      '<button type="button" class="btn danger" data-action="import-data">Заменить базу из файла</button></div></div>' +
      '<div class="panel"><h2>Как это работает</h2>' +
      '<p>Все посетители видят одни и те же записи. Вход не нужен: введите своё имя вверху — оно попадёт в историю изменений.</p></div>';
  }

  async function exportData() {
    try {
      const data = await api("/export");
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "itemdatabase-" + new Date().toISOString().slice(0, 10) + ".json";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      toast("Резервная копия скачана");
    } catch (error) {
      toast(error.message, true);
    }
  }

  async function importData() {
    const input = document.getElementById("importFile");
    const file = input && input.files[0];
    if (!file) {
      toast("Выберите JSON-файл", true);
      return;
    }
    if (!confirm("Внимание: текущие данные будут полностью заменены. Продолжить?")) return;
    try {
      const data = JSON.parse(await file.text());
      const result = await api("/import", {
        method: "POST",
        body: JSON.stringify({ replace: true, data })
      });
      toast("Импортировано предметов: " + result.imported.items);
      await render();
    } catch (error) {
      toast(error.message, true);
    }
  }

  document.addEventListener("click", async (event) => {
    const target = event.target.closest("[data-action]");
    if (!target) return;
    const action = target.dataset.action;
    if (action === "remove-row") {
      target.closest(".repeat-row")?.remove();
    } else if (action === "add-source") {
      document.getElementById("sourcesBox").insertAdjacentHTML("beforeend", sourceRow());
    } else if (action === "add-repair") {
      document.getElementById("repairsBox").insertAdjacentHTML("beforeend", repairRow());
    } else if (action === "add-relation") {
      const form = document.getElementById("itemForm");
      const currentId = form && form.dataset.id ? Number(form.dataset.id) : null;
      document.getElementById("relationsBox").insertAdjacentHTML("beforeend", relationRow({}, currentId));
    } else if (action === "save-item") {
      await saveItem();
    } else if (action === "template-add") {
      await templateAdd();
    } else if (action === "template-save") {
      await templateSave(target);
    } else if (action === "template-delete") {
      await templateDelete(target);
    } else if (action === "template-up") {
      await templateMove(target, -1);
    } else if (action === "template-down") {
      await templateMove(target, 1);
    } else if (action === "save-simple") {
      await saveSimple(target.dataset.kind, target.dataset.id || null);
    } else if (action === "delete-item") {
      if (confirm("Удалить предмет?")) {
        try {
          await api("/items/" + target.dataset.id, { method: "DELETE" });
          toast("Предмет удалён");
          location.hash = "#/items";
        } catch (error) {
          toast(error.message, true);
        }
      }
    } else if (action === "delete-simple") {
      const kind = target.dataset.kind;
      if (confirm("Удалить запись?")) {
        try {
          await api("/" + SIMPLE[kind].path + "/" + target.dataset.id, { method: "DELETE" });
          toast("Запись удалена");
          location.hash = "#/" + kind;
        } catch (error) {
          toast(error.message, true);
        }
      }
    } else if (action === "save-api") {
      localStorage.setItem("itemdb.apiBase", document.getElementById("apiBaseInput").value.trim());
      toast("Адрес API сохранён");
      await checkConnection();
    } else if (action === "check-api") {
      localStorage.setItem("itemdb.apiBase", document.getElementById("apiBaseInput").value.trim());
      await checkConnection();
    } else if (action === "export-data") {
      await exportData();
    } else if (action === "import-data") {
      await importData();
    }
  });

  document.addEventListener("input", (event) => {
    if (event.target.id === "authorInput") {
      state.author = event.target.value;
      localStorage.setItem("itemdb.author", state.author);
    }
    if (event.target.dataset && event.target.dataset.filter) updateItemsGrid();
  });

  document.addEventListener("change", (event) => {
    if (event.target.dataset && event.target.dataset.filter) updateItemsGrid();
  });

  state.author = localStorage.getItem("itemdb.author") || "";
  document.getElementById("authorInput").value = state.author;
  window.addEventListener("hashchange", render);
  render();
  checkConnection();
})();
