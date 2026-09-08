$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "尚未安装依赖，请先运行 .\install.ps1。"
}

& ".venv\Scripts\python.exe" -m module4_demo.app
