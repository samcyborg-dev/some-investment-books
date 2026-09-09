#!/usr/bin/env bash
# Safe to rerun after a workspace restart. Run on the session's existing branch.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pip install --user --break-system-packages -r web_app/requirements.txt
# The source manuscript is authoritative. Repair a damaged PDF only when necessary.
if ! python3 - <<'PY'
import hashlib,json
from pathlib import Path
p=Path('STRATEGY_1_ORB_FORENSIC_RESEARCH.pdf')
m=json.loads(Path('research/strategy_1/build_metadata.json').read_text())
raise SystemExit(0 if p.exists() and hashlib.sha256(p.read_bytes()).hexdigest()==m['sha256'][p.name] else 1)
PY
then
  python3 -m pip install --user --break-system-packages -r research/strategy_1/requirements.txt
  python3 research/strategy_1/build_pdf.py
fi
exec python3 -m uvicorn web_app.app:app --host 0.0.0.0 --port "${PORT:-8000}" --no-access-log
