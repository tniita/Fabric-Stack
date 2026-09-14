import json
from pathlib import Path
import sqlite3
import unittest

from seed import build_tables, validate_tables


TEST_DIRECTORY = Path(__file__).parent
ACCEPTANCE = json.loads((TEST_DIRECTORY / "acceptance-cases.json").read_text())
QUERY = (TEST_DIRECTORY / "validation.sql").read_text()


def query_rows(tables):
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    try:
        for name, rows in tables.items():
            columns = ", ".join(f'"{key}" {"INTEGER" if type(value) is int else "TEXT"}'
                                for key, value in rows[0].items())
            connection.execute(f'CREATE TABLE "fiq_{name}" ({columns})')
            placeholders = ", ".join("?" for key in rows[0])
            connection.executemany(f'INSERT INTO "fiq_{name}" VALUES ({placeholders})',
                                   [tuple(row.values()) for row in rows])
        return [dict(row) for row in connection.execute(QUERY)]
    finally:
        connection.close()


class SeedTests(unittest.TestCase):
    def test_counts_and_determinism(self):
        tables = build_tables()
        self.assertEqual({name: len(rows) for name, rows in tables.items()},
                         dict(suppliers=3, products=12, inventory=12, orders=8, order_lines=16))
        self.assertEqual(tables, build_tables())

    def test_initial_and_replenished(self):
        for scenario, expected in (
            ("initial", {"O001": 4, "O002": 2, "O003": 3}),
            ("replenished", {"O002": 2, "O003": 3}),
        ):
            with self.subTest(scenario=scenario):
                tables = build_tables(scenario)
                self.assertEqual({row["orderId"]: row["shortageQty"]
                                  for row in tables["order_lines"] if row["shortageQty"]}, expected)
                validate_tables(tables)

    def test_reset_is_independent(self):
        initial = build_tables()
        build_tables("replenished")
        self.assertEqual(initial, build_tables("initial"))

    def test_rejects_invalid_data(self):
        mutations = (
            lambda tables: tables["orders"].append(tables["orders"][0].copy()),
            lambda tables: tables["products"][0].update(supplierId="missing"),
            lambda tables: tables["inventory"][0].update(onHandQty=0),
            lambda tables: tables["order_lines"][0].update(allocatedQty=-1),
            lambda tables: tables["order_lines"][0].update(shortageQty=99),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                tables = build_tables()
                mutate(tables)
                with self.assertRaises(ValueError):
                    validate_tables(tables)

    def test_rejects_unknown_scenario(self):
        with self.assertRaises(ValueError):
            build_tables("typo")

    def test_sql_matches_independent_expected_rows(self):
        for scenario, expected in ACCEPTANCE["expectedRows"].items():
            with self.subTest(scenario=scenario):
                self.assertEqual(query_rows(build_tables(scenario)), expected)

    def test_sql_excludes_closed_and_outside_window(self):
        for status, due_at in (
            ("Closed", "2026-09-14T12:00:00Z"),
            ("Open", "2026-09-21T00:00:00Z"),
            ("Open", "2026-09-13T23:59:59Z"),
        ):
            with self.subTest(status=status, due_at=due_at):
                tables = build_tables()
                tables["orders"][0].update(status=status, dueAt=due_at)
                self.assertEqual(query_rows(tables), ACCEPTANCE["expectedRows"]["replenished"])

    def test_sql_includes_window_start(self):
        tables = build_tables()
        tables["orders"][0]["dueAt"] = ACCEPTANCE["window"]["startInclusive"]
        self.assertEqual(query_rows(tables), ACCEPTANCE["expectedRows"]["initial"])


if __name__ == "__main__":
    unittest.main()