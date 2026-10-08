#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
from pathlib import Path
import re
root=Path('.')
blocked_suffix={'.jks','.keystore','.pem'}
for p in root.rglob('*'):
    if not p.is_file(): continue
    if '.git' in p.parts or p.name in {'.env.example','verify-no-secrets.sh'}: continue
    if p.suffix in blocked_suffix or p.name in {'.env','google-services.json'}:
        raise SystemExit(f'Forbidden secret/config artifact: {p}')
    try: text=p.read_text(errors='ignore')
    except Exception: continue
    patterns=[r'sk-[A-Za-z0-9]{20,}',r'AIza[0-9A-Za-z_-]{20,}',r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----',r'(?i)JWT_SECRET\s*=\s*(?!generate-a-long-random-secret|integration-secret-integration-secret-123456789|test-secret-test-secret-test-secret-123456)[^\s]+',r'(?i)AI_API_KEY\s*=\s*(?!server-only-secret|integration-key|test-key)[^\s]+']
    for pat in patterns:
        if re.search(pat,text): raise SystemExit(f'Potential hard-coded secret in {p}')
print('No forbidden secret artifacts or obvious hard-coded secrets detected.')
PY
