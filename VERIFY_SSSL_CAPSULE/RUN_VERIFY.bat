@echo off
setlocal

cd /d %~dp0

python sssl_capsule_verify.py --repo_root ..

if errorlevel 1 (
  echo CAPSULE_RESULT: FAIL
  exit /b 1
)

echo CAPSULE_RESULT: PASS
exit /b 0
