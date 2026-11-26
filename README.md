# ItemDataBase

Общий инструмент геймдизайнера для игры-легаллайка: база предметов, поломок и локаций с полностью настраиваемой формой предмета. Все, кто откроет сайт, видят одни и те же данные и изменения других. Вход не нужен — каждый указывает своё имя, которое попадает в историю.

## Что можно описывать

- **Предмет**: поля задаются вкладкой «Шаблон» — текст, текстовая область, число, флажок и `enum` с одним или несколькими вариантами.
- **Шаблон**: можно переименовать и скрыть встроенные поля, изменить порядок, задать значения по умолчанию и добавить свои поля. Скрытые поля сохраняют значение по умолчанию.
- **Добыча**: лежит на локации или другое; шанс и условия появления. Магазины и вендинговые автоматы удалены.
- **Ремонт**: какие поломки чинит предмет, куда именно наводиться, шаги.
- **Связи предметов**: требует, комбинируется, улучшает.
- **Поломки и локации** — отдельные сущности со связями.

Есть поиск и фильтры, история изменений, экспорт/импорт всей базы вместе с шаблоном в JSON и защита от одновременного редактирования одной записи (`409`, нужно обновить страницу).

API шаблона: `GET/POST /api/template`, `PATCH/DELETE /api/template/{id}`, `POST /api/template/reorder`. Встроенные поля (`system: true`) нельзя удалить — только отключить через `active: false`.

## Локальный запуск

### Windows (самый простой вариант)

1. Дважды кликните `setup.bat` — один раз установит зависимости.
2. Дважды кликните `run.bat` — запустит сайт.

Скрипты сами найдут Python в PATH, а если его нет — используют портативный Python из `%LOCALAPPDATA%\Python312Embed`. Сообщение «Python was not found…» означает, что сработал заглушка Microsoft Store; в этом случае просто используйте `.bat`-файлы вместо команд `python ...`.

### Если Python установлен обычным образом

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run.py
```

Откройте http://localhost:8000 . Документация API: http://localhost:8000/docs . Для автоперезапуска при правках: `RELOAD=1 python run.py`.

База хранится в `itemdb.sqlite3` рядом с проектом. Путь можно переопределить переменной `DB_PATH`, порт — `PORT`.

## GitHub Pages + бесплатный бэкенд

GitHub Pages умеет только статику, поэтому бэкенд нужно разместить отдельно. Проверенный вариант — PythonAnywhere (бесплатный аккаунт, SQLite-файл сохраняется между перезапусками).

### 1. Фронтенд на GitHub Pages

В репозитории включите **Settings → Pages → Source: GitHub Actions**. При push в `main` workflow `.github/workflows/deploy-pages.yml` опубликует папку `web/`.

В `web/config.js` укажите адрес своего бэкенда:

```js
window.APP_CONFIG = { apiBase: "https://<username>.pythonanywhere.com/api" };
```

Либо введите адрес один раз на вкладке «Настройки» — он сохранится в этом браузере через localStorage.

### 2. Бэкенд на PythonAnywhere

1. Зарегистрируйтесь, в **Bash** выполните:

```bash
git clone https://github.com/<username>/<repo>.git ItemDataBase
cd ItemDataBase
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

2. На вкладке **Web** создайте Manual configuration → Python 3.12, укажите:
   - Source code: `/home/<username>/ItemDataBase`
   - Virtualenv: `/home/<username>/ItemDataBase/.venv`

3. Откройте WSGI-файл приложения и замените содержимое:

```python
import os
import sys

project_home = "/home/<username>/ItemDataBase"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ["DB_PATH"] = "/home/<username>/ItemDataBase/itemdb.sqlite3"
os.environ["CORS_ORIGINS"] = "https://<username>.github.io,https://<username>.pythonanywhere.com"

from app.main import app
```

4. Нажмите **Reload**. Проверьте `https://<username>.pythonanywhere.com/api/health`.

Бесплатные приложения PythonAnywhere засыпают — первый запрос после простоя может быть чуть медленнее.

### Резервные копии

На вкладке «Настройки» нажмите «Скачать JSON». Импорт полностью заменяет базу, поэтому делайте копию перед изменениями на живой версии.

## Тесты

```powershell
pip install pytest httpx
pytest -q
```
