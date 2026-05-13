#!/usr/bin/env python3
from decimal import Decimal
import requests


# ─────────────────────────────────────────────
#  API
# ─────────────────────────────────────────────

API_BASE_URL = "https://api.imby.energy/Db/SetMeasurementData"
API_TOKEN    = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE4NzU3OTY3NjEsImlzcyI6Imh0dHBzOi8vbG9jYWxob3N0OjcyOTMiLCJhdWQiOiJodHRwczovL2xvY2FsaG9zdDo3MjkzIn0.UW6Dla-OHuoRt_VDiYtrLSSA9XiAEOYs2BhIQlmBRm4"   # вставьте токен сюда

KPI_GUIDS = {
    "Percentage of nomination delivered":                "f56d54bd-8ba2-4729-b8d0-4ee9b8d1773c",
    "Percentage of time when all control works":         "0591968b-0192-4a9a-98fc-1fb0ce8c7ab7",
    "Visualizer online time":                            "4018528c-a752-4ae9-9357-699e59418c73",
    "MQTT ids working properly":                         "58d0985e-33a2-4844-b262-851757f1b238",
    "Time in days for projects from step 3 till step 5": "9df291f9-9364-41a8-ab72-fec46a77a5df",
    "KPI result":                                        "85a895a5-acbf-490a-adb9-b00d1482d986",
}


def post_measurement(guid: str, timestamp: str, value: float) -> None:
    """Отправляет одно измерение в базу данных через API."""
    url = f"{API_BASE_URL}?measurementVersionGuid={guid}"
    headers = {
        "accept": "*/*",
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = [{"timeStamp": timestamp, "value": value}]

    response = requests.post(url, headers=headers, json=payload)

    if response.ok:
        print(f"  ✓ Записано (guid={guid}, value={value})")
    else:
        print(f"  ✗ Ошибка {response.status_code} для guid={guid}: {response.text}")


def send_all_results(results: list, total: float, timestamp: str) -> None:
    """Отправляет все KPI-показатели и итоговую сумму в БД."""
    print("\nОтправка данных в БД...")

    for r in results:
        guid = KPI_GUIDS.get(r["name"])
        if not guid:
            print(f"  ✗ GUID не найден для '{r['name']}', пропуск")
            continue
        post_measurement(guid, timestamp, r["final"])

    # Итоговая сумма
    post_measurement(KPI_GUIDS["KPI result"], timestamp, total)


# ─────────────────────────────────────────────
#  Ввод и расчёт
# ─────────────────────────────────────────────

def parse_number(raw: str) -> Decimal:
    return Decimal(raw.strip().replace(",", "."))


def ask_period() -> str:
    """Запрашивает год и месяц, возвращает timestamp вида 2026-03-01T12:00:00.000Z."""
    while True:
        try:
            raw = input("Введите период в формате YYYY-MM (например, 2026-03): ").strip()
            year, month = raw.split("-")
            year, month = int(year), int(month)
            if not (1 <= month <= 12):
                raise ValueError
            return f"{year:04d}-{month:02d}-01T12:00:00.000Z"
        except Exception:
            print("Некорректный формат. Введите год и месяц, например: 2026-03")


def ask_value(kpi_name: str) -> Decimal:
    while True:
        try:
            raw = input(f"'{kpi_name}' – введите исходное значение: ")
            return parse_number(raw)
        except Exception:
            print("Некорректное значение. Введите число, например: 97.6")


def calc_kpi(kpi: dict) -> dict:
    a  = kpi["actual"]
    mn = kpi["minimum"]
    tg = kpi["target"]
    w  = kpi["weight"]

    if kpi["type"] == "higher_better":
        if a <= mn:
            percent = Decimal("0")
        elif a <= tg:
            percent = (a - mn) / (tg - mn)
        else:
            percent = Decimal("1")

    else:  # lower_better
        if a >= mn:
            percent = Decimal("0")
        else:
            percent = (a - mn) / (tg - mn)

    final = float(min(w * percent, Decimal("0.2")))

    return {
        **kpi,
        "intermediate": float(percent),
        "final": final,
    }


# ─────────────────────────────────────────────
#  Точка входа
# ─────────────────────────────────────────────

def main():
    kpis = [
        {
            "name":    "Percentage of nomination delivered",
            "minimum": Decimal("95"),
            "target":  Decimal("99.5"),
            "weight":  Decimal("0.2"),
            "type":    "higher_better",
        },
        {
            "name":    "Percentage of time when all control works",
            "minimum": Decimal("95"),
            "target":  Decimal("99"),
            "weight":  Decimal("0.2"),
            "type":    "higher_better",
        },
        {
            "name":    "MQTT ids working properly",
            "minimum": Decimal("98"),
            "target":  Decimal("99.9"),
            "weight":  Decimal("0.2"),
            "type":    "higher_better",
        },
        {
            "name":    "Visualizer online time",
            "minimum": Decimal("95"),
            "target":  Decimal("99"),
            "weight":  Decimal("0.2"),
            "type":    "higher_better",
        },
        {
            "name":    "Time in days for projects from step 3 till step 5",
            "minimum": Decimal("15"),
            "target":  Decimal("10"),
            "weight":  Decimal("0.2"),
            "type":    "lower_better",
        },
    ]

    timestamp = ask_period()

    for kpi in kpis:
        kpi["actual"] = ask_value(kpi["name"])

    results = [calc_kpi(kpi) for kpi in kpis]
    total   = sum(r["final"] for r in results)

    print("\nИтоги KPI:")
    for r in results:
        print(f"  {r['name']}: intermediate={r['intermediate']}, final={r['final']}")
    print(f"  SUM = {total}")

    send_all_results(results, total, timestamp)


if __name__ == "__main__":
    main()