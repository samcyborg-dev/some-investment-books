"""CLI smoke tests; input bars are synthetic and not evidence."""
from datetime import date, datetime, time, timedelta
import json
from pathlib import Path
import subprocess
import sys

from research.strategy_2.strategy2_engine import NY


def write_csv(path: Path) -> None:
    start = datetime.combine(date(2026, 1, 5), time(9, 30), NY)
    lines = ["timestamp,open,high,low,close,volume"]
    for index in range(78):
        timestamp = start + timedelta(minutes=5 * index)
        lines.append(f"{timestamp.isoformat()},100,100.25,99.75,100,1")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def invoke(*args):
    root = Path(__file__).resolve().parents[2]
    return subprocess.run(
        [sys.executable, str(root / "research/strategy_2/run_strategy2.py"), *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )


def test_cli_emits_receipt_without_raw_bars_and_requires_research_ack(tmp_path):
    source = tmp_path / "mes.csv"
    output = tmp_path / "receipt.json"
    write_csv(source)
    receipt = invoke("receipt", "--asset", "MES", "--input", str(source), "--output", str(output))
    assert receipt.returncode == 0, receipt.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["receipt"]["asset"] == "MES"
    assert payload["dataset"]["bar_count"] == 78
    assert "bars" not in payload["dataset"]

    refused = invoke("backtest", "--asset", "MES", "--input", str(source))
    assert refused.returncode == 2
    assert "--research-only" in refused.stderr

    result = invoke("backtest", "--research-only", "--asset", "MES", "--input", str(source))
    assert result.returncode == 0, result.stderr
    result_payload = json.loads(result.stdout)
    assert result_payload["result"]["metrics"]["trade_count"] == 0
    assert result_payload["evidence"].endswith("NOT PROJECT-OWNED")
