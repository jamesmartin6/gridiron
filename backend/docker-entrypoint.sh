#!/bin/sh
set -e

python -m ml.bootstrap

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
