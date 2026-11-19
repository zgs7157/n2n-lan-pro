#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
N2N LAN Pro 核心引擎（无 GUI 依赖）
===================================
给 N2N LAN Pro 客户端与命令行提供：
- 网络诊断：连通性 / 延迟丢包 / 端口探测 / 子网存活扫描 / MTU 探测 / 路由表 / DNS 反查
- 连接审计：JSONL 事件流水 + Markdown/JSON 报告导出
- 增强 edge 会话：在免费版 EdgeSession 基础上开放高级 n2n 参数

房间码 / 密钥派生 / IP 分配全部复用 n2n_room_manager，保证与免费版互通。
"""

import ipaddress
import json
import os
import re
import socket
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import n2n_room_manager as base

IS_WINDOWS = base.IS_WINDOWS
IS_MACOS = base.IS_MACOS
PRO_VERSION = "1.0.1"
PRO_NAME = "N2N LAN Pro"

# 默认端口探测清单：常用远程管理 / 联机 / n2n 相关端口
DEFAULT_PORTS = [22, 23, 80, 135, 139, 443, 445, 3389, 5900, 7654, 8080, 25565, 23333]


# ----------------------------------------------------------------------------
# 子进程执行与解码（Windows 控制台输出是 GBK/OEM 代码页）
# ----------------------------------------------------------------------------
def run_cmd(cmd, timeout=25):
    """执行命令并返回 (returncode, 文本输出)。失败时 returncode=-1、文本为错误信息。"""
    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if IS_WINDOWS else 0,
        )
        codec = "mbcs" if IS_WINDOWS else "utf-8"
        out = (p.stdout or b"").decode(codec, "replace")
        err = (p.stderr or b"").decode(codec, "replace")
        text = out if out.strip() else err
        return p.returncode, text
    except FileNotFoundError:
        return -1, "命令不存在：%s" % cmd[0]
    except subprocess.TimeoutExpired:
        return -1, "命令超时（%d 秒）" % timeout
    except Exception as e:            # noqa: BLE001
        return -1, str(e)


# ----------------------------------------------------------------------------
# 连通性与延迟
# ----------------------------------------------------------------------------
RE_RTT = re.compile(r"(?:时间|time)[=<]\s*(\d+(?:\.\d+)?)\s*ms", re.I)
RE_LOSS = re.compile(r"(\d+(?:\.\d+)?)%\s*(?:的丢失|loss)", re.I)


def ping_once(ip, timeout_ms=800):
    """单次 ping：返回 (是否通, rtt 毫秒或 None, 原始输出)。"""
    if IS_WINDOWS:
        cmd = ["ping", "-n", "1", "-w", str(timeout_ms), ip]
    elif IS_MACOS:
        cmd = ["ping", "-c", "1", "-W", str(max(timeout_ms, 1000)), "-t", "1", ip]
    else:
        cmd = ["ping", "-c", "1", "-W", str(max(1, timeout_ms // 1000)), ip]
    code, text = run_cmd(cmd, timeout=max(6, timeout_ms // 1000 + 4))
    if code != 0:
        return False, None, text
    m = RE_RTT.search(text)
    rtt = float(m.group(1)) if m else 0.0
    return True, rtt, text


def ping_stats(ip, count=10, timeout_ms=1000):
    """连续 ping，统计 通/丢包/最小/平均/最大/抖动。"""
    ok_cnt = 0
    rtts = []
    for _ in range(max(1, count)):
        ok, rtt, _txt = ping_once(ip, timeout_ms=timeout_ms)
        if ok:
            ok_cnt += 1
            rtts.append(rtt or 0.0)
    res = {
        "target": ip,
        "sent": count,
        "received": ok_cnt,
        "loss_pct": round((count - ok_cnt) * 100.0 / count, 1),
        "min_ms": round(min(rtts), 1) if rtts else None,
        "avg_ms": round(sum(rtts) / len(rtts), 1) if rtts else None,
        "max_ms": round(max(rtts), 1) if rtts else None,
        "jitter_ms": round(max(rtts) - min(rtts), 1) if len(rtts) > 1 else (0.0 if rtts else None),
    }
    return res


# ----------------------------------------------------------------------------
# 端口探测
# ----------------------------------------------------------------------------
def probe_port(ip, port, timeout=0.4):
    """TCP connect 探测：返回 {"port","open","state","ms"}；state=open/closed/filtered"""
    t0 = time.time()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        rc = s.connect_ex((ip, int(port)))
        ms = round((time.time() - t0) * 1000, 1)
        if rc == 0:
            return {"port": int(port), "open": True, "state": "open", "ms": ms}
        # WSAETIMEDOUT / 10060 = 被丢包（可能被防火墙过滤）；其余=连接被拒
        return {"port": int(port), "open": False,
                "state": "filtered" if rc in (10060, 110) else "closed", "ms": ms}
    except Exception:
        return {"port": int(port), "open": False, "state": "filtered", "ms": None}
    finally:
        try:
            s.close()
        except Exception:
            pass


def scan_ports(ip, ports=None, timeout=0.4, workers=32):
    """并发探测一组端口，返回按端口排序的结果列表。"""
    ports = ports or DEFAULT_PORTS
    if isinstance(ports, str):
        ports = parse_port_list(ports)
    results = []
    with ThreadPoolExecutor(max_workers=min(max(1, workers), len(ports) or 1)) as ex:
        for r in ex.map(lambda p: probe_port(ip, p, timeout), ports):
            results.append(r)
    return sorted(results, key=lambda x: x["port"])


def parse_port_list(text):
    """'22,80,443' / '1-1024' / '22,80,8000-8100' → [int]"""
    out = []
    for part in re.split(r"[,\s]+", (text or "").strip()):
        if not part:
            continue
        m = re.match(r"^(\d+)-(\d+)$", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a > b:
                a, b = b, a
            out.extend(range(a, min(b, 65535) + 1))
        elif part.isdigit() and 0 < int(part) < 65536:
            out.append(int(part))
    return sorted(set(out))


# ----------------------------------------------------------------------------
# 子网存活扫描
# ----------------------------------------------------------------------------
def arp_table():
    """读取 ARP 缓存 → {ip: mac}（Windows: arp -a）。"""
    code, text = run_cmd(["arp", "-a"] if IS_WINDOWS else ["ip", "neigh"], timeout=12)
    table = {}
    if code != 0:
        return table
    for line in text.splitlines():
        m = re.search(r"(\d{1,3}(?:\.\d{1,3}){3})\s+([0-9a-fA-F]{2}(?:[-:][0-9a-fA-F]{2}){5})", line)
        if m:
            table[m.group(1)] = m.group(2).replace("-", ":").lower()
    return table


def sweep_subnet(subnet, timeout_ms=600, workers=48, progress=None, stop_flag=None):
    """并发 ping 扫描 /24（或给定网段）的存活主机。

    subnet 可以是 "10.240.0" 这样的三段的房间网段，也可以是 "192.168.1.0/24"。
    返回 {"targets": n, "alive": [{"ip","rtt","mac"}...]}
    """
    net = None
    try:
        if "/" in subnet:
            net = ipaddress.ip_network(subnet, strict=False)
        else:
            net = ipaddress.ip_network(subnet + ".0/24", strict=False)
    except ValueError:
        raise ValueError("网段格式不对：%s" % subnet)

    hosts = [str(h) for h in net.hosts()]
    if len(hosts) > 4094:
        raise ValueError("网段太大（%d 个地址），请用 /20 及更小的范围" % len(hosts))
    macs = arp_table()
    alive = []
    done = [0]
    total = len(hosts)

    def worker(ip):
        if stop_flag and stop_flag.is_set():
            return None
        ok, rtt, _ = ping_once(ip, timeout_ms=timeout_ms)
        done[0] += 1
        if progress:
            try:
                progress(done[0], total)
            except Exception:
                pass
        if not ok and ip not in macs:
            return None
        return {"ip": ip, "rtt": rtt, "mac": macs.get(ip, "")}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for r in ex.map(worker, hosts):
            if r:
                alive.append(r)
    alive.sort(key=lambda x: tuple(int(p) for p in x["ip"].split(".")))
    return {"targets": total, "alive": alive, "subnet": str(net)}


# ----------------------------------------------------------------------------
# MTU 探测
# ----------------------------------------------------------------------------
def detect_mtu(ip, low=548, high=1500):
    """二分探测不分片最大载荷，返回 {"ip","payload","mtu","steps"}。

    Windows 用 ping -f -l（禁止分片）；其他系统用 ping -M do -s。
    """
    steps = []

    def ok(size):
        if IS_WINDOWS:
            cmd = ["ping", "-f", "-l", str(size), "-n", "1", "-w", "1500", ip]
        elif IS_MACOS:
            cmd = ["ping", "-D", "-s", str(size), "-c", "1", "-W", "1500", ip]
        else:
            cmd = ["ping", "-M", "do", "-s", str(size), "-c", "1", "-W", "2", ip]
        code, text = run_cmd(cmd, timeout=10)
        good = code == 0
        steps.append({"size": size, "ok": good})
        return good

    # 先确认目标可达，否则后面全是超时，结果无意义
    reach, _, _ = ping_once(ip, timeout_ms=1200)
    if not reach:
        return {"ip": ip, "payload": None, "mtu": None, "steps": steps,
                "note": "目标不可达，无法探测 MTU"}

    if not ok(high):
        lo, hi = low, high
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if ok(mid):
                lo = mid
            else:
                hi = mid
        payload = lo
    else:
        payload = high
    # ping 载荷 + 8(ICMP) + 20(IPv4) = 链路 MTU
    return {"ip": ip, "payload": payload, "mtu": payload + 28 if payload else None, "steps": steps}


# -----------------------------------------------------------------------------
# 本机网络摘要 / 路由 / DNS
# --------------------------------------------------------------------------------
def diag_local(include_public=True):
    """本机网络摘要：网卡地址、虚拟网卡、公网 IPv4/IPv6、默认网关。"""
    info = {
        "hostname": socket.gethostname(),
        "ipv4": [],
        "ipv6": [],
        "public_v4": "",
        "public_v6": "",
        "tap": [],
        "gateway": "",
        "dns": [],
    }
    # 本机地址（用 UDP 连接探测默认出口，不真正发包）
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 53))
        info["ipv4"].append(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        info["ipv6"] = list(base.get_local_ipv6s())
    except Exception:
        pass
    try:
        code, text = run_cmd(["ipconfig", "/all"] if IS_WINDOWS else ["ip", "addr"], timeout=20)
        if code == 0:
            # 中文 ipconfig 的字段行形如「默认网关. . . . : 值」，续行缩进更深；
            # 先把字段行与续行聚合，再按字段名取值，避免 IPv6 行把 IPv4 顶掉
            fields = []
            for line in text.splitlines():
                if ". ." in line and ":" in line:
                    key, _, val = line.partition(":")
                    fields.append([key.strip(" .\t"), val.strip()])
                elif fields and line.startswith(" " * 20) and line.strip():
                    fields[-1][1] = (fields[-1][1] + " " + line.strip()).strip()
                if re.search(r"TAP-Windows|n2n|tun|tap", line, re.I):
                    info["tap"].append(line.strip())
            gws, dnss = [], []
            for k, v in fields:
                kl = k.lower()
                if "默认网关" in k or "default gateway" in kl:
                    gws.append(v)
                elif "dns 服务器" in kl or "dns servers" in kl:
                    dnss.append(v)
            for v in gws:
                m = re.search(r"(\d{1,3}(?:\.\d{1,3}){3})", v)
                if m:
                    info["gateway"] = m.group(1)
                    break
            for v in dnss:
                for ip4 in re.findall(r"(\d{1,3}(?:\.\d{1,3}){3})", v):
                    if ip4 not in info["dns"]:
                        info["dns"].append(ip4)
    except Exception:
        pass
    if include_public:
        try:
            v4, _ = base.fetch_public_ip(4)
            info["public_v4"] = v4 or ""
        except Exception:
            pass
        try:
            v6, _ = base.fetch_public_ip(6)
            info["public_v6"] = v6 or ""
        except Exception:
            pass
    return info


def route_table():
    """返回路由表文本（Windows: route print；Linux: ip route；macOS: netstat -rn）。"""
    if IS_WINDOWS:
        cmd = ["route", "print", "-4"]
    elif IS_MACOS:
        cmd = ["netstat", "-rn"]
    else:
        cmd = ["ip", "route"]
    return run_cmd(cmd, timeout=20)


def dns_lookup(target):
    """正向 + 反向解析：返回 {"target","ip","ptr","aliases"}。"""
    out = {"target": target, "ip": [], "ptr": "", "aliases": [], "error": ""}
    try:
        ipaddress.ip_address(target)
        is_ip = True
    except ValueError:
        is_ip = False
    if is_ip:
        try:
            host, aliases, _addrs = socket.gethostbyaddr(target)
            out["ptr"] = host
            out["aliases"] = list(aliases or [])
        except Exception as e:          # noqa: BLE001
            out["error"] = str(e)
    else:
        try:
            infos = socket.getaddrinfo(target, None)
            ips = sorted({i[4][0] for i in infos})
            out["ip"] = ips
        except Exception as e:          # noqa: BLE001
            out["error"] = str(e)
    return out


# ----------------------------------------------------------------------------
# 连接审计
# ----------------------------------------------------------------------------
class AuditLog:
    """连接与操作事件流水：内存 + JSONL 落盘，可导出 Markdown / JSON 报告。"""

    def __init__(self, path, limit=5000):
        self.path = path
        self.limit = limit
        self.lock = threading.Lock()
        self.events = []
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        self.events.append(json.loads(line))
                    except Exception:
                        continue
            if len(self.events) > self.limit:
                self.events = self.events[-self.limit:]
        except Exception:
            pass

    def log(self, kind, **kw):
        ev = {"ts": time.time(),
              "time": time.strftime("%Y-%m-%d %H:%M:%S"),
              "kind": kind}
        ev.update({k: v for k, v in kw.items() if v is not None})
        with self.lock:
            self.events.append(ev)
            if len(self.events) > self.limit:
                self.events = self.events[-self.limit:]
            try:
                os.makedirs(os.path.dirname(self.path), exist_ok=True)
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(ev, ensure_ascii=False) + "\n")
            except Exception:
                pass
        return ev

    def clear(self):
        with self.lock:
            self.events = []
            try:
                if os.path.exists(self.path):
                    os.remove(self.path)
            except Exception:
                pass

    def stats(self):
        with self.lock:
            evs = list(self.events)
        kinds = {}
        rooms = set()
        for e in evs:
            kinds[e.get("kind", "?")] = kinds.get(e.get("kind", "?"), 0) + 1
            if e.get("code"):
                rooms.add(e["code"])
        return {"total": len(evs), "kinds": kinds, "rooms": len(rooms),
                "first": evs[0]["time"] if evs else "",
                "last": evs[-1]["time"] if evs else ""}

    def export(self, out_dir):
        """导出 Markdown + JSON 快照，返回 (md_path, json_path)。"""
        with self.lock:
            evs = list(self.events)
        os.makedirs(out_dir, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        md_path = os.path.join(out_dir, "n2n-pro-audit-%s.md" % stamp)
        json_path = os.path.join(out_dir, "n2n-pro-audit-%s.json" % stamp)

        lines = ["# N2N LAN Pro 连接审计报告", "",
                 "- 导出时间：%s" % time.strftime("%Y-%m-%d %H:%M:%S"),
                 "- 主机：%s" % socket.gethostname(),
                 "- 事件总数：%d" % len(evs), ""]
        st = self.stats()
        lines += ["## 活动统计", "",
                  "| 类型 | 次数 |", "|---|---|"]
        for k, v in sorted(st["kinds"].items()):
            lines.append("| %s | %d |" % (k, v))
        lines += ["", "## 事件明细", "",
                  "| 时间 | 类型 | 房间码 | 角色 | 虚拟 IP | 服务器 | 详情 |",
                  "|---|---|---|---|---|---|---|"]
        for e in evs:
            lines.append("| %s | %s | %s | %s | %s | %s | %s |" % (
                e.get("time", ""), e.get("kind", ""), e.get("code", ""),
                e.get("role", ""), e.get("ip", ""), e.get("server", ""),
                str(e.get("detail", "")).replace("|", "/")))
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(evs, f, ensure_ascii=False, indent=2)
        return md_path, json_path


# ----------------------------------------------------------------------------
# 增强 edge 会话：开放 n2n 高级参数
# ----------------------------------------------------------------------------
class ProEdgeSession(base.EdgeSession):
    """在免费版 EdgeSession 的启动参数基础上叠加 Pro 高级选项。

    注意：-H（头部加密）、-A（加密算法）、-r（转发放行）会改变 n2n 协议行为，
    开启后可能无法与免费版 / 默认参数的对端互通，界面里已明确提示。
    """

    def start(self, community, key, ip, supernode_list):
        self.stop()
        os.makedirs(base.LOG_DIR, exist_ok=True)
        self.log_path = os.path.join(
            base.LOG_DIR, "edge_%s.log" % re.sub(r"[^A-Za-z0-9_-]", "_", community))

        pro = (self.app.cfg.get("pro") or {})
        args = [base.EDGE_EXE, "-c", community, "-k", key, "-a", ip + "/24"]
        local_v6 = self.app.local_ipv6s
        for sn in supernode_list:
            sn = (sn or "").strip()
            if not sn:
                continue
            kind, host, port = base.parse_supernode(sn)
            if kind == "v6":
                if host.lower() in local_v6:
                    args += ["-l", "127.0.0.1:7654"]
                    continue
                lp = self._start_forwarder(host, port)
                if lp is not None:
                    self.app.append_log("[fwd] IPv6 supernode %s → 127.0.0.1:%d" % (host, lp))
                    args += ["-l", "127.0.0.1:%d" % lp]
                else:
                    args += ["-l", "127.0.0.1:7654"]
            else:
                args += ["-l", sn]

        cfg = self.app.cfg
        if cfg.get("use_multicast", True):
            args.append("-E")
        if IS_WINDOWS and cfg.get("use_game_metric", True):
            args += ["-x", "1"]
        args += ["-M", str(int(cfg.get("mtu", base.DEFAULT_MTU))), "-I", "room-" + community]

        # —— Pro 高级参数 ——
        if pro.get("header_encrypt"):
            args.append("-H")
        if pro.get("packet_forward"):
            args.append("-r")
        if pro.get("pmtu_discovery"):
            args.append("-D")
        cipher = (pro.get("cipher") or "").strip()
        if cipher:
            args += ["-A", cipher]
        extra = (pro.get("extra_args") or "").strip()
        if extra:
            args += [a for a in re.split(r"\s+", extra) if a]

        logf = open(self.log_path, "ab", buffering=0)
        self.proc = subprocess.Popen(
            args,
            stdout=logf,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if IS_WINDOWS else 0,
        )
        self.tailer = base.LogTailer(self.log_path, self.app.append_log)
        self.tailer.start()

        if cfg.get("auto_broadcast") and IS_WINDOWS and os.path.exists(base.WINIPBROADCAST_EXE):
            try:
                self.broadcast_proc = subprocess.Popen(
                    [base.WINIPBROADCAST_EXE],
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except Exception:
                self.broadcast_proc = None
        return self.proc.pid


# ----------------------------------------------------------------------------
# 命令行模式
# ----------------------------------------------------------------------------
def cli(argv):
    """N2N LAN Pro 命令行：doctor / scan / ports / ping / mtu / dns / route

    返回进程退出码；不启动 GUI，适合在无桌面环境或脚本里用。
    """
    import argparse

    ap = argparse.ArgumentParser(prog="n2n_pro", description="%s %s (CLI)" % (PRO_NAME, PRO_VERSION))
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    sub = ap.add_subparsers(dest="cmd")

    p_doc = sub.add_parser("doctor", help="本机网络摘要（含公网 IP）")
    p_doc.add_argument("--no-public", action="store_true", help="跳过公网 IP 查询")

    p_scan = sub.add_parser("scan", help="子网存活扫描")
    p_scan.add_argument("subnet", help="例如 10.240.0 或 192.168.1.0/24")
    p_scan.add_argument("--timeout", type=int, default=600, help="单地址超时（毫秒）")

    p_ports = sub.add_parser("ports", help="端口探测")
    p_ports.add_argument("host")
    p_ports.add_argument("-p", "--ports", default=",".join(str(x) for x in DEFAULT_PORTS))

    p_ping = sub.add_parser("ping", help="延迟与丢包统计")
    p_ping.add_argument("host")
    p_ping.add_argument("-n", "--count", type=int, default=10)

    p_mtu = sub.add_parser("mtu", help="MTU 探测")
    p_mtu.add_argument("host")

    p_dns = sub.add_parser("dns", help="域名/IP 解析")
    p_dns.add_argument("target")

    sub.add_parser("route", help="打印本机路由表")

    ns = ap.parse_args(argv)

    def emit(data, render=None):
        if ns.json:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        elif render:
            print(render(data))
        else:
            print(json.dumps(data, ensure_ascii=False, indent=2))

    if ns.cmd == "doctor":
        d = diag_local(include_public=not ns.no_public)
        emit(d, lambda x: "\n".join([
            "主机名     : %s" % x["hostname"],
            "本机 IPv4  : %s" % (", ".join(x["ipv4"]) or "无"),
            "本机 IPv6  : %s" % (", ".join(x["ipv6"]) or "无"),
            "公网 IPv4  : %s" % (x["public_v4"] or "无（NAT 后或 IPv6-only）"),
            "公网 IPv6  : %s" % (x["public_v6"] or "无"),
            "默认网关   : %s" % (x["gateway"] or "未知"),
            "DNS        : %s" % (", ".join(x["dns"][:4]) or "未知"),
            "虚拟网卡   : %d 条匹配" % len(x["tap"]),
        ]))
    elif ns.cmd == "scan":
        r = sweep_subnet(ns.subnet, timeout_ms=ns.timeout)
        emit(r, lambda x: "扫描 %s：%d 个地址，存活 %d\n%s" % (
            x["subnet"], x["targets"], len(x["alive"]),
            "\n".join("  %-15s rtt=%s ms %s" % (
                a["ip"], a["rtt"], a["mac"]) for a in x["alive"])))
    elif ns.cmd == "ports":
        res = scan_ports(ns.host, parse_port_list(ns.ports))
        emit(res, lambda x: "\n".join("  %5d %-9s %s ms" % (
            r["port"], r["state"], r["ms"]) for r in x))
    elif ns.cmd == "ping":
        r = ping_stats(ns.host, count=ns.count)
        emit(r, lambda x: "目标 %s：%d/%d 通，丢包 %.1f%%，min/avg/max = %s/%s/%s ms" % (
            x["target"], x["received"], x["sent"], x["loss_pct"],
            x["min_ms"], x["avg_ms"], x["max_ms"]))
    elif ns.cmd == "mtu":
        r = detect_mtu(ns.host)
        emit(r, lambda x: "目标 %s：最大不分片载荷 %s，链路 MTU %s%s" % (
            x["ip"], x["payload"], x["mtu"], ("（%s）" % x["note"]) if x.get("note") else ""))
    elif ns.cmd == "dns":
        r = dns_lookup(ns.target)
        emit(r, lambda x: "目标 %s\n  IP: %s\n  PTR: %s\n  别名: %s%s" % (
            x["target"], ", ".join(x["ip"]) or "-", x["ptr"] or "-",
            ", ".join(x["aliases"]) or "-",
            ("\n  错误: " + x["error"]) if x["error"] else ""))
    elif ns.cmd == "route":
        code, text = route_table()
        print(text)
        return code if code >= 0 else 1
    else:
        ap.print_help()
        return 0
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(cli(sys.argv[1:]))
