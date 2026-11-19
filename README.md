# N2N LAN Pro

> 专业版虚拟局域网客户端：在免费版「一个房间码就能异地组网」的基础上，补上**网络诊断、连接审计、房间库、高级参数**四块能力。
> 界面沿用免费版布局，独立安装包，**房间码与免费版完全互通**——两版可以互进对方的房间。

官网：<https://zgs7157.github.io/n2n-lan-pro/>
免费版（同一套房间码的轻量客户端）：<https://github.com/zgs7157/n2n-lan>

---

## 一、下载

| 方式 | 文件 | 说明 |
|---|---|---|
| 安装包（推荐） | `n2n-lan-pro-setup-1.0.1.exe` | 44 MB，独立 AppId，可与免费版并存，自带卸载程序与带图标的桌面快捷方式 |
| 绿色版 | `n2n-lan-pro.zip` | 43 MB，解压双击 `start_pro.bat` |
| 官网直下 | <https://zgs7157.github.io/n2n-lan-pro/#download> | 站内直下 + 直链 + aria2 命令 |

安装包 sha256：

```
fb866cdee54682d9380c8988b56e35792fbffaadfe06868524c9eeb8338b041a
```

---

## 二、四块专业能力

### 网络诊断面板

- 本机网络摘要：主机名、本机 IPv4/IPv6、公网 IPv4/IPv6、默认网关、DNS、虚拟网卡清单
- 整段子网存活扫描：并发 ping，存活主机列出 RTT 与 ARP 表里的 MAC
- 端口探测：`open` / `closed` / `filtered` 三态，支持 `22,80,8000-8100` 这种区间写法
- 延迟统计：丢包率、min / avg / max、抖动
- MTU 探测：`ping -f -l` 二分，输出最大不分片载荷与推算的链路 MTU
- 路由表、DNS 反查

### 连接审计

进房、退房、切网、失败原因自动写入 `logs_pro/audit.jsonl`；审计面板倒序展示，一键导出 Markdown 报告与 JSON 原始记录（`audit_reports/`）。

### 房间库

常去房间存成档案：名称、房间码、身份（房主 / 成员）、服务器、备注，一键进入或切换。

> Windows 只有一张 TAP 网卡（`TAP-Windows Adapter V9`），n2n 无法靠设备名区分多实例，所以**同一时刻只能一个房间在线**；「房间库」是档案 + 一键切换，切换约 2–5 秒重连。

### 高级参数

- 自定义 supernode 地址（多服务器候选）
- 强制 IPv6 / 同局域网本地转发
- 精细 MTU（默认 1290）
- 可选头部加密 `-H` 与加密算法 `-A`（**会破坏与免费版的互通**，默认关闭）
- 报文转发 `-r`、PMTU 发现 `-D`
- 无界面命令行模式

---

## 三、命令行模式（脚本 / 自动化）

```bash
python n2n_pro_manager.py --cli doctor
python n2n_pro_manager.py --cli scan 192.168.1.0/24
python n2n_pro_manager.py --cli ports 10.240.0.1 -p "22,80,7654,8000-8100"
python n2n_pro_manager.py --cli ping 10.240.0.2 -n 10
python n2n_pro_manager.py --cli mtu 192.168.1.1
python n2n_pro_manager.py --cli route
python n2n_pro_manager.py --cli dns 10.240.0.1
```

加 `--json` 输出结构化结果，方便 `jq` 或脚本消费。

Windows 打包版等价于：`n2n_pro_manager.exe --cli doctor`。

---

## 四、与免费版的关系

- **房间码同一套派生**：`J7N3-WD8Y` → community `room-j7n3-wd8y`、网段 `10.240.0`、密钥 `d3ee528c5ac6b776`，两版逐字一致，互相进得去
- **可并存安装**：Pro 用独立 AppId、独立目录（`Program Files\n2n-lan-pro`），卸载不影响免费版
- **配置分离**：Pro 写 `config_pro.json` / `logs_pro/`，不碰免费版的 `config.json` / `logs/`
- 免费版客户端：<https://github.com/zgs7157/n2n-lan>

---

## 五、本机实测（Windows 11）

- `doctor`：主机 HAAVK-SKYNET、本机 192.168.1.4、IPv6 `2409:8a48:9d0:ca00:9146:5dab:ab5:f870`、公网 IPv4 `39.162.81.255`、网关 192.168.1.1、DNS 192.168.1.1
- 端口：`127.0.0.1` 80 open 18–30 ms，其余 closed；`192.168.1.1`（路由器）80 open
- 子网扫描：`192.168.1.0/24` 254 个地址 → 存活 4 台，5 秒完成，MAC 由 ARP 表补全
- MTU：`192.168.1.1` → 最大不分片载荷 1472，链路 MTU 1500
- 无头 GUI：四面板均可打开，审计写入并导出 `n2n-pro-audit-*.md/.json`，房间库增删正常
- edge 参数：默认无 `-H`；`header_encrypt + chacha20` → `-H -A chacha20`；`packet_forward + pmtu_discovery` → `-r -D`

---

## 六、从源码构建

```powershell
# 依赖：Python 3.9+、PyInstaller、Inno Setup 6
pwsh -NoProfile -File tools\build_pro.ps1
```

产物：`build_tmp\dist_pro\n2n_pro_manager.exe`、`client_pro\`（绿色版目录）、`n2n-lan-pro.zip`、`dist_installer_pro\n2n-lan-pro-setup-1.0.1.exe`。

直接跑源码：

```bash
python client/n2n_pro_manager.py          # 图形界面
python client/n2n_pro_manager.py --cli doctor
```

---

## 七、许可与来源

- 客户端代码（`client/n2n_*.py`、本仓库脚本）：MIT
- n2n 引擎：GPLv3（预编译 Windows x64 版随包提供）
- OpenVPN TAP-Windows 驱动：GPLv2（官方签名组件）

本仓库是免费版 <https://github.com/zgs7157/n2n-lan> 的专业版分支，房间码派生与房间协议完全复用免费版，确保互通。
