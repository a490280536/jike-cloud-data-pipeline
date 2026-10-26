from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "登录态捕获助手.py"
PREFLIGHT = ROOT / "scripts" / "吉客云同步预检.py"
LAUNCHER = ROOT / "启动登录态捕获助手.cmd"
AUTOSTART_INSTALLER = ROOT / "scripts" / "install_auth_capture_autostart.ps1"


class AuthCaptureAssistantCliTests(unittest.TestCase):
    def test_preflight_allows_sales_export_without_common_verify(self) -> None:
        spec = importlib.util.spec_from_file_location("jky_preflight", PREFLIGHT)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp_dir:
            captured = Path(temp_dir) / "销售单查询_curl.txt"
            captured.write_text(
                "curl 'https://web.jackyun.com/jkyun/excel-service/manager/startExcelExport' "
                "-H 'authorization: Bearer test-token' -H 'ati: test-ati' "
                "-b 'token=test-cookie' --data-raw 'excelType=2&pageSize=50'\n",
                encoding="utf-8",
            )
            self.assertEqual(module.inspect_curl(captured), [])

    def test_preflight_capability_manifest_marks_unavailable_pages_out_of_scope(self) -> None:
        spec = importlib.util.spec_from_file_location("jky_preflight_capabilities", PREFLIGHT)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / "capability_manifest.json"
            manifest.write_text(
                '{"out_of_scope":{"批次货品库存查询_curl.txt":"账号无权限/无页面",'
                '"预留单查询_curl.txt":"账号无权限/无页面"}}',
                encoding="utf-8",
            )
            self.assertEqual(
                module.load_out_of_scope(manifest),
                {
                    "批次货品库存查询_curl.txt": "账号无权限/无页面",
                    "预留单查询_curl.txt": "账号无权限/无页面",
                },
            )

    @unittest.skipUnless(os.name == "nt", "Windows-only autostart installer")
    def test_autostart_installer_dry_run_describes_hidden_task(self) -> None:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(AUTOSTART_INSTALLER),
                "-DryRun",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )

        combined = completed.stdout + completed.stderr
        self.assertEqual(completed.returncode, 0, combined)
        self.assertIn("JikeAuthCaptureAssistant", combined)
        self.assertIn("start_auth_capture_hidden.ps1", combined)
        self.assertIn(str(ROOT), combined)
        self.assertIn("logs", combined)

    def test_bscm_follow_up_does_not_claim_uncaptured_files_were_completed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            curl_dir = workspace / "curl"
            curl_dir.mkdir()
            fixtures = {
                "进口超市上海仓_正向全链路数据_curl.txt": (
                    "https://bscm.jinritemai.com/scm/visualized/"
                    "exportFulfillOrderList?subject_aid=305219"
                ),
                "进口超市上海仓_货权转移采购单_curl.txt": (
                    "https://bscm.jinritemai.com/api/procurement/po/list?"
                    "orderType=5&createTimeStart=1&createTimeEnd=2&page=1&pageSize=20&"
                    "subject_aid=305219&msToken=x&a_bogus=x&verifyFp=x&fp=x"
                ),
                "进口超市上海仓_货权转移采购单导出_curl.txt": (
                    "https://bscm.jinritemai.com/api/gei/generalExport?"
                    "bizType=TransferProcurementOrder&queryParams=%7B%7D&subject_aid=305219&"
                    "msToken=x&a_bogus=x&verifyFp=x&fp=x"
                ),
            }
            for name, url in fixtures.items():
                (curl_dir / name).write_text(
                    f"curl '{url}' -H 'user-agent: old-agent' -b 'sessionid=old-cookie'\n",
                    encoding="utf-8",
                )
            source = workspace / "captured.txt"
            source.write_text(
                "curl 'https://bscm.jinritemai.com/scm/visualized/"
                "exportFulfillOrderList?subject_aid=305219' "
                "-H 'user-agent: new-agent' -b 'sessionid=new-cookie'\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--source",
                    str(source),
                    "--curl-dir",
                    str(curl_dir),
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env={**os.environ, "PYTHONUTF8": "1"},
            )

            combined = completed.stdout + completed.stderr
            self.assertEqual(completed.returncode, 0, combined)
            self.assertIn("本次仅更新", combined)
            self.assertIn("其余文件未在本次重新捕获", combined)
            self.assertNotIn("四件套已齐", combined)
            self.assertNotIn("[OK]", combined)
            self.assertLessEqual(len([line for line in combined.splitlines() if line.strip()]), 3)

    @unittest.skipUnless(os.name == "nt", "Windows-only batch launcher")
    def test_windows_launcher_forwards_help_without_cmd_parse_errors(self) -> None:
        completed = subprocess.run(
            ["cmd.exe", "/d", "/c", "call", str(LAUNCHER), "--help"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3,
        )

        combined = completed.stdout + completed.stderr
        self.assertEqual(completed.returncode, 0, combined)
        self.assertNotIn("not recognized", combined)
        self.assertIn("--once", combined)

    def test_routes_general_export_curl_to_purchase_export_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            curl_dir = workspace / "curl"
            curl_dir.mkdir()
            source = workspace / "captured.txt"
            captured = (
                "curl 'https://bscm.jinritemai.com/api/gei/generalExport?"
                "bizType=TransferProcurementOrder&queryParams=%7B%7D&subject_aid=305219&"
                "msToken=x&a_bogus=x&verifyFp=x&fp=x' "
                "-H 'user-agent: test-agent' -b 'sessionid=test-cookie'\n"
            )
            source.write_text(captured, encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--source",
                    str(source),
                    "--curl-dir",
                    str(curl_dir),
                    "--no-follow-up",
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            target = curl_dir / "进口超市上海仓_货权转移采购单导出_curl.txt"
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertEqual(target.read_text(encoding="utf-8"), captured)
            self.assertEqual(len(list(curl_dir.glob("*_curl.txt"))), 1)

    def test_routes_jackyun_stock_query_without_common_verify(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            curl_dir = workspace / "curl"
            source = workspace / "captured.txt"
            captured = (
                "curl 'https://web.jackyun.com/api/stockSkuList?warehouseId=1' "
                "-H 'user-agent: test-agent' -b 'sessionid=test-cookie'\n"
            )
            source.write_text(captured, encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--source",
                    str(source),
                    "--curl-dir",
                    str(curl_dir),
                    "--no-follow-up",
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            target = curl_dir / "分仓库查询_curl.txt"
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertEqual(target.read_text(encoding="utf-8"), captured)

    def test_routes_jackyun_read_only_list_endpoints_without_common_verify(self) -> None:
        cases = {
            "listGoodsDoc": "入库查询_curl.txt",
            "getsaleschannelinfoforcols": "渠道列表_curl.txt",
            "batch.stock.search/pagelist": "批次货品库存查询_curl.txt",
        }
        for endpoint, filename in cases.items():
            with self.subTest(endpoint=endpoint):
                with tempfile.TemporaryDirectory() as temp_dir:
                    workspace = Path(temp_dir)
                    curl_dir = workspace / "curl"
                    source = workspace / "captured.txt"
                    captured = (
                        f"curl 'https://web.jackyun.com/api/{endpoint}' "
                        "-H 'user-agent: test-agent' -b 'sessionid=test-cookie'\n"
                    )
                    source.write_text(captured, encoding="utf-8")

                    completed = subprocess.run(
                        [
                            sys.executable,
                            str(SCRIPT),
                            "--source",
                            str(source),
                            "--curl-dir",
                            str(curl_dir),
                            "--no-follow-up",
                        ],
                        check=False,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                    )

                    target = curl_dir / filename
                    self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                    self.assertEqual(target.read_text(encoding="utf-8"), captured)

    def test_routes_jackyun_export_types_to_distinct_files(self) -> None:
        cases = {
            "excelType=2": "销售单查询_curl.txt",
            "excelType=11": "销售单明细账_curl.txt",
            "excelType=reserve.search": "预留单查询_curl.txt",
        }
        for marker, filename in cases.items():
            with self.subTest(marker=marker):
                with tempfile.TemporaryDirectory() as temp_dir:
                    workspace = Path(temp_dir)
                    curl_dir = workspace / "curl"
                    source = workspace / "captured.txt"
                    captured = (
                        "curl 'https://web.jackyun.com/jkyun/excel-service/manager/startExcelExport' "
                        "-H 'authorization: Bearer test-token' "
                        "-H 'user-agent: test-agent' -b 'token=test-cookie' "
                        f"--data-raw 'commonVerify=test-verify&{marker}'\n"
                    )
                    source.write_text(captured, encoding="utf-8")

                    completed = subprocess.run(
                        [
                            sys.executable,
                            str(SCRIPT),
                            "--source",
                            str(source),
                            "--curl-dir",
                            str(curl_dir),
                            "--no-follow-up",
                        ],
                        check=False,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                    )

                    target = curl_dir / filename
                    self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                    self.assertEqual(target.read_text(encoding="utf-8"), captured)

    def test_accepts_non_plaintext_jackyun_export_without_common_verify(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            curl_dir = workspace / "curl"
            curl_dir.mkdir()
            source = workspace / "captured.txt"
            source.write_text(
                "curl 'https://web.jackyun.com/jkyun/excel-service/manager/startExcelExport' "
                "-H 'authorization: Bearer test-token' -H 'user-agent: test-agent' "
                "-b 'token=test-cookie' --data-raw 'pageIndex=0&pageSize=50'\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--source",
                    str(source),
                    "--curl-dir",
                    str(curl_dir),
                    "--no-follow-up",
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            target = curl_dir / "每日更新_curl.txt"
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertTrue(target.exists())
            self.assertNotIn("commonVerify", target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
