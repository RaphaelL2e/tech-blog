#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


DEFAULT_WEALTH_OS_DIR = Path("/Users/liyafei/Documents/RaphaelWorkspace/04 - Codex项目/五年计划/wealth-os")
DEFAULT_OUTPUT = Path("static/wealth/wealth-data.enc.json")
AAD = b"raphael-tech-blog:wealth-os:v1"
ITERATIONS = 310_000


def b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def import_wealth_modules(wealth_os_dir: Path):
    dashboard_dir = wealth_os_dir / "dashboard"
    if not dashboard_dir.exists():
        raise FileNotFoundError(f"dashboard directory not found: {dashboard_dir}")
    sys.path.insert(0, str(dashboard_dir))
    from analytics import build_dashboard_summary  # type: ignore
    from app import build_weekly_operation_advice, load_dca_plan  # type: ignore

    return build_dashboard_summary, build_weekly_operation_advice, load_dca_plan


def money_rows(items: dict[str, float], financial_assets: float, total_assets: float) -> list[dict]:
    rows = []
    for name, amount in items.items():
        financial_ratio = amount / financial_assets if financial_assets else 0.0
        total_ratio = amount / total_assets if total_assets else 0.0
        rows.append(
            {
                "name": name,
                "amount": amount,
                "ratio": total_ratio if name == "公积金" else financial_ratio,
                "financialRatio": financial_ratio,
                "totalRatio": total_ratio,
            }
        )
    return rows


def build_plain_payload(wealth_os_dir: Path) -> dict:
    build_dashboard_summary, build_weekly_operation_advice, load_dca_plan = import_wealth_modules(wealth_os_dir)
    assets_path = wealth_os_dir / "data" / "assets.csv"
    dca_plan_path = wealth_os_dir / "data" / "dca_plan.csv"
    summary = build_dashboard_summary(assets_path)
    dca_rows = load_dca_plan(dca_plan_path)
    weekly_advice = build_weekly_operation_advice(summary, dca_rows)

    fund_names = {row["标的"] for row in dca_rows}
    dca_payload = {
        "fundCount": len(fund_names),
        "planCount": len(dca_rows),
        "activeCount": sum(1 for row in dca_rows if row["状态"] == "持续定投"),
        "pausedCount": sum(1 for row in dca_rows if row["状态"] == "暂停定投"),
        "weeklyAmount": sum(row["_weekly_amount"] for row in dca_rows),
        "monthlyAmount": sum(row["_monthly_amount"] for row in dca_rows),
        "rows": [
            {
                "snapshotDate": row["统计日期"],
                "assetName": row["标的"],
                "planName": row["计划"],
                "institution": row["机构"],
                "market": row["市场"],
                "direction": row["方向"],
                "assetType": row["资产类型"],
                "frequency": row["频率"],
                "singleAmount": row["_single_amount"],
                "weeklyAmount": row["_weekly_amount"],
                "monthlyAmount": row["_monthly_amount"],
                "accumulatedAmount": row["_accumulated_amount"],
                "currentValue": row["_current_value"],
                "returnRate": row["收益率"],
                "nextDebitDate": row["下次扣款"],
                "status": row["状态"],
                "reviewDate": row["复盘日期"],
                "note": row["备注"],
            }
            for row in dca_rows
        ],
    }

    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "snapshotDate": summary.snapshot_date,
            "totalAssets": summary.total_assets,
            "financialAssets": summary.financial_assets,
            "providentFund": summary.provident_fund,
            "cash": summary.cash,
            "investmentAssets": summary.investment_assets,
            "liabilities": summary.liabilities,
            "netAssets": summary.net_assets,
            "liquidityScore": summary.liquidity_score,
            "liquidityNote": summary.liquidity_note,
            "riskScore": summary.risk_score,
            "riskNote": summary.risk_note,
            "rebalancingSuggestions": summary.rebalancing_suggestions,
            "nextActions": summary.next_actions,
        },
        "categoryRows": money_rows(summary.by_category, summary.financial_assets, summary.total_assets),
        "assetRows": money_rows(summary.by_asset, summary.financial_assets, summary.total_assets),
        "allocationRows": [
            {"name": name, "ratio": ratio, "amount": ratio * summary.financial_assets}
            for name, ratio in summary.allocation.items()
        ],
        "weeklyAdvice": [
            {
                "priority": row["优先级"],
                "action": row["动作"],
                "recommendation": row["本周建议"],
                "reason": row["理由"],
            }
            for row in weekly_advice
        ],
        "dca": dca_payload,
    }


def read_password(args: argparse.Namespace) -> str:
    if args.password_stdin:
        password = sys.stdin.readline().rstrip("\n")
    else:
        password = os.environ.get("WEALTH_PASSWORD", "")
        if not password:
            password = getpass.getpass("Wealth payload password: ")
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                raise ValueError("passwords do not match")
    if len(password) < 12:
        raise ValueError("password must be at least 12 characters")
    return password


def encrypt_payload(payload: dict, password: str) -> dict:
    salt = os.urandom(16)
    iv = os.urandom(12)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=ITERATIONS,
    )
    key = kdf.derive(password.encode("utf-8"))
    plaintext = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ciphertext = AESGCM(key).encrypt(iv, plaintext, AAD)
    return {
        "schemaVersion": 1,
        "cipher": "AES-256-GCM",
        "kdf": {
            "name": "PBKDF2",
            "hash": "SHA-256",
            "iterations": ITERATIONS,
            "salt": b64(salt),
        },
        "iv": b64(iv),
        "aad": AAD.decode("ascii"),
        "ciphertext": b64(ciphertext),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export encrypted Wealth OS payload for the Hugo blog.")
    parser.add_argument("--wealth-os-dir", type=Path, default=Path(os.environ.get("WEALTH_OS_DIR", DEFAULT_WEALTH_OS_DIR)))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--password-stdin", action="store_true", help="Read the encryption password from stdin.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    wealth_os_dir = args.wealth_os_dir.expanduser().resolve()
    output = args.output.expanduser()
    password = read_password(args)
    payload = build_plain_payload(wealth_os_dir)
    encrypted = encrypt_payload(payload, password)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(encrypted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote encrypted wealth payload to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
