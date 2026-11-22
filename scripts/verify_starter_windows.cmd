@echo off
setlocal
python starter\generate_fixtures.py --seed 2026 || exit /b 1
python starter\verify_fixtures.py || exit /b 1
python -m unittest discover -s tests -p "test_*.py" -v || exit /b 1
echo Starter fixtures verified. Full app still must be built by Codex.
