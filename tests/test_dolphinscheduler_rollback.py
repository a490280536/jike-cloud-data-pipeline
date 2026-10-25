from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "配置海豚工作流.py"


def load_scheduler_module():
    spec = importlib.util.spec_from_file_location("jky_scheduler_under_test", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeDolphinClient:
    def __init__(self, module) -> None:
        self.module = module
        self.releases: list[tuple[int, int, str]] = []
        self.requests: list[tuple[str, str]] = []

    def definitions(self, project_code: int) -> list[dict[str, object]]:
        return [{"name": "demo", "code": 77, "releaseState": "ONLINE"}]

    def release(self, project_code: int, code: int, state: str) -> None:
        self.releases.append((project_code, code, state))

    def task_codes(self, project_code: int, count: int) -> list[int]:
        return [101 + index for index in range(count)]

    def request(self, method: str, path: str, **kwargs):
        self.requests.append((method, path))
        if method == "PUT":
            raise RuntimeError("injected update failure")
        return None


class CreateFailureClient(FakeDolphinClient):
    def definitions(self, project_code: int) -> list[dict[str, object]]:
        return []

    def request(self, method: str, path: str, **kwargs):
        self.requests.append((method, path))
        if method == "POST":
            raise RuntimeError("injected create failure")
        return None


class DolphinSchedulerRollbackTests(unittest.TestCase):
    def test_failed_update_restores_existing_online_workflow(self) -> None:
        module = load_scheduler_module()
        client = FakeDolphinClient(module)
        task = module.TaskSpec("demo-task", "Demo task", "true", "test")

        with self.assertRaisesRegex(RuntimeError, "injected update failure"):
            module.upsert_workflow(
                client,
                project_code=1,
                name="demo",
                description="test",
                tasks=(task,),
                edges=(),
                online=True,
            )

        self.assertEqual(client.releases, [(1, 77, "OFFLINE"), (1, 77, "ONLINE")])
        self.assertEqual(client.requests, [("PUT", "/projects/1/process-definition/77")])

    def test_failed_create_never_releases_new_workflow_online(self) -> None:
        module = load_scheduler_module()
        client = CreateFailureClient(module)
        task = module.TaskSpec("demo-task", "Demo task", "true", "test")

        with self.assertRaisesRegex(RuntimeError, "injected create failure"):
            module.upsert_workflow(
                client,
                project_code=1,
                name="new-workflow",
                description="test",
                tasks=(task,),
                edges=(),
                online=True,
            )

        self.assertEqual(client.releases, [])
        self.assertEqual(client.requests[0], ("POST", "/projects/1/process-definition"))


if __name__ == "__main__":
    unittest.main()
