"""
Сбор тест-кейсов двух групп из TestOps и сохранение в JSON-файлы.

Группа A: Epic=Deposit/Withdraw, Feature=IBAN screen
  Признак: fullName содержит IbanScreen/IbansScreen в контексте depositWithdraw
  Примеры: DepositWithdrawIbanScreenEuroTests (iOS),
           depositWithdraw.IbansScreenTests (Android)

Группа B: Epic=IBANS
  Признак: название начинается с "IBANS:" (префикс добавлен вручную в TestOps)

Результат: group_a.json и group_b.json
Каждый файл содержит список кейсов с полями:
  id, name, fullName, automated, layer, project, steps_text, steps_raw
"""
from __future__ import annotations

import os
import json
import time
import re
import sys
from pathlib import Path
from typing import Optional

# ────────────────────────────────────────────────────────────────
# CONFIG
# ────────────────────────────────────────────────────────────────
def _load_env() -> dict:
    env = {}
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env


ENV = _load_env()
TESTOPS_URL = ENV.get("TESTOPS_URL", "https://vengacrypto.testops.cloud").rstrip("/")
TESTOPS_USERNAME = ENV.get("TESTOPS_USERNAME", "")
TESTOPS_PASSWORD = ENV.get("TESTOPS_PASSWORD", "")

# Проекты для поиска
ALL_PROJECTS = {
    2: "Venga UI",
    5: "Backend",
    6: "BPM",
    7: "EXCHANGE",
    8: "API",
    15: "Landing Tests",
    16: "Venga Retool",
    17: "Blockchain",
}

# ────────────────────────────────────────────────────────────────
# AUTH
# ────────────────────────────────────────────────────────────────
def get_token() -> str:
    import requests

    resp = requests.post(
        f"{TESTOPS_URL}/api/uaa/oauth/token",
        data={
            "grant_type": "password",
            "username": TESTOPS_USERNAME,
            "password": TESTOPS_PASSWORD,
            "client_id": "api",
            "scope": "openid",
        },
        timeout=30,
    )
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        raise RuntimeError("TestOps: не удалось получить access_token")
    return token


# ────────────────────────────────────────────────────────────────
# API
# ────────────────────────────────────────────────────────────────
def fetch_all_cases(token: str, project_id: int) -> list[dict]:
    """Все тест-кейсы проекта (постраничная загрузка)."""
    import requests

    headers = {"Authorization": f"Bearer {token}"}
    cases, page = [], 0
    while True:
        resp = requests.get(
            f"{TESTOPS_URL}/api/rs/testcase",
            headers=headers,
            params={"projectId": project_id, "size": 200, "page": page},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        cases.extend(data.get("content", []))
        if data.get("last", True) or len(cases) >= data.get("totalElements", 0):
            break
        page += 1
    return cases


def fetch_detail(token: str, tc_id: int) -> dict:
    """Детали одного кейса — в т.ч. fullName."""
    import requests

    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(
        f"{TESTOPS_URL}/api/rs/testcase/{tc_id}",
        headers=headers,
        timeout=30,
    )
    if resp.status_code == 404:
        return {}
    resp.raise_for_status()
    return resp.json()


def fetch_steps(token: str, tc_id: int) -> tuple[str, dict]:
    """
    Шаги тест-кейса.
    Возвращает (плоский текст шагов, сырой JSON ответа).
    """
    import requests

    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(
        f"{TESTOPS_URL}/api/rs/testcase/{tc_id}/step",
        headers=headers,
        timeout=30,
    )
    if resp.status_code != 200:
        return ("", {})
    raw = resp.json()
    text = _flatten_steps(raw)
    return (text, raw)


def _flatten_steps(data: dict) -> str:
    """Собирает все тексты шагов в плоскую строку (с отступами для дочерних)."""
    lines: list[str] = []

    shared = data.get("sharedSteps", {})
    scenario_steps = data.get("scenarioSteps", {})
    shared_scenario = data.get("sharedStepScenarioSteps", {})
    all_leaf = {**scenario_steps, **shared_scenario}

    def _step_text(step_id, indent=0) -> list[str]:
        step = scenario_steps.get(str(step_id)) or scenario_steps.get(step_id)
        if not step:
            step = shared_scenario.get(str(step_id)) or shared_scenario.get(step_id)
        if not step:
            return []
        result = []
        if step.get("sharedStepId"):
            sh = shared.get(str(step["sharedStepId"])) or shared.get(step["sharedStepId"])
            if sh:
                body = sh.get("body", "").strip()
                if body:
                    result.append("  " * indent + body)
                for child_id in sh.get("children", []):
                    result.extend(_step_text(child_id, indent + 1))
        else:
            body = step.get("body", "").strip()
            if body:
                result.append("  " * indent + body)
            for child_id in step.get("children", []):
                result.extend(_step_text(child_id, indent + 1))
        return result

    for step_id in data.get("root", {}).get("children", []):
        lines.extend(_step_text(step_id, 0))

    return "\n".join(lines)


# ────────────────────────────────────────────────────────────────
# CLASSIFICATION
# ────────────────────────────────────────────────────────────────
# Паттерны fullName/name для Group A (Deposit/Withdraw + IBAN screen)
_GROUP_A_PATTERNS = [
    re.compile(r"DepositWithdraw.*Iban.*Tests", re.IGNORECASE),
    re.compile(r"depositWithdraw[./].*[Ii]bans?[Ss]creen", re.IGNORECASE),
    re.compile(r"deposit.?withdraw.*iban", re.IGNORECASE),   # fallback по имени
]

# Паттерн для Group B (Epic=IBANS) — название начинается с "IBANS:"
_GROUP_B_PREFIX = re.compile(r"^IBANS\s*:", re.IGNORECASE)


def classify(name: str, full_name: str) -> Optional[str]:
    combined = f"{name} ||| {full_name}"

    for pat in _GROUP_A_PATTERNS:
        if pat.search(combined):
            return "A"

    if _GROUP_B_PREFIX.search(name):
        return "B"

    return None


# ────────────────────────────────────────────────────────────────
# MAIN
# ────────────────────────────────────────────────────────────────
def main():
    if not TESTOPS_USERNAME or not TESTOPS_PASSWORD:
        print("Укажите TESTOPS_USERNAME и TESTOPS_PASSWORD в .env", file=sys.stderr)
        sys.exit(1)

    print("Авторизация в TestOps...")
    token = get_token()
    print("OK\n")

    # ── Шаг 1: загрузить все кейсы (только id + name) ──────────
    print("Загрузка списков кейсов из всех проектов...")
    all_cases: list[dict] = []
    for proj_id, proj_name in ALL_PROJECTS.items():
        cases = fetch_all_cases(token, proj_id)
        for c in cases:
            c["_project_id"] = proj_id
            c["_project_name"] = proj_name
        all_cases.extend(cases)
        print(f"  [{proj_id}] {proj_name}: {len(cases)} кейсов")

    print(f"\nВсего кейсов: {len(all_cases)}\n")

    # ── Шаг 2: предфильтр — кандидаты на обе группы ───────────
    # Group A: "iban" или "deposit" в имени (нужен fullName для точной классификации)
    # Group B: название начинается с "IBANS:" (точный признак, добавлен вручную)
    iban_in_name = re.compile(r"\biban", re.IGNORECASE)
    deposit_in_name = re.compile(r"deposit", re.IGNORECASE)
    ibans_prefix = re.compile(r"^IBANS\s*:", re.IGNORECASE)

    candidates = [
        c for c in all_cases
        if iban_in_name.search(c.get("name", ""))
        or deposit_in_name.search(c.get("name", ""))
        or ibans_prefix.search(c.get("name", ""))
    ]
    print(f"Кандидаты (IBAN/Deposit в имени, или IBANS: префикс): {len(candidates)}")

    # ── Шаг 3: загрузить fullName для кандидатов ───────────────
    print("Загрузка деталей кандидатов (fullName)...")
    enriched: list[dict] = []
    for i, c in enumerate(candidates, 1):
        detail = fetch_detail(token, c["id"])
        full_name = detail.get("fullName", "")
        enriched.append({
            "id": c["id"],
            "project_id": c["_project_id"],
            "project_name": c["_project_name"],
            "name": c.get("name", ""),
            "fullName": full_name,
            "automated": c.get("automated", False),
            "layer": (c.get("testLayer") or {}).get("name", ""),
        })
        if i % 10 == 0 or i == len(candidates):
            print(f"  {i}/{len(candidates)} деталей загружено")
        time.sleep(0.05)

    # ── Шаг 4: классификация ────────────────────────────────────
    group_a: list[dict] = []
    group_b: list[dict] = []
    for tc in enriched:
        grp = classify(tc["name"], tc["fullName"])
        if grp == "A":
            group_a.append(tc)
        elif grp == "B":
            group_b.append(tc)

    print(f"\nГруппа A (Deposit/Withdraw + IBAN screen): {len(group_a)} кейсов")
    for tc in group_a:
        print(f"  #{tc['id']} [{tc['layer']}] {tc['name']}")

    print(f"\nГруппа B (IBANS): {len(group_b)} кейсов")
    for tc in group_b:
        print(f"  #{tc['id']} [{tc['layer']}] {tc['name']}")

    # ── Шаг 5: загрузить шаги для обеих групп ──────────────────
    print("\nЗагрузка шагов для Группы A...")
    for tc in group_a:
        text, raw = fetch_steps(token, tc["id"])
        tc["steps_text"] = text
        tc["steps_raw"] = raw
        label = "есть шаги" if text.strip() else "нет шагов"
        print(f"  #{tc['id']} — {label}")
        time.sleep(0.05)

    print("\nЗагрузка шагов для Группы B...")
    for tc in group_b:
        text, raw = fetch_steps(token, tc["id"])
        tc["steps_text"] = text
        tc["steps_raw"] = raw
        label = "есть шаги" if text.strip() else "нет шагов"
        print(f"  #{tc['id']} — {label}")
        time.sleep(0.05)

    # ── Шаг 6: сохранить JSON ──────────────────────────────────
    out_dir = Path(__file__).resolve().parent
    path_a = out_dir / "group_a.json"
    path_b = out_dir / "group_b.json"

    with open(path_a, "w", encoding="utf-8") as f:
        json.dump(group_a, f, ensure_ascii=False, indent=2)
    with open(path_b, "w", encoding="utf-8") as f:
        json.dump(group_b, f, ensure_ascii=False, indent=2)

    print(f"\nСохранено:")
    print(f"  {path_a}  ({len(group_a)} кейсов)")
    print(f"  {path_b}  ({len(group_b)} кейсов)")
    print("\nГотово. Передайте эти два файла для анализа дублей.")


if __name__ == "__main__":
    main()
