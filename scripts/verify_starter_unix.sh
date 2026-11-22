#!/usr/bin/env sh
set -eu
python3 starter/generate_fixtures.py --seed 2026
python3 starter/verify_fixtures.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
printf '%s\n' 'Starter fixtures verified. Full app still must be built by Codex.'
