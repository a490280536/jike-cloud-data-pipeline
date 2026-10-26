#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DolphinScheduler 日常同步前置检查。

检查本地运行条件、cURL 关键认证材料，并调用渠道列表第一页验证登录态；
不发起导出，也不修改数据库。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parent.parent
CURL_DIR = ROOT / "curl"

REQUIRED_CURLS = (
    "销售单查询_curl.txt",
    "销售单明细账_curl.txt",
    "入库查询_curl.txt",
    "渠道列表_curl.txt",
    "总库存查询_curl.txt",
    "分仓库查询_curl.txt",
    "批次货品库存查询_curl.txt",
    "预留单查询_curl.txt",
    "进口超市上海仓_正向全链路数据_curl.txt",
    "进口超市上海仓_货权转移采购单_curl.txt",
    "进口超市上海仓_货权转移采购单导出_curl.txt",
)

SALES_EXPORT_CURLS = {
    "销售单查询_curl.txt",
    "销售单明细账_curl.txt",
}

COOKIE_ONLY_CURLS = {
    "进口超市上海仓_正向全链路数据_curl.txt",
    "进口超市上海仓_货权转移采购单_curl.txt",
    "进口超市上海仓_货权转移采购单导出_curl.txt",
}


def normalized(text: str) -> str:
    return text.replace("^\r\n", "").replace("^\n", "").replace("^", "")


def load_out_of_scope(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    values = payload.get("out_of_scope", {})
    if not isinstance(values, dict):
        raise ValueError("capability manifest 的 out_of_scope 必须是对象")
    unknown = sorted(set(values) - set(REQUIRED_CURLS))
    if unknown:
        raise ValueError(f"capability manifest 含未知文件名: {', '.join(unknown)}")
    return {str(name): str(reason) for name, reason in values.items()}


def inspect_curl(path: Path) -> list[str]:
    problems: list[str] = []
    if not path.exists():
        return ["文件不存在"]
    text = normalized(path.read_text(encoding="utf-8", errors="ignore"))
    if len(text.strip()) < 100:
        problems.append("文件内容为空或过短")
    if path.name not in COOKIE_ONLY_CURLS and not re.search(
        r"authorization\s*:\s*Bearer\s+\S+|access_token=Bearer", text, re.I
    ):
        problems.append("缺少 authorization/access_token")
    if not re.search(r"(?:^|[;\s])token=|(?:^|[;\s])_ati=|\bati\s*:|(?:-b|--cookie)\s+", text, re.I):
        problems.append("缺少 cookie/ati 登录态")
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description="检查吉客云日常同步所需 cURL")
    parser.add_argument("--curl-dir", type=Path, default=CURL_DIR)
    parser.add_argument(
        "--capability-manifest",
        type=Path,
        help="账号权限边界 JSON；默认读取 <curl-dir>/capability_manifest.json",
    )
    parser.add_argument("--skip-live", action="store_true", help="仅排障时跳过渠道列表登录态实测")
    args = parser.parse_args()

    manifest_path = args.capability_manifest or args.curl_dir / "capability_manifest.json"
    try:
        out_of_scope = load_out_of_scope(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] capability manifest: {exc}", flush=True)
        raise SystemExit(2) from exc

    failed = False
    for name in REQUIRED_CURLS:
        if name in out_of_scope:
            print(f"[SKIP] {name}: {out_of_scope[name]}", flush=True)
            continue
        path = args.curl_dir / name
        problems = inspect_curl(path)
        if problems:
            failed = True
            print(f"[FAIL] {name}: {'；'.join(problems)}", flush=True)
        else:
            print(f"[OK] {name}", flush=True)
            if name in SALES_EXPORT_CURLS:
                text = normalized(path.read_text(encoding="utf-8", errors="ignore"))
                if "commonVerify=" not in text:
                    print(
                        f"[INFO] {name}: 无 commonVerify，将按非明文模式导出；"
                        "仅当吉客云实际返回 verifyType 时才需要手机验证",
                        flush=True,
                    )
    if failed:
        raise SystemExit(2)
    if not args.skip_live:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from 渠道列表_web import find_list_and_total, load_curl_info, request_json

        channel_curl = load_curl_info(str(args.curl_dir / "渠道列表_curl.txt"))
        params = dict(channel_curl["params"])
        params.update({"pageIndex": "0", "pageSize": "1"})
        try:
            with requests.Session() as session:
                rows, total = find_list_and_total(request_json(session, channel_curl, params))
            print(f"[OK] 吉客云实时登录态: 首页面={len(rows)}，总数={total}", flush=True)
        except Exception as exc:
            print(f"[FAIL] 吉客云实时登录态: {exc}", flush=True)
            raise SystemExit(3) from exc
    print("[DONE] 吉客云同步前置检查通过", flush=True)


if __name__ == "__main__":
    main()
