# N2N LAN Pro 打包脚本（Windows）
# 用法：pwsh -NoProfile -File tools\build_pro.ps1
# 产物：client_pro（绿色版目录）、n2n-lan-pro.zip、dist_installer_pro\n2n-lan-pro-setup-1.0.0.exe

$ErrorActionPreference = "Stop"
$root = "D:\N2N\n2n-lan-pro"
$py = "C:\Python314\python.exe"
$iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
$proName = "n2n-lan-pro-setup-1.0.0.exe"
Set-Location $root

$tmp = Join-Path $root "build_tmp\pro"
$dist = Join-Path $root "build_tmp\dist_pro"
$clientPro = Join-Path $root "client_pro"

Write-Host "== 0/6 环境检查 =="
Get-Process n2n_pro_manager -ErrorAction SilentlyContinue | Stop-Process -Force
if (Test-Path (Join-Path $root "client\n2n_pro_manager.py")) { "  源码就位" } else { throw "缺少 client\n2n_pro_manager.py" }
if (Test-Path $iscc) { "  ISCC 就位" } else { throw "找不到 Inno Setup: $iscc" }
$pyOk = & $py -c "import PyInstaller, sys; print(PyInstaller.__version__)"
Write-Host "  PyInstaller $pyOk"

Write-Host "== 1/6 编译 Pro 主程序 =="
New-Item -ItemType Directory -Force -Path $tmp, $dist | Out-Null
& $py -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name n2n_pro_manager `
    --icon (Join-Path $root "client\n2n-lan.ico") `
    --version-file (Join-Path $root "tools\version_info_pro.txt") `
    --distpath $dist --workpath $tmp --specpath $tmp `
    --paths client `
    (Join-Path $root "client\n2n_pro_manager.py") 2>&1 | Select-Object -Last 6
$newExe = Join-Path $dist "n2n_pro_manager.exe"
if (-not (Test-Path $newExe)) { throw "打包失败：找不到 $newExe" }
Write-Host ("  exe ok: {0} bytes" -f (Get-Item $newExe).Length)

Write-Host "== 2/6 组装绿色版目录 client_pro =="
if (Test-Path $clientPro) { Remove-Item -LiteralPath $clientPro -Recurse -Force }
New-Item -ItemType Directory -Force -Path $clientPro | Out-Null
$rc = robocopy "client" "client_pro" /E /NFL /NDL /NJH /NJS `
    /XD "logs" "logs_pro" "__pycache__" ".pytest_cache" "audit_reports" `
    /XF "n2n_room_manager.exe" "config.json" "config_pro.json" "*.pyc" "*.bak" "edge_lucktu_nov6.bak.exe" "n2n_room_manager_old_noipv6.exe" "start.bat" "WinIPBroadcast.exe" "README_EN.txt" 2>&1
if ($LASTEXITCODE -ge 8) { throw "robocopy 失败，退出码 $LASTEXITCODE" }
Copy-Item -LiteralPath $newExe -Destination (Join-Path $clientPro "n2n_pro_manager.exe") -Force
Write-Host "  已复制 " + ((Get-ChildItem $clientPro -Recurse -File | Measure-Object).Count) + " 个文件"

Write-Host "== 3/6 写启动脚本 =="
$bat = @'
@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist n2n_pro_manager.exe (
  start "" n2n_pro_manager.exe
) else (
  pythonw n2n_pro_manager.py
)
'@
Set-Content -LiteralPath (Join-Path $clientPro "start_pro.bat") -Value $bat -Encoding utf8
Write-Host "  start_pro.bat ok"

$readme = @'
N2N LAN Pro 1.0.0（专业版）使用说明
========================================

启动：双击 n2n_pro_manager.exe（或 start_pro.bat）

房间码与免费版完全互通：同一串 8 位码在两版里算出同一个房间、同网段、同密钥。
主界面工具条上有四个专业面板：
  · 网络诊断 —— 本机网络摘要、Ping 统计、端口探测、MTU 探测、子网扫描、路由表、DNS 解析
  · 连接审计 —— 进房/退房/切网/失败自动留痕，可导出 Markdown 报告与 JSON
  · 房间库   —— 常去房间存成档案，一键进入或切换
  · 高级参数 —— 自定义 supernode、强制 IPv6/本地转发、精细 MTU、头部加密、报文转发与 PMTU

无界面命令行（脚本 / 自动化）：
  python n2n_pro_manager.py --cli doctor
  python n2n_pro_manager.py --cli scan 192.168.1.0/24
  python n2n_pro_manager.py --cli ports 10.240.0.1 -p "22,80,7654,8000-8100"
  python n2n_pro_manager.py --cli ping 10.240.0.2 -n 10
  python n2n_pro_manager.py --cli mtu 192.168.1.1
  python n2n_pro_manager.py --cli route
  python n2n_pro_manager.py --cli dns 10.240.0.1
加 --json 输出结构化结果。

文件位置：
  配置  config_pro.json
  日志  logs_pro\
  审计  logs_pro\audit.jsonl，导出在 audit_reports\

首次使用如需安装虚拟网卡驱动或放行防火墙，按提示点「是」（UAC），之后不再打扰。

已知限制：Windows 只有一张 TAP 网卡，同一时刻只能一个房间在线；「房间库」是档案 + 一键切换，
切换约 2-5 秒重连。开启头部加密（-H/-A）会破坏与免费版的互通，默认关闭。
'@
Set-Content -LiteralPath (Join-Path $clientPro "使用说明.txt") -Value $readme -Encoding utf8
Write-Host "  使用说明.txt ok"

Write-Host "== 4/6 绿色版 zip =="
$zip = Join-Path $root "n2n-lan-pro.zip"
if (Test-Path $zip) { Remove-Item -LiteralPath $zip -Force }
Compress-Archive -Path (Join-Path $clientPro "*") -DestinationPath $zip -CompressionLevel Optimal
$zipSize = (Get-Item $zip).Length
Write-Host ("  zip ok: {0} bytes" -f $zipSize)

Write-Host "== 5/6 编译安装包 =="
& $iscc "setup_pro.iss" 2>&1 | Select-Object -Last 4
$setup = Join-Path $root "dist_installer_pro\$proName"
if (-not (Test-Path $setup)) { throw "安装包未生成：$setup" }

Write-Host "== 6/6 结果 =="
$setupSize = (Get-Item $setup).Length
$setupHash = (Get-FileHash -LiteralPath $setup -Algorithm SHA256).Hash.ToLower()
$exeSize = (Get-Item (Join-Path $clientPro "n2n_pro_manager.exe")).Length
Write-Host ("setup  : {0} bytes  sha256={1}" -f $setupSize, $setupHash)
Write-Host ("zip    : {0} bytes" -f $zipSize)
Write-Host ("exe    : {0} bytes" -f $exeSize)
Write-Host ("版本   : {0}" -f (Get-Item (Join-Path $clientPro "n2n_pro_manager.exe")).VersionInfo.FileVersion)
