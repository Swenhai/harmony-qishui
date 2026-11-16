# 汽水音乐 · 纯血鸿蒙自动看广告攒免费听

适用于 **HarmonyOS NEXT（纯血鸿蒙）** 全机型的 UI 自动化脚本。通过系统自带的 `hdc shell uitest` 截图、识别按钮、模拟点击，自动完成「点免费听 → 等广告播完 → 点领取成功 → 点领取奖励 → 下一条」的循环，把看广告换来的免费听会员尽量攒多。

**纯 UI 操作**：不修改 App、不注入进程、不伪造观看进度、不加速播放。广告该播多久就播多久，脚本只在你不在手机旁边时替你点按钮。

---

## 支持的设备

- 系统：HarmonyOS NEXT（HongMeng Kernel），API 12 及以上
- 机型：不限。所有点击坐标都从 OCR 识别出的文字中心计算，**不依赖特定分辨率**
- 屏幕：1260×2720、1280×2776、1312×2848 等均已适配
- 应用：汽水音乐鸿蒙版（包名自动探测，默认 `com.luna.hm.music`）

> 安卓手机不适用（请用 adb 版脚本）。本仓库只针对纯血鸿蒙。

---

## 前置条件

1. **装了 hdc**
   安装 [DevEco Studio](https://developer.huawei.com/consumer/cn/deveco-studio/) 后会自带 `hdc.exe`，也可以用独立的 OpenHarmony toolchains。脚本会自动搜索常见安装目录。
2. **手机开了开发者调试**
   设置 → 关于本机 → 连点版本号开启开发者选项 → 打开「USB 调试」或「无线调试」。
   - 无线调试：记下「IP 地址和端口」，如 `192.168.1.5:38805`，电脑和手机须在同一 WiFi。
   - USB：直接用数据线连上，`hdc list targets` 能看到序列号即可。
3. **手机装了汽水音乐鸿蒙版**，并登录。
4. **Python 3.10+**（推荐 3.12）

---

## 安装

Windows（双击 `启动.bat` 会自动完成第 2、3 步）：

```bat
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

macOS / Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 使用

**最简单**：双击 `启动.bat`（Windows）或运行 `./启动.sh`（macOS/Linux），脚本会自动找 hdc、发现设备、探测包名并开始循环。

命令行方式：

```bash
# 先看看发现了哪些设备
python hm_free_vip.py --list-devices

# 自动发现唯一设备并开始
python hm_free_vip.py

# 指定无线设备
python hm_free_vip.py --connect 192.168.1.5:38805

# 只领 5 条后自动停
python hm_free_vip.py --rounds 5

# 指定 hdc 路径（自动找不到时）
python hm_free_vip.py --hdc "D:\hdc\toolchains\toolchains\hdc.exe"
```

停止：在窗口按 `Ctrl+C`，脚本会自动恢复音量并打印本次领取条数。

---

## 配置

复制 `config.example.json` 为 `config.json`，按需修改。命令行参数优先级高于配置文件。

| 配置项 | 默认 | 说明 |
|---|---|---|
| `hdc` | 自动查找 | hdc 路径，留空自动搜索 PATH 和 DevEco 安装目录 |
| `device` | 自动发现 | 设备标识 `IP:PORT` 或 USB 序列号 |
| `bundle` | 自动探测 | 汽水音乐包名 |
| `ability` | `MainAbility` | 入口 Ability |
| `rounds` | `0` | 领取条数，`0` = 无限循环 |
| `interval` | `1.5` | 识别间隔（秒） |
| `timeout` | `180` | 单条广告最长等待（秒） |
| `mute` | `true` | 开始时静音、退出恢复 |
| `mute_keycode` | `164` | 媒体静音键，多数鸿蒙机型通用；个别机型无效可设 `false` 关闭静音 |
| `debug` | `false` | 每 20 张截图存到 `hm_debug/` 便于排查 |
| `keywords` | 见文件 | OCR 关键词，汽水音乐改版导致识别不到时在这里调整 |

---

## 工作原理

```
播放页「免费听1天」
      ↓ 点
广告播放中（右上角「XX秒后可领取奖励」倒计时）  ← 此阶段只等待，不点任何东西
      ↓ 倒计时结束
右上角「领取成功×」  → 点掉
      ↓
奖励弹窗「再看N个视频提前得 第N日免费听」+「领取奖励」  → 点领取奖励
      ↓
下一条广告，循环
```

状态判断用 OCR 识别屏幕文字，并做了三处防误操作：

1. 奖励弹窗优先级最高——弹窗盖住广告页时，背景的「领取成功×」不会造成死循环
2. 含「立即下载 / 进入直播间 / 安装」等诱导文字的按钮一律不点
3. 误入直播间时点「取消 / 退出不看了」；跳到应用商店等未知页超时自动返回

---

## 常见问题

**找不到 hdc**
用 `python hm_free_vip.py --hdc "完整路径\hdc.exe"` 指定，或把 hdc 目录加进 PATH，也可设环境变量 `HDC`。

**`hdc list targets` 没有设备**
确认开发者选项里的 USB 调试 / 无线调试已开；无线调试要电脑和手机在同一 WiFi；无线调试的「配对端口」和「连接端口」是两个不同的端口，`--connect` 要用页面顶部显示的**连接端口**。

**识别不到按钮 / 一直在「未知页/等待」**
汽水音乐改版后文案变了。打开 `--debug` 看 `hm_debug/` 里的截图，把实际文字加进 `config.json` 的 `keywords`。

**静音没生效**
个别机型 `164` 键无效，把 `mute` 设成 `false`。

**广告播完但会员天数没涨**
脚本只负责点按钮，领取是否成功由 App 决定。若 App 当天已达领取上限，界面会出现不同的提示文案，此时把 `--rounds` 调小或改关键词。

---

## 许可

MIT
