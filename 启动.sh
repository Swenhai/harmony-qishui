#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo "========================================"
echo "  汽水音乐 纯血鸿蒙版 自动看广告攒会员"
echo "========================================"
echo

if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    echo "[错误] 未找到 Python 3.10+"
    exit 1
fi

if [ ! -x .venv/bin/python ]; then
    echo "[初始化] 创建虚拟环境..."
    "$PY" -m venv .venv
fi

if ! .venv/bin/python -c "import rapidocr_onnxruntime" >/dev/null 2>&1; then
    echo "[初始化] 安装依赖（首次运行）..."
    .venv/bin/python -m pip install -r requirements.txt
fi

echo "[提示] 自动发现 hdc 与设备；手机需开 USB 调试或无线调试并保持亮屏。"
echo "        停止：按 Ctrl + C"
echo "========================================"
echo

.venv/bin/python -u hm_free_vip.py "$@"
