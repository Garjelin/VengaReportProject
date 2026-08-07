#!/usr/bin/env python3
"""
Reads cell B1 from the 'queue' sheet in Google Sheets and sends it to Slack.
Usage: python3 send_joke_to_slack.py
"""

import json
import os
import urllib.request
from pathlib import Path

from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

load_dotenv()

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
GOOGLE_SHEET_ID = "1hMmBxtWdK7YxwfdrbizY-HP3a5t6h3EaF2nhGDX_x1A"
GOOGLE_CREDENTIALS_PATH = Path(__file__).resolve().parent / "credentials.json"
DUTY_PERSON_RANGE = "queue!D1"
DUTY_TASK_RANGE = "queue!E1"


def read_cell(service, range_: str, required: bool = True) -> str:
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=GOOGLE_SHEET_ID, range=range_)
        .execute()
    )
    rows = result.get("values") or []
    if not rows or not rows[0]:
        if required:
            raise ValueError(f"Cell {range_} is empty or not found")
        return ""
    return rows[0][0]


def get_sheets_service():
    credentials = service_account.Credentials.from_service_account_file(
        str(GOOGLE_CREDENTIALS_PATH),
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    return build("sheets", "v4", credentials=credentials)


def send_to_slack(text: str) -> None:
    payload = json.dumps({
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": text,
                },
            }
        ]
    }).encode("utf-8")

    req = urllib.request.Request(
        SLACK_WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=10) as response:
        result = response.read().decode()

    if result == "ok":
        print("Message sent to Slack successfully!")
    else:
        raise RuntimeError(f"Unexpected Slack response: {result}")


if __name__ == "__main__":
    if not SLACK_WEBHOOK_URL:
        raise SystemExit("Укажите SLACK_WEBHOOK_URL в .env")

    service = get_sheets_service()

    person = read_cell(service, DUTY_PERSON_RANGE)
    task = read_cell(service, DUTY_TASK_RANGE, required=False)
    print(f"Person: {person!r}, Task: {task!r}")

    text = f"Дежурный сегодня: {person}"
    if task:
        text += f"\n>{task}"
    send_to_slack(text)
    print("Done.")
