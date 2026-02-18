#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")"

python3 sssl_capsule_verify.py --repo_root ..

echo "CAPSULE_RESULT: PASS"
