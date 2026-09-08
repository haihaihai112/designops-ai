#!/usr/bin/env bash
set -euo pipefail

if [ ! -x ".venv/bin/python" ]; then
  echo "尚未安装依赖，请先运行 ./install.sh。" >&2
  exit 1
fi

.venv/bin/python -m module4_demo.app
