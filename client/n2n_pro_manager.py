#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
N2N LAN Pro（专业版）
=====================
在免费版同一套界面与房间码体系之上，为网络安全 / 网络调试人员增加：

1. 网络诊断面板：本机网络摘要、Ping 延迟与丢包、端口探测、子网存活扫描、MTU 探测、路由表、DNS 解析
2. 连接审计与导出：所有建房/进房/连接/失败/离开/IP 分配事件流水，可一键导出 Markdown + JSON 报告
3. 房间库：保存多个房间档案，一键切换（受 Windows 单 TAP 驱动限制，同一时刻一个房间在线）
4. 高级参数：自定义 supernode / 多节点、MTU、组播、头部加密 -H、转发放行 -r、PMTU -D、加密算法 -A

房间码、密钥派生、虚拟 IP 分配全部复用 n2n_room_manager，与免费版完全互通。
"""

import os
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

# —— 先按 Pro 的路径改写免费版模块的全局路径，再导入其 App 类 ——
import n2n_room_manager as base

PRO_CONFIG_PATH = os.path.join(base.BASE_DIR, "config_pro.json")
PRO_LOG_DIR = os.path.join(base.BASE_DIR, "logs_pro")
PRO_AUDIT_PATH = os.path.join(PRO_LOG_DIR, "audit.jsonl")

PRO_EXTRA_DEFAULTS = {
    "profiles": [],                 # 房间库：[{name, code, role, server, ip, note, last_used}]
    "pro": {                        # 高级参数
        "header_encrypt": False,    # edge -H（开启后与免费版默认参数不互通）
        "packet_forward": False,    # edge -r
        "pmtu_discovery": False,    # edge -D
        "cipher": "",               # edge -A（aes / chacha20 / none，空=默认）
        "extra_args": "",           # 追加的原始 edge 参数
        "force_v6_order": False,    # 诊断用：优先进 IPv6 探测
    },
}


def load_config_pro():
    import json
    cfg = dict(base.DEFAULT_CONFIG)
    cfg.update(PRO_EXTRA_DEFAULTS)
    if os.path.exists(PRO_CONFIG_PATH):
        try:
            with open(PRO_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in data.items():
                if k in cfg:
                    if isinstance(cfg.get(k), dict) and isinstance(v, dict):
                        merged = dict(cfg[k])
                        merged.update(v)
                        cfg[k] = merged
                    else:
                        cfg[k] = v
        except Exception:
            pass
    return cfg


def save_config_pro(cfg):
    import json
    try:
        os.makedirs(base.BASE_DIR, exist_ok=True)
        with open(PRO_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# 让免费版的 App / EdgeSession / 日志全部落到 Pro 的配置与目录
base.load_config = load_config_pro
base.save_config = save_config_pro
base.CONFIG_PATH = PRO_CONFIG_PATH
base.LOG_DIR = PRO_LOG_DIR

import n2n_pro_core as core            # noqa: E402  （需在 base 路径改写后导入）

try:
    import room_presence               # noqa: E402  局域网房间发现（Pro 独占）
except Exception:
    room_presence = None


# ----------------------------------------------------------------------------
# Pro 文案（跟随免费版的语言切换）
# ----------------------------------------------------------------------------
PRO_TEXT = {
    "zh": {
        "badge": "PRO",
        "title": "N2N LAN Pro",
        "btn_diag": "网络诊断",
        "btn_audit": "连接审计",
        "btn_profiles": "房间库",
        "btn_adv": "高级参数",
        "btn_near": "附近房间",
        "near_title": "附近房间",
        "near_hint": "同一局域网里有人开房时，房间会自动出现在这里（对方需运行 1.2.2 / Pro 1.0.2 及以上版本）。"
                     "双击即可直接加入。",
        "near_col_code": "房间码", "near_col_host": "房主", "near_col_count": "人数",
        "near_col_src": "来源 IP", "near_col_server": "服务器", "near_col_ver": "版本",
        "near_join": "加入选中", "near_refresh": "刷新",
        "near_empty": "暂未发现房间 —— 等对方开着房间，几秒内会自动出现",
        "near_none_sel": "请先选中一个房间",
        "near_stat": "发现 %(n)d 个房间 · 每 4 秒自动刷新",
        "near_busy": "正在切换房间，请稍候…",
        "near_joining": "正在加入 %(code)s …",
        "tip": "专业版：诊断面板 · 连接审计 · 房间库 · 高级参数；房间码与免费版完全互通",
        "diag_title": "网络诊断",
        "audit_title": "连接审计",
        "profiles_title": "房间库",
        "adv_title": "高级参数",
        "target": "目标地址",
        "ports": "端口",
        "btn_local": "本机摘要",
        "btn_ping": "Ping 统计",
        "btn_ports": "端口探测",
        "btn_mtu": "MTU 探测",
        "btn_sweep": "子网扫描",
        "btn_route": "路由表",
        "btn_dns": "DNS 解析",
        "busy": "执行中…",
        "done": "完成",
        "sweep_prog": "已扫描 %(a)d/%(b)d",
        "local_head": "—— 本机网络摘要 ——",
        "ping_fmt": "目标 %(target)s：%(received)d/%(sent)d 通，丢包 %(loss_pct)s%%，"
                    "min/avg/max = %(min_ms)s/%(avg_ms)s/%(max_ms)s ms，抖动 %(jitter_ms)s ms",
        "port_head": "—— 端口探测 %(host)s ——",
        "mtu_fmt": "最大不分片载荷 %(payload)s 字节 → 链路 MTU 约 %(mtu)s",
        "sweep_fmt": "扫描 %(subnet)s：%(targets)d 个地址，存活 %(alive)d 台",
        "audit_stat": "事件 %(total)d 条 · 房间 %(rooms)d 个 · 起 %(first)s · 止 %(last)s",
        "audit_export": "导出报告",
        "audit_clear": "清空记录",
        "audit_refresh": "刷新",
        "audit_exported": "已导出：\n%(md)s\n%(json)s",
        "audit_clear_ask": "确定清空全部审计记录？该操作会删除 audit.jsonl",
        "col_time": "时间", "col_kind": "类型", "col_code": "房间码",
        "col_role": "角色", "col_ip": "虚拟 IP", "col_detail": "详情",
        "pf_name": "名称", "pf_code": "房间码 / 邀请码", "pf_role": "角色",
        "pf_server": "服务器（可空）", "pf_note": "备注",
        "pf_add": "加入库", "pf_enter": "进入选中", "pf_del": "删除选中",
        "pf_hint": "双击或点「进入选中」即进入该房间。Windows 单 TAP 驱动下同一时刻只有一个房间在线，"
                   "切换会自动断开当前房间（约 2-5 秒）。",
        "pf_need_name": "名称和房间码都要填",
        "pf_bad_code": "房间码应为 8 位（字母数字）",
        "pf_role_host": "房主", "pf_role_guest": "加入",
        "pf_busy": "当前有房间在线，已先自动断开再进入",
        "adv_sn": "自定义 supernode（host:port，可逗号分隔多个）",
        "adv_mtu": "MTU",
        "adv_multicast": "接受组播/广播（edge -E，MC 局域网发现需要）",
        "adv_metric": "游戏跃点优化（edge -x 1，仅 Windows）",
        "adv_auto_bc": "随房间自动启动广播助手（WinIPBroadcast）",
        "adv_header": "头部加密（edge -H）⚠ 开启后与免费版默认参数不互通",
        "adv_forward": "允许转发（edge -r，可做中转节点）",
        "adv_pmtu": "路径 MTU 发现（edge -D）",
        "adv_cipher": "加密算法（edge -A）",
        "adv_extra": "额外 edge 参数（原样追加）",
        "adv_save": "保存",
        "adv_saved": "已保存到 config_pro.json",
        "ver_hint": "Pro 版 %(v)s：更新随免费版主线发布，可在项目 Releases 页查看",
    },
    "en": {
        "badge": "PRO",
        "title": "N2N LAN Pro",
        "btn_diag": "Diagnostics",
        "btn_audit": "Audit",
        "btn_profiles": "Room vault",
        "btn_adv": "Advanced",
        "btn_near": "Nearby rooms",
        "near_title": "Nearby rooms",
        "near_hint": "Rooms opened by others on the same LAN show up here automatically "
                     "(both sides need 1.2.2 / Pro 1.0.2 or newer). Double-click to join.",
        "near_col_code": "Room code", "near_col_host": "Host", "near_col_count": "Members",
        "near_col_src": "From IP", "near_col_server": "Server", "near_col_ver": "Version",
        "near_join": "Join selected", "near_refresh": "Refresh",
        "near_empty": "No rooms yet — they appear within seconds while a host keeps a room open",
        "near_none_sel": "Select a room first",
        "near_stat": "%(n)d room(s) found · auto-refresh every 4 s",
        "near_busy": "Switching rooms, please wait…",
        "near_joining": "Joining %(code)s …",
        "tip": "Pro: diagnostics · audit · room vault · advanced params; room codes are fully compatible with the free edition",
        "diag_title": "Network diagnostics",
        "audit_title": "Connection audit",
        "profiles_title": "Room vault",
        "adv_title": "Advanced parameters",
        "target": "Target",
        "ports": "Ports",
        "btn_local": "Host summary",
        "btn_ping": "Ping stats",
        "btn_ports": "Port probe",
        "btn_mtu": "MTU probe",
        "btn_sweep": "Subnet sweep",
        "btn_route": "Route table",
        "btn_dns": "DNS lookup",
        "busy": "Running…",
        "done": "Done",
        "sweep_prog": "Scanned %(a)d/%(b)d",
        "local_head": "—— Host network summary ——",
        "ping_fmt": "%(target)s: %(received)d/%(sent)d replies, %(loss_pct)s%% loss, "
                    "min/avg/max = %(min_ms)s/%(avg_ms)s/%(max_ms)s ms, jitter %(jitter_ms)s ms",
        "port_head": "—— Port probe %(host)s ——",
        "mtu_fmt": "Max unfragmented payload %(payload)s bytes → link MTU ≈ %(mtu)s",
        "sweep_fmt": "Swept %(subnet)s: %(targets)d addresses, %(alive)d alive",
        "audit_stat": "%(total)d events · %(rooms)d rooms · %(first)s → %(last)s",
        "audit_export": "Export report",
        "audit_clear": "Clear",
        "audit_refresh": "Refresh",
        "audit_exported": "Exported:\n%(md)s\n%(json)s",
        "audit_clear_ask": "Clear all audit records? This deletes audit.jsonl",
        "col_time": "Time", "col_kind": "Type", "col_code": "Room",
        "col_role": "Role", "col_ip": "Virtual IP", "col_detail": "Detail",
        "pf_name": "Name", "pf_code": "Room / invite code", "pf_role": "Role",
        "pf_server": "Server (optional)", "pf_note": "Note",
        "pf_add": "Add", "pf_enter": "Enter selected", "pf_del": "Delete selected",
        "pf_hint": "Double-click or press Enter to join. Windows single-TAP allows one live room at a time; "
                   "switching drops the current room automatically (2-5 s).",
        "pf_need_name": "Name and room code are required",
        "pf_bad_code": "Room code must be 8 alphanumeric characters",
        "pf_role_host": "Host", "pf_role_guest": "Join",
        "pf_busy": "A room is already online; it was dropped first",
        "adv_sn": "Custom supernode (host:port, comma-separated)",
        "adv_mtu": "MTU",
        "adv_multicast": "Accept multicast/broadcast (edge -E, needed for MC LAN discovery)",
        "adv_metric": "Game metric (edge -x 1, Windows only)",
        "adv_auto_bc": "Auto-start broadcast helper (WinIPBroadcast)",
        "adv_header": "Header encryption (edge -H) — breaks compatibility with the free defaults",
        "adv_forward": "Packet forwarding (edge -r, act as relay)",
        "adv_pmtu": "Path MTU discovery (edge -D)",
        "adv_cipher": "Cipher (edge -A)",
        "adv_extra": "Extra edge args (passed verbatim)",
        "adv_save": "Save",
        "adv_saved": "Saved to config_pro.json",
        "ver_hint": "Pro %(v)s: updates follow the main release line, see the project Releases page",
    },
}


def tp(key, **kw):
    lang = base._lang if base._lang in PRO_TEXT else "en"
    s = PRO_TEXT[lang].get(key, key)
    if kw:
        try:
            s = s % kw
        except Exception:
            pass
    return s


# ----------------------------------------------------------------------------
# 主应用
# ----------------------------------------------------------------------------
class ProApp(base.App):
    # 求 Star 指向 Pro 自己的仓库，文案里也用它自己的名字
    REPO_URL = "https://github.com/zgs7157/n2n-lan-pro"
    STAR_APP_NAME = "N2N LAN Pro"

    def __init__(self, root):
        super().__init__(root)
        # 换成支持高级参数的 edge 会话
        try:
            self.session.stop()
        except Exception:
            pass
        self.session = core.ProEdgeSession(self)
        self.audit = core.AuditLog(PRO_AUDIT_PATH)
        self._diag_win = None
        self._audit_win = None
        self._profiles_win = None
        self._adv_win = None
        self._pro_workers = 0
        # 局域网房间发现：常驻监听 23335，收到别人的房间公告就列出来
        self._near_win = None
        self._near_tree = None
        self._btn_near = None
        self._near_last = 0.0
        self._near_sig = None
        self.discovery = None
        if room_presence is not None:
            try:
                self.discovery = room_presence.RoomDiscovery()
                self.discovery.start()
            except Exception:
                self.discovery = None

        root.title("%s %s" % (core.PRO_NAME, core.PRO_VERSION))
        root.geometry("900x780")
        root.minsize(820, 700)
        self._apply_pro_look()
        self.root.after(2000, self._near_tick)

    # ---------------- 主界面：沿用免费版布局，追加 Pro 标识与工具条 ----------------
    def _apply_pro_look(self):
        # 头部标题换成 Pro 名称，并在右侧加一个红色 PRO 徽标
        try:
            for w in self._head.winfo_children():
                if isinstance(w, ttk.Label) and w.cget("text") == base.tr("app_title"):
                    w.configure(text="%s %s" % (core.PRO_NAME, core.PRO_VERSION))
                    self._badge = tk.Label(self._head, text=tp("badge"), bg="#c62828", fg="white",
                                           font=("", 9, "bold"), padx=6, pady=1)
                    self._badge.pack(side="left", padx=(10, 0))
                    break
        except Exception:
            pass
        # 版本按钮改为 Pro 标识，点击只解释版本策略（不吃免费版的更新提示）
        try:
            self._ver_btn.configure(text="Pro %s" % core.PRO_VERSION,
                                    command=self._pro_version_info)
        except Exception:
            pass

        # Pro 工具条：插在「联机玩法」提示之前（第一个是 Pro 独有的附近房间）
        bar = ttk.Frame(self.root)
        self._btn_near = ttk.Button(bar, text=self._near_btn_text(), command=self.open_nearby)
        self._btn_near.pack(side="left", padx=(0, 8))
        for text, cmd, pack_side in (
            (tp("btn_diag"), self.open_diag, "left"),
            (tp("btn_audit"), self.open_audit, "left"),
            (tp("btn_profiles"), self.open_profiles, "left"),
            (tp("btn_adv"), self.open_pro_settings, "left"),
        ):
            ttk.Button(bar, text=text, command=cmd).pack(side=pack_side, padx=(0, 8))
        bar.pack(fill="x", padx=16, pady=(14, 0), before=self.lbl_tip)
        tk.Label(self.root, text=tp("tip"), fg="#666", font=("", 9),
                 wraplength=760, justify="left").pack(anchor="w", padx=16, pady=(4, 2),
                                                     before=self.lbl_tip)

    # ---------------- 附近房间（Pro 独占） ----------------
    def _near_list(self):
        """附近房间列表，排除「自己当前所在的这个房间」"""
        if self.discovery is None:
            return []
        try:
            rows = self.discovery.snapshot()
        except Exception:
            return []
        cur = ((self._params or {}).get("code") or "").replace("-", "").upper()
        out = []
        for r in rows:
            code = (r.get("code") or "").replace("-", "").upper()
            if cur and code == cur:
                continue
            out.append(r)
        return out

    def _near_count(self):
        return len(self._near_list())

    def _near_btn_text(self):
        n = self._near_count()
        return "%s (%d)" % (tp("btn_near"), n)

    def _near_tick(self):
        """每 3 秒刷新工具条角标；附近房间窗口开着就同步列表"""
        try:
            if self._btn_near is not None:
                want = self._near_btn_text()
                if self._btn_near.cget("text") != want:
                    self._btn_near.configure(text=want)
        except Exception:
            pass
        try:
            if self._near_win is not None and self._near_win.winfo_exists():
                self._near_refresh()
        except Exception:
            pass
        try:
            self.root.after(3000, self._near_tick)
        except Exception:
            pass

    def open_nearby(self):
        if self._near_win is not None and self._near_win.winfo_exists():
            self._near_win.lift()
            return
        win = tk.Toplevel(self.root)
        self._near_win = win
        win.title("%s — %s" % (tp("title"), tp("near_title")))
        win.geometry("900x520")
        win.transient(self.root)

        ttk.Label(win, text=tp("near_hint"), foreground="#666", wraplength=840,
                  justify="left").pack(anchor="w", padx=12, pady=(10, 4))
        self._near_stat = tk.Label(win, text="", fg="#777", font=("", 9))
        self._near_stat.pack(anchor="w", padx=12)

        body = ttk.Frame(win)
        body.pack(fill="both", expand=True, padx=12, pady=(6, 0))
        cols = ("code", "host", "count", "src", "server", "ver")
        tree = ttk.Treeview(body, columns=cols, show="headings", height=12)
        for c, t, w in (("code", tp("near_col_code"), 120),
                        ("host", tp("near_col_host"), 118),
                        ("count", tp("near_col_count"), 60),
                        ("src", tp("near_col_src"), 110),
                        ("server", tp("near_col_server"), 236),
                        ("ver", tp("near_col_ver"), 62)):
            tree.heading(c, text=t)
            tree.column(c, width=w, minwidth=w, anchor="w", stretch=False)
        vsb = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        tree.bind("<Double-1>", lambda e: self._near_join())
        self._near_tree = tree
        self._near_rows = {}
        self._near_sig = None

        btns = ttk.Frame(win)
        btns.pack(fill="x", padx=12, pady=(8, 12))
        ttk.Button(btns, text=tp("near_join"), command=self._near_join).pack(side="left")
        ttk.Button(btns, text=tp("near_refresh"), command=self._near_refresh).pack(side="left", padx=6)
        self._near_refresh()

    def _near_refresh(self):
        tree = getattr(self, "_near_tree", None)
        if tree is None:
            return
        rows = self._near_list()
        sig = tuple((r.get("code"), r.get("count"), r.get("host"), r.get("server")) for r in rows)
        # 内容没变就不重建，避免每 3 秒把用户的选中项刷掉
        if sig == getattr(self, "_near_sig", None):
            return
        self._near_sig = sig
        sel_code = ""
        for iid in tree.selection():
            row = (getattr(self, "_near_rows", {}) or {}).get(str(iid))
            if row:
                sel_code = row.get("code") or ""
        self._near_rows = {str(i): r for i, r in enumerate(rows)}
        try:
            tree.delete(*tree.get_children())
            for iid, r in self._near_rows.items():
                code = r.get("code") or ""
                show = base.format_code(code) if len(base.clean_code(code)) == 8 else code
                tree.insert("", "end", iid=iid, values=(
                    show, r.get("host", "") or "—",
                    r.get("count") or 0, r.get("src", "") or "—",
                    r.get("server", "") or "—", r.get("ver", "") or "—"))
            if sel_code:
                for iid, r in self._near_rows.items():
                    if r.get("code") == sel_code:
                        tree.selection_set(iid)
                        break
        except Exception:
            return
        try:
            if rows:
                self._near_stat.configure(text=tp("near_stat", n=len(rows)))
            else:
                self._near_stat.configure(text=tp("near_empty"))
        except Exception:
            pass

    def _near_join(self):
        tree = getattr(self, "_near_tree", None)
        if tree is None:
            return
        sel = tree.selection()
        if not sel:
            messagebox.showwarning(tp("near_title"), tp("near_none_sel"))
            return
        row = (getattr(self, "_near_rows", {}) or {}).get(str(sel[0]))
        if not row:
            return
        if self._busy:
            messagebox.showinfo(tp("near_title"), tp("near_busy"))
            return
        code = base.clean_code(row.get("code") or "")
        if len(code) != 8:
            messagebox.showwarning(tp("near_title"), tp("pf_bad_code"))
            return
        p = {"name": row.get("name") or code, "code": code, "role": "guest",
             "server": row.get("server") or "", "ip": row.get("host") or "",
             "note": "nearby %s" % (row.get("src") or "")}
        try:
            self.audit.log("nearby_join", code=code, role="guest",
                           server=p["server"], detail=row.get("src") or "")
        except Exception:
            pass
        if self._near_win is not None and self._near_win.winfo_exists():
            try:
                self._near_win.destroy()
            except Exception:
                pass
            self._near_win = None
            self._near_tree = None
        self._set_state("preparing", tp("near_joining", code=base.format_code(code)))
        self._enter_profile(p)

    # ---------------- 更新策略（Pro 独立版本号，不误报免费版版本） ----------------
    def _maybe_auto_check(self):
        return

    def check_update(self, manual=False):
        return

    def _pro_version_info(self):
        messagebox.showinfo(tp("title"), tp("ver_hint", v=core.PRO_VERSION))

    # ---------------- 审计钩子 ----------------
    def _start_edge(self, params, server, invite):
        super()._start_edge(params, server, invite)
        try:
            self.audit.log("room_start", code=params.get("code"),
                           role="host" if self._is_host else "guest",
                           ip=params.get("host_ip"), server=server, detail="connecting")
        except Exception:
            pass

    def _mark_connected(self):
        super()._mark_connected()
        try:
            conn = self._connected or {}
            self.audit.log("connected", code=conn.get("code"),
                           role="host" if self._is_host else "guest",
                           ip=conn.get("ip"), server=conn.get("server"), detail="edge OK")
        except Exception:
            pass

    def _finish_fail(self, note=""):
        super()._finish_fail(note)
        try:
            self.audit.log("failed", code=(self._params or {}).get("code"),
                           role="host" if self._is_host else "guest", detail=str(note))
        except Exception:
            pass

    def leave_room(self):
        conn = dict(self._connected or {})
        super().leave_room()
        try:
            self.audit.log("left", code=conn.get("code"), ip=conn.get("ip"),
                           role="host" if self._is_host else "guest", detail="user left")
        except Exception:
            pass

    def _switch_ip(self, new_ip, old_ip):
        super()._switch_ip(new_ip, old_ip)
        try:
            self.audit.log("ip", code=(self._params or {}).get("code"), ip=new_ip,
                           detail="virtual IP %s → %s" % (old_ip, new_ip))
        except Exception:
            pass

    # ---------------- 通用后台执行 ----------------
    def _bg(self, fn, on_ok, on_err=None):
        """后台跑 fn，结果回主线程。"""
        def runner():
            try:
                res = fn()
            except Exception as e:            # noqa: BLE001
                res = e
            try:
                if isinstance(res, Exception):
                    self.root.after(0, lambda: (on_err or (lambda e: None))(res))
                else:
                    self.root.after(0, lambda: on_ok(res))
            except Exception:
                pass
        threading.Thread(target=runner, daemon=True).start()

    # ---------------- 网络诊断 ----------------
    def open_diag(self):
        if self._diag_win is not None and self._diag_win.winfo_exists():
            self._diag_win.lift()
            return
        win = tk.Toplevel(self.root)
        self._diag_win = win
        win.title("%s — %s" % (tp("title"), tp("diag_title")))
        win.geometry("880x640")
        win.transient(self.root)

        top = ttk.Frame(win)
        top.pack(fill="x", padx=12, pady=(12, 6))
        ttk.Label(top, text=tp("target")).pack(side="left")
        dft = ""
        try:
            subnet = ((self._params or {}).get("subnet") or "")
            dft = (subnet + ".1") if subnet else ""
        except Exception:
            dft = ""
        self._diag_host = tk.StringVar(value=dft or "127.0.0.1")
        ttk.Entry(top, textvariable=self._diag_host, width=18, font=("Consolas", 11)).pack(side="left", padx=6)
        ttk.Label(top, text=tp("ports")).pack(side="left", padx=(12, 0))
        self._diag_ports = tk.StringVar(value=",".join(str(p) for p in core.DEFAULT_PORTS))
        ttk.Entry(top, textvariable=self._diag_ports, width=34, font=("Consolas", 10)).pack(side="left", padx=6)

        bar = ttk.Frame(win)
        bar.pack(fill="x", padx=12)
        for text, fn in ((tp("btn_local"), self._diag_local),
                         (tp("btn_ping"), self._diag_ping),
                         (tp("btn_ports"), self._diag_ports_run),
                         (tp("btn_mtu"), self._diag_mtu),
                         (tp("btn_sweep"), self._diag_sweep),
                         (tp("btn_route"), self._diag_route),
                         (tp("btn_dns"), self._diag_dns)):
            ttk.Button(bar, text=text, command=fn).pack(side="left", padx=(0, 6))

        self._diag_status = tk.StringVar(value="")
        ttk.Label(win, textvariable=self._diag_status, foreground="#666").pack(anchor="w", padx=12, pady=(6, 0))

        self._diag_out = scrolledtext.ScrolledText(win, height=24, font=("Consolas", 10), wrap="none")
        self._diag_out.pack(fill="both", expand=True, padx=12, pady=(6, 12))
        self._diag_out.insert("end", "点上面的按钮开始诊断。\n")

    def _diag_write(self, text):
        try:
            self._diag_out.insert("end", text + "\n")
            self._diag_out.see("end")
        except Exception:
            pass

    def _diag_start(self, name):
        try:
            self._diag_status.set("%s：%s" % (name, tp("busy")))
        except Exception:
            pass

    def _diag_end(self, name):
        try:
            self._diag_status.set("%s：%s" % (name, tp("done")))
        except Exception:
            pass

    def _diag_local(self):
        self._diag_start(tp("btn_local"))

        def job():
            d = core.diag_local()
            lines = [tp("local_head"), "hostname: %s" % d["hostname"],
                     "IPv4: %s" % (", ".join(d["ipv4"]) or "-"),
                     "IPv6: %s" % (", ".join(d["ipv6"]) or "-"),
                     "public v4: %s" % (d["public_v4"] or "-"),
                     "public v6: %s" % (d["public_v6"] or "-"),
                     "gateway: %s" % (d["gateway"] or "-"),
                     "dns: %s" % (", ".join(d["dns"][:4]) or "-")]
            if d["tap"]:
                lines.append("virtual adapters:")
                lines += ["  " + t for t in d["tap"][:6]]
            return "\n".join(lines)

        self._bg(job, lambda t: (self._diag_write(t), self._diag_end(tp("btn_local"))),
                 lambda e: self._diag_write("出错：%s" % e))

    def _diag_ping(self):
        host = self._diag_host.get().strip()
        if not host:
            return
        self._diag_start(tp("btn_ping"))

        def job():
            r = core.ping_stats(host, count=10)
            return tp("ping_fmt", **r) if r["received"] else "目标 %s 10 次全部超时（不可达或被过滤）" % host

        self._bg(job, lambda t: (self._diag_write(t), self._diag_end(tp("btn_ping"))),
                 lambda e: self._diag_write("出错：%s" % e))

    def _diag_ports_run(self):
        host = self._diag_host.get().strip()
        ports = core.parse_port_list(self._diag_ports.get())
        if not host or not ports:
            return
        self._diag_start(tp("btn_ports"))

        def job():
            res = core.scan_ports(host, ports)
            lines = [tp("port_head", host=host)]
            for r in res:
                lines.append("  %5d  %-9s %s ms" % (r["port"], r["state"], r["ms"]))
            lines.append("  open: %d / %d" % (sum(1 for r in res if r["open"]), len(res)))
            return "\n".join(lines)

        self._bg(job, lambda t: (self._diag_write(t), self._diag_end(tp("btn_ports"))),
                 lambda e: self._diag_write("出错：%s" % e))

    def _diag_mtu(self):
        host = self._diag_host.get().strip()
        if not host:
            return
        self._diag_start(tp("btn_mtu"))

        def job():
            r = core.detect_mtu(host)
            if not r.get("payload"):
                return "目标 %s：%s" % (host, r.get("note") or "探测失败")
            return tp("mtu_fmt", **r)

        self._bg(job, lambda t: (self._diag_write(t), self._diag_end(tp("btn_mtu"))),
                 lambda e: self._diag_write("出错：%s" % e))

    def _diag_sweep(self):
        subnet = ""
        try:
            subnet = ((self._params or {}).get("subnet") or "")
        except Exception:
            subnet = ""
        if not subnet:
            messagebox.showinfo(tp("diag_title"), "当前没有活动房间，请输入本机所在网段（如 192.168.1.0/24）。")
            return
        self._diag_start(tp("btn_sweep"))

        def prog(a, b):
            try:
                self.root.after(0, lambda: self._diag_status.set(tp("sweep_prog", a=a, b=b)))
            except Exception:
                pass

        def job():
            r = core.sweep_subnet(subnet, progress=prog)
            lines = [tp("sweep_fmt", subnet=r["subnet"], targets=r["targets"], alive=len(r["alive"]))]
            for a in r["alive"]:
                lines.append("  %-15s rtt=%-6s %s" % (a["ip"], a["rtt"], a["mac"]))
            return "\n".join(lines)

        self._bg(job, lambda t: (self._diag_write(t), self._diag_end(tp("btn_sweep"))),
                 lambda e: self._diag_write("出错：%s" % e))

    def _diag_route(self):
        self._diag_start(tp("btn_route"))

        def job():
            code, text = core.route_table()
            return text

        self._bg(job, lambda t: (self._diag_write(t), self._diag_end(tp("btn_route"))),
                 lambda e: self._diag_write("出错：%s" % e))

    def _diag_dns(self):
        host = self._diag_host.get().strip()
        if not host:
            return
        self._diag_start(tp("btn_dns"))

        def job():
            r = core.dns_lookup(host)
            return "target %s\n  IP: %s\n  PTR: %s\n  aliases: %s%s" % (
                r["target"], ", ".join(r["ip"]) or "-", r["ptr"] or "-",
                ", ".join(r["aliases"]) or "-", ("\n  error: " + r["error"]) if r["error"] else "")

        self._bg(job, lambda t: (self._diag_write(t), self._diag_end(tp("btn_dns"))),
                 lambda e: self._diag_write("出错：%s" % e))

    # ---------------- 连接审计 ----------------
    def open_audit(self):
        if self._audit_win is not None and self._audit_win.winfo_exists():
            self._audit_win.lift()
            self._audit_refresh()
            return
        win = tk.Toplevel(self.root)
        self._audit_win = win
        win.title("%s — %s" % (tp("title"), tp("audit_title")))
        win.geometry("900x560")
        win.transient(self.root)

        self._audit_stat = tk.StringVar(value="")
        ttk.Label(win, textvariable=self._audit_stat, foreground="#555").pack(anchor="w", padx=12, pady=(10, 4))

        bar = ttk.Frame(win)
        bar.pack(fill="x", padx=12)
        ttk.Button(bar, text=tp("audit_refresh"), command=self._audit_refresh).pack(side="left")
        ttk.Button(bar, text=tp("audit_export"), command=self._audit_export).pack(side="left", padx=6)
        ttk.Button(bar, text=tp("audit_clear"), command=self._audit_clear).pack(side="left", padx=6)

        body = ttk.Frame(win)
        body.pack(fill="both", expand=True, padx=12, pady=(8, 12))
        cols = ("time", "kind", "code", "role", "ip", "detail")
        tree = ttk.Treeview(body, columns=cols, show="headings", height=18)
        for c, t, w in (("time", tp("col_time"), 150), ("kind", tp("col_kind"), 110),
                        ("code", tp("col_code"), 110), ("role", tp("col_role"), 70),
                        ("ip", tp("col_ip"), 110), ("detail", tp("col_detail"), 300)):
            tree.heading(c, text=t)
            tree.column(c, width=w, anchor="w")
        vsb = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._audit_tree = tree
        self._audit_refresh()

    def _audit_refresh(self):
        tree = getattr(self, "_audit_tree", None)
        if tree is None:
            return
        try:
            for i in tree.get_children():
                tree.delete(i)
            for e in self.audit.events[-800:]:
                tree.insert("", "end", values=(e.get("time", ""), e.get("kind", ""),
                                               e.get("code", ""), e.get("role", ""),
                                               e.get("ip", ""), e.get("detail", "")))
            st = self.audit.stats()
            self._audit_stat.set(tp("audit_stat", total=st["total"], rooms=st["rooms"],
                                    first=st["first"] or "-", last=st["last"] or "-"))
        except Exception:
            pass

    def _audit_export(self):
        try:
            out_dir = os.path.join(base.BASE_DIR, "audit_reports")
            md, js = self.audit.export(out_dir)
            messagebox.showinfo(tp("audit_title"), tp("audit_exported", md=md, json=js))
        except Exception as e:
            messagebox.showerror(tp("audit_title"), str(e))

    def _audit_clear(self):
        if not messagebox.askyesno(tp("audit_title"), tp("audit_clear_ask")):
            return
        self.audit.clear()
        self._audit_refresh()

    # ---------------- 房间库 ----------------
    def open_profiles(self):
        if self._profiles_win is not None and self._profiles_win.winfo_exists():
            self._profiles_win.lift()
            return
        win = tk.Toplevel(self.root)
        self._profiles_win = win
        win.title("%s — %s" % (tp("title"), tp("profiles_title")))
        win.geometry("920x600")
        win.transient(self.root)

        ttk.Label(win, text=tp("pf_hint"), foreground="#666", wraplength=860,
                  justify="left").pack(anchor="w", padx=12, pady=(10, 6))

        body = ttk.Frame(win)
        body.pack(fill="both", expand=True, padx=12)
        cols = ("name", "code", "role", "server", "note")
        tree = ttk.Treeview(body, columns=cols, show="headings", height=14)
        for c, t, w in (("name", tp("pf_name"), 180), ("code", tp("pf_code"), 170),
                        ("role", tp("pf_role"), 80), ("server", tp("pf_server"), 240),
                        ("note", tp("pf_note"), 220)):
            tree.heading(c, text=t)
            tree.column(c, width=w, anchor="w")
        vsb = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        tree.bind("<Double-1>", lambda e: self._pf_enter())
        self._pf_tree = tree

        form = ttk.Frame(win)
        form.pack(fill="x", padx=12, pady=(10, 4))
        self._pf_name = tk.StringVar()
        self._pf_code = tk.StringVar()
        self._pf_role = tk.StringVar(value=tp("pf_role_guest"))
        self._pf_server = tk.StringVar()
        self._pf_note = tk.StringVar()
        ttk.Label(form, text=tp("pf_name")).grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self._pf_name, width=20).grid(row=0, column=1, padx=(4, 12))
        ttk.Label(form, text=tp("pf_code")).grid(row=0, column=2, sticky="w")
        ttk.Entry(form, textvariable=self._pf_code, width=24, font=("Consolas", 11)).grid(row=0, column=3, padx=(4, 12))
        ttk.Label(form, text=tp("pf_role")).grid(row=0, column=4, sticky="w")
        cb = ttk.Combobox(form, textvariable=self._pf_role, width=8,
                          values=[tp("pf_role_host"), tp("pf_role_guest")], state="readonly")
        cb.grid(row=0, column=5, padx=(4, 12))
        ttk.Label(form, text=tp("pf_server")).grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(form, textvariable=self._pf_server, width=34).grid(row=1, column=1, columnspan=2,
                                                                    sticky="w", padx=(4, 12), pady=(6, 0))
        ttk.Label(form, text=tp("pf_note")).grid(row=1, column=3, sticky="w", pady=(6, 0))
        ttk.Entry(form, textvariable=self._pf_note, width=30).grid(row=1, column=4, columnspan=2,
                                                                   sticky="w", padx=(4, 12), pady=(6, 0))

        btns = ttk.Frame(win)
        btns.pack(fill="x", padx=12, pady=(4, 12))
        ttk.Button(btns, text=tp("pf_add"), command=self._pf_add).pack(side="left")
        ttk.Button(btns, text=tp("pf_enter"), command=self._pf_enter).pack(side="left", padx=6)
        ttk.Button(btns, text=tp("pf_del"), command=self._pf_del).pack(side="left", padx=6)

        self._pf_refresh()

    def _pf_refresh(self):
        tree = getattr(self, "_pf_tree", None)
        if tree is None:
            return
        try:
            for i in tree.get_children():
                tree.delete(i)
            for idx, p in enumerate(self.cfg.get("profiles") or []):
                tree.insert("", "end", iid=str(idx), values=(
                    p.get("name", ""), p.get("code", ""), p.get("role", ""),
                    p.get("server", ""), p.get("note", "")))
        except Exception:
            pass

    def _pf_add(self):
        name = self._pf_name.get().strip()
        code = base.clean_code(self._pf_code.get())
        if not name or not code:
            messagebox.showwarning(tp("profiles_title"), tp("pf_need_name"))
            return
        if len(code) != 8:
            messagebox.showwarning(tp("profiles_title"), tp("pf_bad_code"))
            return
        role = "host" if self._pf_role.get() == tp("pf_role_host") else "guest"
        params = base.code_to_params(code) or {}
        item = {"name": name, "code": code, "role": role,
                "server": self._pf_server.get().strip(),
                "ip": params.get("host_ip", ""),
                "note": self._pf_note.get().strip(),
                "last_used": ""}
        profiles = list(self.cfg.get("profiles") or [])
        profiles = [p for p in profiles if not (p.get("code") == code and p.get("name") == name)]
        profiles.append(item)
        self.cfg["profiles"] = profiles
        base.save_config(self.cfg)
        self.audit.log("profile_add", code=code, role=role, server=item["server"], detail=name)
        self._pf_refresh()

    def _pf_del(self):
        tree = getattr(self, "_pf_tree", None)
        if tree is None:
            return
        sel = tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        profiles = list(self.cfg.get("profiles") or [])
        if 0 <= idx < len(profiles):
            removed = profiles.pop(idx)
            self.cfg["profiles"] = profiles
            base.save_config(self.cfg)
            self.audit.log("profile_del", code=removed.get("code"), detail=removed.get("name"))
            self._pf_refresh()

    def _pf_enter(self):
        tree = getattr(self, "_pf_tree", None)
        if tree is None:
            return
        sel = tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        profiles = list(self.cfg.get("profiles") or [])
        if not (0 <= idx < len(profiles)):
            return
        p = profiles[idx]
        p["last_used"] = time.strftime("%Y-%m-%d %H:%M:%S")
        base.save_config(self.cfg)
        self._enter_profile(p)

    def _leave_silent(self):
        """切房间时不弹确认框，直接收摊（房间库 / 附近房间一键切换用）"""
        conn = dict(self._connected or {})
        try:
            self.session.stop()
            self.host_sn.stop()
            self.ip_alloc.stop()
        except Exception:
            pass
        self._connected = None
        self._busy = False
        try:
            self.chat_listener.clear_room()
            if self.presence is not None:
                self.presence.clear_room()
            if self.chat_win is not None:
                self._close_chat()
            if self.mem_tree is not None:
                self.mem_tree.delete(*self.mem_tree.get_children())
                self.lbl_members.configure(text=base.tr("members_wait"))
            if self.card.winfo_ismapped():
                self.card.pack_forget()
        except Exception:
            pass
        self._set_state("idle")
        try:
            self.audit.log("left", code=conn.get("code"), ip=conn.get("ip"),
                           role="host" if self._is_host else "guest",
                           detail="auto (switch room)")
        except Exception:
            pass

    def _enter_profile(self, p):
        if self._busy:
            return
        if self.session.running or self._connected:
            try:
                self._leave_silent()
            except Exception:
                pass
            time.sleep(1.0)
        code = base.clean_code(p.get("code"))
        params = base.code_to_params(code)
        if not params:
            messagebox.showwarning(tp("profiles_title"), tp("pf_bad_code"))
            return
        self._busy = True
        try:
            self.btn_host.configure(state="disabled")
            self.btn_join.configure(state="disabled")
        except Exception:
            pass
        self._retry_done = False
        self._ip_asked = False
        self._v6_gateway_up = False
        self._set_state("preparing", base.tr("prep_driver"))
        snapshot = dict(self.cfg)
        if p.get("role") == "host":
            self._is_host = True
            threading.Thread(target=self._host_flow, args=(params, snapshot), daemon=True).start()
        else:
            self._is_host = False
            server = p.get("server") or ""
            threading.Thread(target=self._join_flow, args=(params, server), daemon=True).start()
        self.audit.log("profile_enter", code=code, role=p.get("role"),
                       server=p.get("server"), detail=p.get("name", ""))

    # ---------------- 高级参数 ----------------
    def open_pro_settings(self):
        if self._adv_win is not None and self._adv_win.winfo_exists():
            self._adv_win.lift()
            return
        win = tk.Toplevel(self.root)
        self._adv_win = win
        win.title("%s — %s" % (tp("title"), tp("adv_title")))
        win.geometry("700x560")
        win.transient(self.root)

        pro = dict(self.cfg.get("pro") or {})

        ttk.Label(win, text=tp("adv_sn"), foreground="#555").pack(anchor="w", padx=14, pady=(12, 2))
        self._adv_sn = tk.StringVar(value=self.cfg.get("supernode") or ",".join(self.cfg.get("public_nodes") or []))
        ttk.Entry(win, textvariable=self._adv_sn, width=64).pack(anchor="w", padx=14)

        ttk.Label(win, text=tp("adv_mtu"), foreground="#555").pack(anchor="w", padx=14, pady=(10, 2))
        self._adv_mtu = tk.IntVar(value=int(self.cfg.get("mtu") or base.DEFAULT_MTU))
        ttk.Spinbox(win, from_=1050, to=1500, increment=10, textvariable=self._adv_mtu,
                    width=8).pack(anchor="w", padx=14)

        self._adv_vars = {}
        for key, text, val in (
            ("use_multicast", tp("adv_multicast"), bool(self.cfg.get("use_multicast", True))),
            ("use_game_metric", tp("adv_metric"), bool(self.cfg.get("use_game_metric", True))),
            ("auto_broadcast", tp("adv_auto_bc"), bool(self.cfg.get("auto_broadcast", False))),
            ("pro.header_encrypt", tp("adv_header"), bool(pro.get("header_encrypt"))),
            ("pro.packet_forward", tp("adv_forward"), bool(pro.get("packet_forward"))),
            ("pro.pmtu_discovery", tp("adv_pmtu"), bool(pro.get("pmtu_discovery"))),
        ):
            var = tk.BooleanVar(value=val)
            ttk.Checkbutton(win, text=text, variable=var).pack(anchor="w", padx=14, pady=2)
            self._adv_vars[key] = var

        ttk.Label(win, text=tp("adv_cipher"), foreground="#555").pack(anchor="w", padx=14, pady=(8, 2))
        self._adv_cipher = tk.StringVar(value=(pro.get("cipher") or ""))
        ttk.Combobox(win, textvariable=self._adv_cipher, width=14, state="readonly",
                     values=["", "aes", "chacha20", "none"]).pack(anchor="w", padx=14)

        ttk.Label(win, text=tp("adv_extra"), foreground="#555").pack(anchor="w", padx=14, pady=(8, 2))
        self._adv_extra = tk.StringVar(value=pro.get("extra_args") or "")
        ttk.Entry(win, textvariable=self._adv_extra, width=64).pack(anchor="w", padx=14)

        ttk.Button(win, text=tp("adv_save"), command=self._adv_save).pack(anchor="w", padx=14, pady=14)

    def _adv_save(self):
        sn = self._adv_sn.get().strip()
        self.cfg["supernode"] = sn
        self.cfg["mtu"] = int(self._adv_mtu.get() or base.DEFAULT_MTU)
        for key, var in self._adv_vars.items():
            if key.startswith("pro."):
                self.cfg.setdefault("pro", {})[key.split(".", 1)[1]] = bool(var.get())
            else:
                self.cfg[key] = bool(var.get())
        self.cfg.setdefault("pro", {})["cipher"] = self._adv_cipher.get().strip()
        self.cfg.setdefault("pro", {})["extra_args"] = self._adv_extra.get().strip()
        base.save_config(self.cfg)
        self.audit.log("adv_save", detail="supernode=%s mtu=%s" % (sn, self.cfg["mtu"]))
        messagebox.showinfo(tp("adv_title"), tp("adv_saved"))


# ----------------------------------------------------------------------------
# 入口
# ----------------------------------------------------------------------------
def selftest():
    """基础自检：房间码互通、诊断函数可用性。"""
    print("%s %s selftest" % (core.PRO_NAME, core.PRO_VERSION))
    params = base.code_to_params("J7N3WD8Y")
    print("  room params:", params)
    assert params and params["community"] == "room-j7n3-wd8y"
    assert base.parse_invite("J7N3-WD8Y@1.2.3.4:7654")["server"] == "1.2.3.4:7654"
    print("  room code compatible with free edition: OK")
    r = core.probe_port("127.0.0.1", 7654, timeout=0.4)
    print("  port probe:", r)
    print("  ok")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("--cli", "cli"):
        return core.cli(argv[1:])
    if "--selftest" in argv:
        selftest()
        return 0
    root = tk.Tk()
    app = ProApp(root)          # noqa: F841
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
