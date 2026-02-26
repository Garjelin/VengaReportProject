"""
Тестовый скрипт: отправка данных в Google Таблицу через Google Sheets API.

Перед запуском:
1. Создайте проект в Google Cloud Console и включите Google Sheets API.
2. Создайте учётные данные (Service Account), скачайте JSON-ключ.
3. Положите файл ключа в корень проекта как credentials.json (или укажите путь в GOOGLE_CREDENTIALS_PATH).
4. Создайте Google Таблицу и откройте доступ на редактирование для email из Service Account
   (например: xxx@project-id.iam.gserviceaccount.com).
5. Укажите ID таблицы в GOOGLE_SHEET_ID (из URL: docs.google.com/spreadsheets/d/<SHEET_ID>/edit).
"""
import os
import sys
from datetime import datetime
from pathlib import Path

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv

load_dotenv()

# ID таблицы из URL: https://docs.google.com/spreadsheets/d/<SPREADSHEET_ID>/edit
GOOGLE_SHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "")
# Лист, в который пишем (должен существовать в таблице)
SHEET_NAME = "TC_STATUS"
# Диапазон на этом листе — перезаписывается при каждом запуске
TIME_RANGE = "A1:A10"
# Путь к JSON-ключу Service Account (по умолчанию credentials.json в корне проекта)
GOOGLE_CREDENTIALS_PATH = os.environ.get(
    "GOOGLE_CREDENTIALS_PATH",
    str(Path(__file__).resolve().parent / "credentials.json"),
)


def get_sheets_service():
    """Создаёт клиент Google Sheets API с учётными данными Service Account."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    if not Path(GOOGLE_CREDENTIALS_PATH).exists():
        raise FileNotFoundError(
            f"Файл учётных данных не найден: {GOOGLE_CREDENTIALS_PATH}\n"
            "Скачайте JSON-ключ Service Account из Google Cloud Console и сохраните как credentials.json"
        )

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = service_account.Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_PATH,
        scopes=scopes,
    )
    service = build("sheets", "v4", credentials=credentials)
    return service


def write_current_time_to_sheet(service, spreadsheet_id: str):
    """Перезаписывает диапазон A1:A10 на листе Sheet2 текущим временем."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    range_full = f"'{SHEET_NAME}'!{TIME_RANGE}"
    body = {"values": [[now] for _ in range(10)]}  # 10 строк с одним и тем же временем
    result = (
        service.spreadsheets()
        .values()
        .update(
            spreadsheetId=spreadsheet_id,
            range=range_full,
            valueInputOption="USER_ENTERED",
            body=body,
        )
        .execute()
    )
    return result


def main():
    if not GOOGLE_SHEET_ID:
        print(
            "Укажите GOOGLE_SHEET_ID (ID таблицы из URL).\n"
            "Пример: export GOOGLE_SHEET_ID=1abc...xyz\n"
            "Или создайте файл .env с строкой: GOOGLE_SHEET_ID=1abc...xyz"
        )
        sys.exit(1)

    print("Подключение к Google Sheets API...")
    service = get_sheets_service()
    print(f"Запись текущего времени в {SHEET_NAME}!{TIME_RANGE}...")
    result = write_current_time_to_sheet(service, GOOGLE_SHEET_ID)
    print(
        f"Готово. Обновлено ячеек: {result.get('updatedCells', '?')}, "
        f"строк: {result.get('updatedRows', '?')}."
    )
    print(f"Время записано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
