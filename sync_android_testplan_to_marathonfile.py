"""
Синхронизация данных из Google Таблицы (вкладка ANDROID_TESTPLAN, столбец A)
в файл Marathonfile.

Читает все непустые значения из столбца A на вкладке ANDROID_TESTPLAN
и записывает их построчно в указанный Marathonfile.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv

load_dotenv()

# Google
GOOGLE_SHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "")
GOOGLE_CREDENTIALS_PATH = os.environ.get(
    "GOOGLE_CREDENTIALS_PATH",
    str(Path(__file__).resolve().parent / "credentials.json"),
)
SHEET_NAME_ANDROID_TESTPLAN = "ANDROID_TESTPLAN"
COLUMN_A_RANGE = "A1:A1000"

# Файл назначения
MARATHONFILE_PATH = os.environ.get(
    "MARATHONFILE_PATH",
    "/Users/sergeyyakimov/StudioProjects/saptain/test-resources/testplans/user-plan/Marathonfile",
)


def get_sheets_service():
    """Клиент Google Sheets API (Service Account)."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    if not Path(GOOGLE_CREDENTIALS_PATH).exists():
        raise FileNotFoundError(
            f"Файл учётных данных не найден: {GOOGLE_CREDENTIALS_PATH}"
        )
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = service_account.Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_PATH,
        scopes=scopes,
    )
    return build("sheets", "v4", credentials=credentials)


def read_column_a_from_android_testplan(service, spreadsheet_id: str) -> list[str]:
    """
    Читает столбец A на вкладке ANDROID_TESTPLAN.
    Возвращает список непустых значений (как строки, без лишней фильтрации).
    """
    range_full = f"'{SHEET_NAME_ANDROID_TESTPLAN}'!{COLUMN_A_RANGE}"
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=range_full)
        .execute()
    )
    rows = result.get("values") or []
    lines = []
    for row in rows:
        # Сохраняем ведущие пробелы (важно для отступов YAML) и пустые строки
        raw = (row[0] if row else "").rstrip()
        lines.append(raw)
    return lines


def write_lines_to_marathonfile(file_path: str, lines: list[str]) -> None:
    """Записывает список строк в файл построчно."""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def main():
    if not GOOGLE_SHEET_ID:
        print("Укажите GOOGLE_SHEET_ID в .env или переменной окружения.")
        sys.exit(1)

    print("Подключение к Google Sheets...")
    sheets = get_sheets_service()
    print(f"Чтение столбца A с вкладки {SHEET_NAME_ANDROID_TESTPLAN}...")
    lines = read_column_a_from_android_testplan(sheets, GOOGLE_SHEET_ID)

    if not lines:
        print(f"В столбце A на вкладке {SHEET_NAME_ANDROID_TESTPLAN} не найдено ни одного значения.")
        sys.exit(1)

    print(f"Найдено строк: {len(lines)}")
    print(f"Запись в файл: {MARATHONFILE_PATH}")
    write_lines_to_marathonfile(MARATHONFILE_PATH, lines)
    print("Готово. Данные записаны в Marathonfile.")


if __name__ == "__main__":
    main()
