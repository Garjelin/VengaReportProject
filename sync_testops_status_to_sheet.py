"""
Синхронизация статусов тест-кейсов из TestOps в Google Таблицу.

На вкладке TC_STATUS в столбце A должны быть номера тест-кейсов (ID).
Скрипт запрашивает у TestOps результат последнего прогона для каждого кейса
и записывает статус в столбец B напротив каждого номера.

Опирается на логику sync-all-from-list.sh (TestOps API: токен, history).
"""
import os
import sys
import time
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
SHEET_NAME_TC_STATUS = "TC_STATUS"
COLUMN_A_RANGE = "A1:A1000"   # откуда читаем номера кейсов
COLUMN_B_START = "B1"        # с какой ячейки пишем статусы

# TestOps (как в sync-all-from-list.sh)
TESTOPS_URL = os.environ.get("TESTOPS_URL", "https://vengacrypto.testops.cloud")
TESTOPS_USERNAME = os.environ.get("TESTOPS_USERNAME", "")
TESTOPS_PASSWORD = os.environ.get("TESTOPS_PASSWORD", "")


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


def get_testops_token():
    """Получить access_token TestOps (OAuth password grant)."""
    import requests

    url = f"{TESTOPS_URL.rstrip('/')}/api/uaa/oauth/token"
    data = {
        "grant_type": "password",
        "username": TESTOPS_USERNAME,
        "password": TESTOPS_PASSWORD,
        "client_id": "api",
        "scope": "openid",
    }
    resp = requests.post(url, data=data, timeout=30)
    resp.raise_for_status()
    body = resp.json()
    token = body.get("access_token")
    if not token:
        raise RuntimeError("TestOps: в ответе нет access_token")
    return token


def normalize_status(status: str) -> str:
    """UNKNOWN -> SKIPPED, BROKEN -> FAILED; остальное без изменений."""
    s = (status or "").upper()
    if s == "UNKNOWN":
        return "SKIPPED"
    if s == "BROKEN":
        return "FAILED"
    return s


def get_last_status(test_case_id: str, token: str) -> str:
    """
    Запрос к TestOps: результат последнего прогона тест-кейса.
    Возвращает статус: PASSED, FAILED, BROKEN, SKIPPED, UNKNOWN или NO_RESULT.
    """
    import requests

    url = f"{TESTOPS_URL.rstrip('/')}/api/testcase/{test_case_id}/history"
    params = {"page": 0, "size": 1}
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    content = data.get("content") or []
    if not content:
        return "NO_RESULT"
    raw = (content[0].get("status") or "UNKNOWN").upper()
    return normalize_status(raw)


def read_case_ids_from_sheet(service, spreadsheet_id: str) -> list[str]:
    """Читает столбец A на вкладке TC_STATUS, возвращает список непустых ID."""
    range_full = f"'{SHEET_NAME_TC_STATUS}'!{COLUMN_A_RANGE}"
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=range_full)
        .execute()
    )
    rows = result.get("values") or []
    ids = []
    for row in rows:
        if not row:
            continue
        raw = (row[0] or "").strip()
        if not raw or raw.startswith("#"):
            continue
        # только число или число в начале строки (как в sync-all-from-list: id или id:expected)
        case_id = raw.split(":")[0].strip()
        if case_id.isdigit():
            ids.append(case_id)
    return ids


def write_statuses_to_sheet(service, spreadsheet_id: str, statuses: list[str]) -> dict:
    """Пишет список статусов в столбец B на TC_STATUS, начиная с B1."""
    if not statuses:
        return {}
    range_full = f"'{SHEET_NAME_TC_STATUS}'!{COLUMN_B_START}"
    body = {"values": [[s] for s in statuses]}
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
        print("Укажите GOOGLE_SHEET_ID в .env или переменной окружения.")
        sys.exit(1)
    if not TESTOPS_USERNAME or not TESTOPS_PASSWORD:
        print("Укажите TESTOPS_USERNAME и TESTOPS_PASSWORD в .env или переменных окружения.")
        sys.exit(1)

    print("Подключение к Google Sheets...")
    sheets = get_sheets_service()
    print("Чтение номеров кейсов из столбца A (TC_STATUS)...")
    case_ids = read_case_ids_from_sheet(sheets, GOOGLE_SHEET_ID)
    if not case_ids:
        print("В столбце A на вкладке TC_STATUS не найдено ни одного номера кейса.")
        sys.exit(1)
    print(f"Найдено кейсов: {len(case_ids)}")

    print("Авторизация в TestOps...")
    token = get_testops_token()
    print("Запрос статусов из TestOps...")
    statuses = []
    for i, case_id in enumerate(case_ids, 1):
        try:
            status = get_last_status(case_id, token)
            statuses.append(status)
            print(f"  [{i}/{len(case_ids)}] #{case_id} -> {status}")
        except Exception as e:
            statuses.append(f"ERROR: {e!s}"[:50])
            print(f"  [{i}/{len(case_ids)}] #{case_id} -> ERROR: {e}")
        time.sleep(0.1)

    print("Запись статусов в столбец B...")
    write_statuses_to_sheet(sheets, GOOGLE_SHEET_ID, statuses)
    print("Готово. Статусы записаны в TC_STATUS, столбец B.")


if __name__ == "__main__":
    main()
