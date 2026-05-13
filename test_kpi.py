#!/usr/bin/env python3
"""
Unit-тесты для KPI-калькулятора.
Запуск: python -m pytest test_kpi.py -v
"""

import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
import requests

# ─── Импортируем тестируемые функции ──────────────────────────────────────────
import importlib, sys, types

# Загружаем модуль динамически, чтобы не запускать main()
import KPI_report_generator as kpi_mod

parse_number    = kpi_mod.parse_number
calc_kpi        = kpi_mod.calc_kpi
post_measurement = kpi_mod.post_measurement
send_all_results = kpi_mod.send_all_results
ask_period       = kpi_mod.ask_period
KPI_GUIDS        = kpi_mod.KPI_GUIDS


# ═══════════════════════════════════════════════════════════════════════════════
#  БЛОК 1 — parse_number (тесты 1-6)
# ═══════════════════════════════════════════════════════════════════════════════

class TestParseNumber:

    def test_01_integer_string(self):
        """T01 — целое число без дробной части"""
        assert parse_number("42") == Decimal("42")

    def test_02_decimal_dot(self):
        """T02 — число с точкой как разделителем"""
        assert parse_number("97.6") == Decimal("97.6")

    def test_03_decimal_comma(self):
        """T03 — число с запятой как разделителем (европейский формат)"""
        assert parse_number("97,6") == Decimal("97.6")

    def test_04_leading_trailing_spaces(self):
        """T04 — пробелы вокруг числа игнорируются"""
        assert parse_number("  99.5  ") == Decimal("99.5")

    def test_05_zero(self):
        """T05 — нулевое значение"""
        assert parse_number("0") == Decimal("0")

    def test_06_large_number(self):
        """T06 — большое число без потери точности"""
        assert parse_number("100000.99") == Decimal("100000.99")


# ═══════════════════════════════════════════════════════════════════════════════
#  БЛОК 2 — calc_kpi / higher_better (тесты 7-14)
# ═══════════════════════════════════════════════════════════════════════════════

def make_kpi(actual, type_="higher_better", minimum=95, target=99, weight=0.2):
    return {
        "name":    "Test KPI",
        "minimum": Decimal(str(minimum)),
        "target":  Decimal(str(target)),
        "weight":  Decimal(str(weight)),
        "type":    type_,
        "actual":  Decimal(str(actual)),
    }


class TestCalcKpiHigherBetter:

    def test_07_actual_below_minimum_gives_zero(self):
        """T07 — actual ≤ minimum → intermediate = 0, final = 0"""
        result = calc_kpi(make_kpi(actual=90))
        assert result["intermediate"] == 0.0
        assert result["final"] == 0.0

    def test_08_actual_equals_minimum_gives_zero(self):
        """T08 — actual == minimum → intermediate = 0"""
        result = calc_kpi(make_kpi(actual=95))
        assert result["intermediate"] == 0.0

    def test_09_actual_equals_target_gives_full_weight(self):
        """T09 — actual == target → percent = 1, final = weight"""
        result = calc_kpi(make_kpi(actual=99))
        assert abs(result["intermediate"] - 1.0) < 1e-9
        assert abs(result["final"] - 0.2) < 1e-9

    def test_10_actual_above_target_capped_at_weight(self):
        """T10 — actual > target → final не превышает weight"""
        result = calc_kpi(make_kpi(actual=105))
        assert result["final"] == pytest.approx(0.2)

    def test_11_actual_midpoint_gives_half_weight(self):
        """T11 — actual = (min+target)/2 → intermediate ≈ 0.5, final ≈ 0.1"""
        result = calc_kpi(make_kpi(actual=97))   # (95+99)/2 = 97
        assert abs(result["intermediate"] - 0.5) < 1e-9
        assert abs(result["final"] - 0.1) < 1e-9

    def test_12_final_never_exceeds_weight(self):
        """T12 — final ≤ weight при любых корректных значениях"""
        result = calc_kpi(make_kpi(actual=999))
        assert result["final"] <= 0.2 + 1e-9

    def test_13_weight_zero_gives_zero_final(self):
        """T13 — нулевой вес → final = 0 независимо от actual"""
        result = calc_kpi(make_kpi(actual=99, weight=0))
        assert result["final"] == 0.0

    def test_14_result_contains_all_keys(self):
        """T14 — результат содержит все ожидаемые ключи"""
        result = calc_kpi(make_kpi(actual=97))
        for key in ("name", "minimum", "target", "weight", "type", "actual",
                    "intermediate", "final"):
            assert key in result


# ═══════════════════════════════════════════════════════════════════════════════
#  БЛОК 3 — calc_kpi / lower_better (тесты 15-19)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalcKpiLowerBetter:

    def test_15_actual_above_minimum_gives_zero(self):
        """T15 — actual ≥ minimum (lower_better) → percent = 0"""
        result = calc_kpi(make_kpi(actual=16, type_="lower_better",
                                   minimum=15, target=10))
        assert result["intermediate"] == 0.0
        assert result["final"] == 0.0

    def test_16_actual_equals_minimum_gives_zero(self):
        """T16 — actual == minimum → percent = 0"""
        result = calc_kpi(make_kpi(actual=15, type_="lower_better",
                                   minimum=15, target=10))
        assert result["intermediate"] == 0.0

    def test_17_actual_equals_target_gives_full_weight(self):
        """T17 — actual == target → percent = 1, final = weight"""
        result = calc_kpi(make_kpi(actual=10, type_="lower_better",
                                   minimum=15, target=10))
        assert abs(result["intermediate"] - 1.0) < 1e-9
        assert abs(result["final"] - 0.2) < 1e-9

    def test_18_actual_below_target_intermediate_above_one(self):
        """T18 — actual < target → percent > 1, но final зажат весом"""
        result = calc_kpi(make_kpi(actual=5, type_="lower_better",
                                   minimum=15, target=10))
        assert result["intermediate"] > 1.0
        assert result["final"] == pytest.approx(0.2)

    def test_19_midpoint_lower_better(self):
        """T19 — actual = midpoint → intermediate ≈ 0.5"""
        result = calc_kpi(make_kpi(actual=12.5, type_="lower_better",
                                   minimum=15, target=10))
        assert abs(result["intermediate"] - 0.5) < 1e-9


# ═══════════════════════════════════════════════════════════════════════════════
#  БЛОК 4 — post_measurement (тесты 20-23)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPostMeasurement:

    @patch("KPI_report_generator.requests.post")
    def test_20_successful_post_prints_ok(self, mock_post, capsys):
        """T20 — успешный ответ API → выводит ✓"""
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_post.return_value = mock_resp

        post_measurement("test-guid", "2026-03-01T12:00:00.000Z", 0.18)
        out = capsys.readouterr().out
        assert "✓" in out

    @patch("KPI_report_generator.requests.post")
    def test_21_failed_post_prints_error(self, mock_post, capsys):
        """T21 — неуспешный ответ API → выводит ✗ и код ошибки"""
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        mock_post.return_value = mock_resp

        post_measurement("bad-guid", "2026-03-01T12:00:00.000Z", 0.1)
        out = capsys.readouterr().out
        assert "✗" in out
        assert "401" in out

    @patch("KPI_report_generator.requests.post")
    def test_22_correct_url_built(self, mock_post):
        """T22 — URL формируется с правильным guid"""
        mock_resp = MagicMock(); mock_resp.ok = True
        mock_post.return_value = mock_resp

        guid = "abc-123"
        post_measurement(guid, "2026-03-01T12:00:00.000Z", 0.15)
        call_url = mock_post.call_args[0][0]
        assert guid in call_url

    @patch("KPI_report_generator.requests.post")
    def test_23_payload_is_list_with_value(self, mock_post):
        """T23 — payload — список с одним объектом, содержащим value"""
        mock_resp = MagicMock(); mock_resp.ok = True
        mock_post.return_value = mock_resp

        post_measurement("g1", "2026-01-01T00:00:00.000Z", 99.5)
        payload = mock_post.call_args[1]["json"]
        assert isinstance(payload, list)
        assert payload[0]["value"] == 99.5


# ═══════════════════════════════════════════════════════════════════════════════
#  БЛОК 5 — send_all_results (тесты 24-26)
# ═══════════════════════════════════════════════════════════════════════════════

class TestSendAllResults:

    @patch("KPI_report_generator.post_measurement")
    def test_24_posts_for_each_kpi_plus_total(self, mock_post):
        """T24 — вызывается N+1 раз (по одному на KPI + итог)"""
        results = [
            {"name": "Percentage of nomination delivered",        "final": 0.18},
            {"name": "Percentage of time when all control works", "final": 0.17},
            {"name": "MQTT ids working properly",                 "final": 0.19},
            {"name": "Visualizer online time",                    "final": 0.16},
            {"name": "Time in days for projects from step 3 till step 5", "final": 0.15},
        ]
        send_all_results(results, 0.85, "2026-03-01T12:00:00.000Z")
        assert mock_post.call_count == len(results) + 1

    @patch("KPI_report_generator.post_measurement")
    def test_25_unknown_kpi_name_skipped(self, mock_post, capsys):
        """T25 — KPI с неизвестным именем пропускается (не вызывает post)"""
        results = [{"name": "Unknown KPI XYZ", "final": 0.1}]
        send_all_results(results, 0.1, "2026-03-01T12:00:00.000Z")
        # Должен быть вызван только для итогового KPI result
        assert mock_post.call_count == 1

    @patch("KPI_report_generator.post_measurement")
    def test_26_total_posted_with_correct_value(self, mock_post):
        """T26 — итоговое значение total передаётся в post_measurement"""
        results = [{"name": "Percentage of nomination delivered", "final": 0.2}]
        send_all_results(results, 0.99, "2026-03-01T12:00:00.000Z")
        # Последний вызов — KPI result с total
        last_call = mock_post.call_args_list[-1]
        assert last_call[0][2] == 0.99  # третий позиционный аргумент — value


# ═══════════════════════════════════════════════════════════════════════════════
#  БЛОК 6 — ask_period (тесты 27-28)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAskPeriod:

    @patch("builtins.input", return_value="2026-03")
    def test_27_valid_period_returns_timestamp(self, _):
        """T27 — корректный ввод → возвращает ISO timestamp"""
        ts = ask_period()
        assert ts == "2026-03-01T12:00:00.000Z"

    @patch("builtins.input", side_effect=["bad-input", "13-2026", "2026-05"])
    def test_28_invalid_then_valid_period(self, _):
        """T28 — после некорректных вводов принимает корректный"""
        ts = ask_period()
        assert ts == "2026-05-01T12:00:00.000Z"


# ═══════════════════════════════════════════════════════════════════════════════
#  БЛОК 7 — KPI_GUIDS и интеграция (тесты 29-30)
# ═══════════════════════════════════════════════════════════════════════════════

class TestKpiGuids:

    def test_29_all_expected_kpi_names_in_guids(self):
        """T29 — словарь KPI_GUIDS содержит все 6 ожидаемых ключей"""
        expected_keys = {
            "Percentage of nomination delivered",
            "Percentage of time when all control works",
            "Visualizer online time",
            "MQTT ids working properly",
            "Time in days for projects from step 3 till step 5",
            "KPI result",
        }
        assert expected_keys == set(KPI_GUIDS.keys())

    def test_30_full_kpi_pipeline_sum_correct(self):
        """T30 — интеграционный тест: сумма пяти KPI по 0.2 = 1.0"""
        kpis = [
            {"name": "A", "minimum": Decimal("0"),   "target": Decimal("100"),
             "weight": Decimal("0.2"), "type": "higher_better", "actual": Decimal("100")},
            {"name": "B", "minimum": Decimal("0"),   "target": Decimal("100"),
             "weight": Decimal("0.2"), "type": "higher_better", "actual": Decimal("100")},
            {"name": "C", "minimum": Decimal("0"),   "target": Decimal("100"),
             "weight": Decimal("0.2"), "type": "higher_better", "actual": Decimal("100")},
            {"name": "D", "minimum": Decimal("0"),   "target": Decimal("100"),
             "weight": Decimal("0.2"), "type": "higher_better", "actual": Decimal("100")},
            {"name": "E", "minimum": Decimal("100"), "target": Decimal("0"),
             "weight": Decimal("0.2"), "type": "lower_better",  "actual": Decimal("0")},
        ]
        results = [calc_kpi(k) for k in kpis]
        total = sum(r["final"] for r in results)
        assert abs(total - 1.0) < 1e-9