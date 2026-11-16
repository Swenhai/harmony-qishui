#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
汽水音乐（HarmonyOS NEXT 纯血鸿蒙版）自动看广告攒免费听
==========================================================
纯 UI 自动化：用 hdc shell uitest 截图 / OCR 识别按钮 / 注入点击。
不修改 App、不伪造观看进度、不加速播放；广告该播多久就播多久，
脚本只在倒计时结束后替你点「领取成功」和「领取奖励」。

通用性设计（适配所有纯血鸿蒙机型）：
  - hdc 自动查找：命令行 > HDC 环境变量 > PATH > DevEco Studio 常见安装目录
  - 设备自动发现：hdc list targets 自动识别 USB / 无线设备；多设备可交互选择
  - 分辨率无关：所有点击坐标来自 OCR 识别出的文字中心，不写死任何屏幕尺寸
  - 包名自动探测：从已安装应用列表里找 com.luna.*.music，找不到才用默认值
  - 关键词 / 间隔 / 超时 / 轮数全部外置到 config.json 或命令行参数

依赖：Python 3.10+（推荐 3.12）、rapidocr-onnxruntime、numpy
      hdc（安装 DevEco Studio 后自带，或用独立 toolchains）

用法：python hm_free_vip.py --list-devices     # 只看设备
      python hm_free_vip.py                    # 自动发现并开始
      python hm_free_vip.py --connect 192.168.1.5:38805   # 指定无线设备
      python hm_free_vip.py --rounds 5         # 只领 5 条后停止
      Ctrl+C 停止（自动恢复音量）
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------- 默认配置（config.json 可覆盖） ----------------
DEFAULTS = {
    "hdc": "",                       # hdc 可执行文件路径；留空自动查找
    "device": "",                    # 设备标识（IP:PORT 或 USB 序列号）；留空自动选择
    "bundle": "",                    # 汽水音乐包名；留空自动探测
    "ability": "MainAbility",        # 入口 Ability
    "rounds": 0,                     # 领取条数；0 = 无限循环
    "interval": 1.5,                 # 截图识别间隔（秒）
    "timeout": 180,                  # 单条广告最长等待（秒）
    "mute": True,                    # 开始静音、退出恢复
    "mute_keycode": "164",           # 鸿蒙媒体静音键，多数机型通用
    "debug": False,                  # 每 20 张截图存一份到 hm_debug/
}

# OCR 关键词。汽水音乐版本差异导致文案微调时，改 config.json 的 keywords 即可。
KEYWORDS = {
    "free_listen": ["免费听"],                       # 播放页「免费听1天」
    "claim_done": ["领取成功"],                       # 广告播完右上角「领取成功×」
    "countdown": ["可领取奖励", "秒后"],             # 广告播放中倒计时
    "reward_btn": ["领取奖励", "继续观看"],          # 奖励弹窗绿色按钮
    "cancel_live": ["取消"],                         # 直播间拦截
    "exit_live": ["退出不看了"],                     # 误入直播间后退出
    "feedback": ["反馈"],                            # 广告页右上角，确认在广告页
    "dialog_mark": ["再看", "提前得", "坚持退出"],   # 奖励弹窗特征
}

# 这些文字出现在按钮上时不点（广告诱导下载 / 进直播间）
DANGER_WORDS = ["立即下载", "下载", "进入直播间", "打开", "安装"]

TMP_REMOTE = "/data/local/tmp/_hm_cap.png"
# hdc file recv 在 Windows 上会把带盘符的路径误当相对路径拼接
# （实测报 path:D:\xxx\D:/xxx/file.png），用相对文件名最稳。
# main() 开头会 chdir 到脚本目录，保证落点正确。
TMP_LOCAL = "_hm_cap.png"
DEBUG_DIR = os.path.join(SCRIPT_DIR, "hm_debug")
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
PNG_END = b"IEND\xaeB`\x82"


# ---------------- hdc 查找与命令封装 ----------------
def find_hdc(explicit=None):
    """按优先级找 hdc：显式参数 > 环境变量 > PATH > DevEco 常见目录。"""
    candidates = []

    def add(p):
        if p and p not in candidates:
            candidates.append(p)

    add(explicit)
    add(os.environ.get("HDC"))
    add(shutil.which("hdc"))
    add(shutil.which("hdc.exe"))

    roots = []
    for key in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "USERPROFILE"):
        val = os.environ.get(key)
        if val:
            roots.append(val)
    roots += [os.path.expanduser("~"), "C:\\", "D:\\"]

    for root in roots:
        for sub in ("Huawei", "DevEco Studio", "hdc", "toolchains", "DevEcoStudio"):
            add(os.path.join(root, sub, "toolchains", "toolchains", "hdc.exe"))
            add(os.path.join(root, sub, "toolchains", "hdc.exe"))
            add(os.path.join(root, sub, "hdc.exe"))
            add(os.path.join(root, sub, "toolchains", "toolchains", "hdc"))
            add(os.path.join(root, sub, "toolchains", "hdc"))
        # 递归找两层，覆盖不同 DevEco 版本目录结构
        for pat in ("Huawei/**/hdc.exe", "DevEco Studio/**/hdc.exe",
                    "DevEcoStudio/**/hdc", "Huawei/**/hdc"):
            for p in glob.glob(os.path.join(root, pat), recursive=True)[:20]:
                add(p)
    add("/usr/local/bin/hdc")
    add("/opt/huawei/DevEcoStudio/toolchains/hdc")

    for p in candidates:
        if os.path.isfile(p):
            return os.path.abspath(p)
    return None


def run_hdc(hdc_bin, args, device=None, timeout=30):
    """执行 hdc。device=None 时不加 -t（list targets/connect 不能带 -t）。"""
    cmd = [hdc_bin]
    if device:
        cmd += ["-t", device]
    cmd += args
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return r.stdout.decode("utf-8", "ignore").strip(), r.returncode
    except Exception:
        return "", -1


def parse_devices(output):
    """从 hdc list targets 输出里挑出可用设备标识。"""
    devices = []
    for line in (output or "").splitlines():
        s = line.strip()
        if not s or s.startswith("[") or s.startswith("<"):
            continue
        if re.fullmatch(r"[\w.\-]+:\d+", s) or re.fullmatch(r"[A-Za-z0-9_\-]{8,}", s):
            devices.append(s)
    return devices


def pick_device(hdc_bin, args):
    """按 --connect / --device / 配置 / 自动发现的优先级确定设备。"""
    connect = getattr(args, "connect", None)
    if connect:
        print(f"[连接] hdc connect {connect}")
        run_hdc(hdc_bin, ["connect", connect])
        time.sleep(2)

    devices = parse_devices(run_hdc(hdc_bin, ["list", "targets"])[0])
    if getattr(args, "list_devices", False):
        print("已发现设备：" if devices else "未发现设备")
        for d in devices:
            print("  " + d)
        return None

    wanted = getattr(args, "device", None)
    if wanted:
        if wanted in devices:
            return wanted
        print(f"[提示] 设备 {wanted} 不在列表中，尝试连接")
        run_hdc(hdc_bin, ["connect", wanted])
        time.sleep(2)
        devices = parse_devices(run_hdc(hdc_bin, ["list", "targets"])[0])
        return wanted if wanted in devices else None

    if len(devices) == 1:
        return devices[0]
    if len(devices) > 1:
        print("发现多个设备：")
        for i, d in enumerate(devices):
            print(f"  [{i}] {d}")
        try:
            idx = int(input("输入序号选择（直接回车选第一个）: ").strip() or "0")
            return devices[idx]
        except Exception:
            return devices[0]

    print("[错误] 未发现鸿蒙设备。请开启开发者选项 → USB 调试（或无线调试），")
    print("       或先执行 hdc connect <IP:PORT>；也可在脚本参数里传 --connect。")
    return None


def detect_bundle(hdc_bin, device, configured):
    """自动探测汽水音乐鸿蒙版包名，找不到才回退默认值。"""
    if configured:
        return configured
    out, _ = run_hdc(hdc_bin, ["shell", "bm", "dump", "-a"], device)
    ids = re.findall(r'"([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+)"', out)
    for pkg in ids:
        if "luna" in pkg.lower() and "music" in pkg.lower():
            return pkg
    for pkg in ids:
        if any(k in pkg.lower() for k in ("qishui", "soda")):
            return pkg
    return "com.luna.hm.music"


def screenshot(hdc_bin, device):
    """截图并拉到本地，返回本地路径；失败返回 None。

    注意：hdc file recv 在 Windows 上不支持带盘符的绝对路径，
    也不支持正斜杠（会把 cwd 拼进去），必须用相对文件名。
    另外它即使传输失败也常返回 rc=0，所以要校验 PNG 文件头尾。
    """
    run_hdc(hdc_bin, ["shell", "uitest", "screenCap", "-p", TMP_REMOTE], device)
    for attempt in range(2):
        try:
            r = subprocess.run([hdc_bin, "-t", device, "file", "recv",
                                TMP_REMOTE, TMP_LOCAL],
                               capture_output=True, timeout=90)
            if os.path.isfile(TMP_LOCAL):
                with open(TMP_LOCAL, "rb") as f:
                    data = f.read()
                if (len(data) > 1000 and data[:8] == PNG_MAGIC
                        and PNG_END in data[-32:]):
                    return TMP_LOCAL
            out = r.stdout.decode("utf-8", "ignore").strip()
            print(f"   [截图重试 {attempt + 1}] {out[:100]}")
        except Exception as e:
            print(f"   [截图异常] {e}")
        time.sleep(1)
    return None


def tap(hdc_bin, device, x, y):
    run_hdc(hdc_bin, ["shell", "uitest", "uiInput", "click", str(int(x)), str(int(y))], device)


def key_back(hdc_bin, device):
    run_hdc(hdc_bin, ["shell", "uitest", "uiInput", "keyEvent", "Back"], device)


def mute_toggle(hdc_bin, device, keycode):
    run_hdc(hdc_bin, ["shell", "uitest", "uiInput", "keyEvent", keycode], device)


# ---------------- OCR 与状态判断 ----------------
_engine = None


def ocr(path):
    """返回 [(text, cx, cy, score), ...]；坐标来自识别框中心，天然分辨率无关。"""
    global _engine
    try:
        if _engine is None:
            from rapidocr_onnxruntime import RapidOCR
            _engine = RapidOCR()
        result, _ = _engine(path)
    except Exception as e:
        print(f"[OCR 错误] {e}")
        return []
    out = []
    for box, text, score in (result or []):
        cx = sum(p[0] for p in box) / 4
        cy = sum(p[1] for p in box) / 4
        out.append((text, cx, cy, score))
    return out


def find(items, keywords, min_score=0.6, exclude=None):
    exclude = exclude or []
    for text, cx, cy, score in items:
        if score < min_score or any(e in text for e in exclude):
            continue
        if any(k in text for k in keywords):
            return (cx, cy, text)
    return None


def has_any(items, keywords, min_score=0.6):
    return any(score >= min_score and any(k in text for k in keywords)
               for text, _, _, score in items)


def is_reward_dialog(items, kw):
    """奖励弹窗会盖在广告页上，背景「领取成功×」会造成干扰，必须优先识别。"""
    return has_any(items, kw["dialog_mark"]) and (
        has_any(items, kw["reward_btn"]) or has_any(items, ["坚持退出"])
    )


def click_cancel_live(hdc_bin, device, items, kw):
    """直播广告拦截：只在高置信度且确认是直播语境时点取消，避免误点。"""
    hit = find(items, kw["exit_live"], min_score=0.6)
    if hit:
        tap(hdc_bin, device, hit[0], hit[1])
        return hit[2]
    all_text = " ".join(t for t, _, _, s in items if s > 0.6)
    if "直播间" in all_text or "后进入" in all_text:
        hit = find(items, kw["cancel_live"], min_score=0.75)
        if hit:
            tap(hdc_bin, device, hit[0], hit[1])
            return hit[2]
    return None


# ---------------- 主循环 ----------------
def main():
    os.chdir(SCRIPT_DIR)  # hdc file recv 用相对路径，先确保落点正确
    ap = argparse.ArgumentParser(description="汽水音乐鸿蒙版自动看广告攒免费听")
    ap.add_argument("--hdc", default=None, help="hdc 路径（默认自动查找）")
    ap.add_argument("--device", default=None, help="设备标识 IP:PORT 或 USB 序列号")
    ap.add_argument("--connect", default=None, help="先连接无线设备，如 192.168.1.5:38805")
    ap.add_argument("--list-devices", action="store_true", help="只列出设备后退出")
    ap.add_argument("--bundle", default=None, help="汽水音乐包名（默认自动探测）")
    ap.add_argument("--ability", default=None, help="入口 Ability（默认 MainAbility）")
    ap.add_argument("--rounds", type=int, default=None, help="领取条数，0=无限（默认 0）")
    ap.add_argument("--interval", type=float, default=None, help="识别间隔秒（默认 1.5）")
    ap.add_argument("--timeout", type=int, default=None, help="单条广告超时秒（默认 180）")
    ap.add_argument("--no-mute", action="store_true", help="不静音")
    ap.add_argument("--debug", action="store_true", help="保存调试截图")
    ap.add_argument("--config", default=os.path.join(SCRIPT_DIR, "config.json"),
                    help="配置文件路径（默认脚本同目录 config.json）")
    args = ap.parse_args()

    cfg = {}
    if os.path.isfile(args.config):
        try:
            with open(args.config, encoding="utf-8") as f:
                cfg = json.load(f) or {}
        except Exception as e:
            print(f"[警告] 配置文件读取失败: {e}")

    def val(name):
        cli = getattr(args, name, None)
        if cli is not None:
            return cli
        if name in cfg:
            return cfg[name]
        return DEFAULTS[name]

    hdc_bin = find_hdc(val("hdc"))
    if not hdc_bin:
        print("[错误] 找不到 hdc。请安装 DevEco Studio，或用 --hdc 指定 hdc.exe 路径。")
        return 1

    print("=" * 54)
    print("  汽水音乐 · 纯血鸿蒙版 自动看广告攒免费听")
    print("=" * 54)
    print(f"hdc : {hdc_bin}")

    device = pick_device(hdc_bin, args)
    if not device:
        return 1
    print(f"设备: {device}")

    bundle = detect_bundle(hdc_bin, device, val("bundle"))
    ability = val("ability")
    rounds_limit = int(val("rounds"))
    interval = float(val("interval"))
    ad_timeout = int(val("timeout"))
    mute = bool(val("mute")) and not args.no_mute
    mute_keycode = str(val("mute_keycode"))
    debug = bool(val("debug")) or args.debug

    kw = dict(KEYWORDS)
    if isinstance(cfg.get("keywords"), dict):
        for k, v in cfg["keywords"].items():
            if k in kw and isinstance(v, list):
                kw[k] = v

    print(f"应用: {bundle}/{ability}")
    print(f"设置: 目标 {rounds_limit or '无限'} 条 / 间隔 {interval}s / 超时 {ad_timeout}s / "
          f"静音 {'开' if mute else '关'}")
    print("\n[启动] 打开汽水音乐")
    run_hdc(hdc_bin, ["shell", "aa", "start", "-a", ability, "-b", bundle], device)
    time.sleep(4)

    if mute:
        mute_toggle(hdc_bin, device, mute_keycode)
        print("[静音] 已开启（退出时自动恢复）")
    if debug:
        os.makedirs(DEBUG_DIR, exist_ok=True)

    rounds = 0
    ad_start = None
    last_state = ""
    shot_no = 0
    unknown_streak = 0
    print("\n[开始] 循环运行中，Ctrl+C 停止…\n")

    try:
        while True:
            if rounds_limit and rounds >= rounds_limit:
                print(f"[完成] 已领取 {rounds_limit} 条，达到设定目标。")
                break

            path = screenshot(hdc_bin, device)
            shot_no += 1
            if not path:
                print(f"[{datetime.now():%H:%M:%S}] 截图失败，重试")
                time.sleep(2)
                continue

            if debug and shot_no % 20 == 0:
                shutil.copy(path, os.path.join(DEBUG_DIR, f"s_{shot_no:04d}.png"))

            items = ocr(path)
            all_text = " ".join(t for t, _, _, s in items if s > 0.6)

            # 优先级 1：奖励弹窗（弹窗盖在广告页上，背景的「领取成功×」会干扰）
            if is_reward_dialog(items, kw):
                hit = find(items, kw["reward_btn"], min_score=0.6, exclude=DANGER_WORDS)
                if hit:
                    tap(hdc_bin, device, hit[0], hit[1])
                    rounds += 1
                    ad_start = time.time()
                    print(f"[{datetime.now():%H:%M:%S}] ✅ 已领取第 {rounds} 条 → 进入下一条")
                    state = "领取奖励"
                else:
                    state = "弹窗识别中"

            # 优先级 2：广告倒计时中，等待
            elif has_any(items, kw["countdown"], min_score=0.5):
                if ad_start is None:
                    ad_start = time.time()
                if time.time() - ad_start > ad_timeout:
                    print(f"[{datetime.now():%H:%M:%S}] 广告超时 {ad_timeout}s，返回重试")
                    key_back(hdc_bin, device)
                    ad_start = None
                state = "广告倒计时"

            # 优先级 3：广告播完，点右上角「领取成功×」
            elif find(items, kw["claim_done"], min_score=0.6) and (
                    has_any(items, kw["feedback"]) or has_any(items, kw["countdown"], min_score=0.5)):
                hit = find(items, kw["claim_done"], min_score=0.6)
                tap(hdc_bin, device, hit[0], hit[1])
                print(f"[{datetime.now():%H:%M:%S}] 广告#{rounds + 1} 播完 → 点领取成功")
                state = "点领取成功"
                time.sleep(1)

            # 优先级 4：播放页「免费听1天」
            elif find(items, kw["free_listen"], min_score=0.6):
                hit = find(items, kw["free_listen"], min_score=0.6)
                tap(hdc_bin, device, hit[0], hit[1])
                ad_start = time.time()
                print(f"[{datetime.now():%H:%M:%S}] 播放页 → 点免费听，开始广告")
                state = "点免费听"

            # 优先级 5：直播广告拦截
            elif click_cancel_live(hdc_bin, device, items, kw):
                state = "拦截直播广告"

            else:
                state = "未知页/等待"
                unknown_streak += 1
                # 长时间什么都不认识：多半是锁屏、后台或 App 掉前台
                if unknown_streak == 12:
                    print("   [提示] 连续多轮识别不到界面，请确认手机已解锁、汽水音乐在前台、屏幕常亮。")
                if ad_start and time.time() - ad_start > ad_timeout:
                    key_back(hdc_bin, device)
                    ad_start = None

            if state != "未知页/等待":
                unknown_streak = 0
            if state != last_state:
                print(f"   状态: {state}")
                last_state = state
            time.sleep(interval)

    except KeyboardInterrupt:
        print(f"\n[停止] 用户中断。")
    finally:
        if mute:
            mute_toggle(hdc_bin, device, mute_keycode)
            print("[恢复] 音量已恢复")
        try:
            if os.path.exists(TMP_LOCAL):
                os.remove(TMP_LOCAL)
        except Exception:
            pass
        run_hdc(hdc_bin, ["shell", "rm", "-f", TMP_REMOTE], device)
        print(f"[统计] 本次共领取 {rounds} 条广告（约 {rounds} 天免费听，实际以 App 显示为准）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
