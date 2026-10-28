from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "分仓库查询_web.py"


def load_stock_module():
    spec = importlib.util.spec_from_file_location("jky_stock_under_test", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeCursor:
    def __init__(self, module) -> None:
        self.module = module
        self.executed: list[str] = []
        self.rowcount = 1
        self._fetchone = ("existing",)

    def execute(self, sql: str) -> None:
        self.executed.append(sql)
        if "RENAME TABLE" in sql:
            raise RuntimeError("injected rename failure")

    def fetchone(self):
        return self._fetchone

    def close(self) -> None:
        return None


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self.cursor_instance = cursor
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return self.cursor_instance

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        return None


class FakePyMySQL:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    def connect(self, **kwargs):
        return self.connection


class SnapshotRollbackTests(unittest.TestCase):
    def test_rename_failure_preserves_old_table_and_cleans_tmp(self) -> None:
        module = load_stock_module()
        cursor = FakeCursor(module)
        connection = FakeConnection(cursor)
        fake_pymysql = FakePyMySQL(connection)
        import pandas as pd

        frame = pd.DataFrame([{column: "x" for column in module.FINAL_COLUMNS}])
        with patch.object(module, "pymysql", fake_pymysql):
            with self.assertRaisesRegex(RuntimeError, "injected rename failure"):
                module.write_exact_snapshot_to_mysql(frame, "ods_test_snapshot")

        statements = "\n".join(cursor.executed)
        self.assertIn("RENAME TABLE", statements)
        self.assertIn("DROP TABLE IF EXISTS `ods_test_snapshot_tmp_web_", statements)
        self.assertEqual(connection.rollbacks, 1)
        self.assertFalse(any("DROP TABLE IF EXISTS `ods_test_snapshot`\n" in sql for sql in cursor.executed))


if __name__ == "__main__":
    unittest.main()
