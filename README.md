# VengaReportProject

Выгрузка отчётов в Google Таблицы через Google Sheets API.

## Быстрый тест отправки данных в Google Таблицу

### 1. Окружение и зависимости

```bash
cd /Users/sergeyyakimov/work/VengaReportProject
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Настройка Google Cloud и таблицы

1. **Google Cloud Console**  
   Перейдите в [Google Cloud Console](https://console.cloud.google.com/).

2. **Проект**  
   Создайте проект (или выберите существующий).

3. **Включите Google Sheets API**  
   Меню «APIs & Services» → «Library» → найдите «Google Sheets API» → «Enable».

4. **Учётные данные (Service Account)**  
   - «APIs & Services» → «Credentials» → «Create Credentials» → «Service account».  
   - Задайте имя (например, `venga-sheets`), создайте.  
   - В списке сервисных аккаунтов откройте созданный → вкладка «Keys» → «Add Key» → «Create new key» → **JSON**.  
   - Скачанный файл сохраните в корень проекта как **`credentials.json`** (или другой путь и укажите его в переменной окружения, см. ниже).

5. **Email сервисного аккаунта**  
   В консоли в карточке Service Account скопируйте **email** (вид: `xxx@project-id.iam.gserviceaccount.com`). Он понадобится для доступа к таблице.

6. **Google Таблица**  
   - Создайте новую таблицу: [sheets.new](https://sheets.new).  
   - В URL таблицы найдите **ID**:
     ```
     https://docs.google.com/spreadsheets/d/ 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms  /edit
                                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                            это GOOGLE_SHEET_ID
     ```  
   - Откройте доступ: кнопка «Настройки доступа» → добавьте **email сервисного аккаунта** с правом **Редактор** → «Готово».

### 3. Переменные окружения

Скопируйте пример и подставьте свой ID таблицы:

```bash
cp .env.example .env
```

В `.env` задайте:

```env
GOOGLE_SHEET_ID=ваш_id_таблицы_из_url
```

Если файл ключа не `credentials.json` и лежит в другом месте:

```env
GOOGLE_CREDENTIALS_PATH=/путь/к/вашему-ключу.json
```

### 4. Запуск теста

```bash
source .venv/bin/activate
python test_google_sheet.py
```

При успехе в консоли будет сообщение об обновлённых ячейках/строках, а в таблице появятся тестовые строки (заголовки и несколько строк с датой и статусом).

### 5. Если что-то пошло не так

- **Файл учётных данных не найден** — проверьте путь в `GOOGLE_CREDENTIALS_PATH` и что файл лежит в проекте (и не попал в `.gitignore` под другим именем).
- **403 / Permission denied** — таблица должна быть доступна на редактирование для email сервисного аккаунта из `credentials.json`.
- **404 / Not found** — проверьте, что `GOOGLE_SHEET_ID` скопирован из URL таблицы без лишних символов.

## Структура проекта

- `requirements.txt` — зависимости (Google API client, auth, dotenv).
- `test_google_sheet.py` — скрипт для тестовой записи данных в таблицу.
- `.env.example` — пример переменных окружения (копируйте в `.env` и заполните).
- `credentials.json` — **не коммитить**; хранить только локально (уже в `.gitignore`).

Дальше можно добавлять свои отчёты и вызывать тот же API для выгрузки в нужные листы и диапазоны.
