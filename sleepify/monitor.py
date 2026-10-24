# -*- coding: utf-8 -*-
"""Watching an app: its CPU, disk and (optionally, as Administrator) network activity, and deciding when it is done."""
import collections
import struct
import time

import psutil

from . import common as C
from . import system


# ---------------------------------------------------------------- which apps can be watched
def list_apps(windows=None, include_background=False):
    """[{name, count, title}] - one row per program name. Normally only programs that have a window."""
    if windows is None:
        windows = system.visible_windows()
    groups = {}
    for p in psutil.process_iter(["pid", "name"]):
        name = p.info.get("name") or ""
        if not name:
            continue
        g = groups.setdefault(name.lower(), {"name": name, "count": 0, "title": ""})
        g["count"] += 1
        if not g["title"] and windows.get(p.info["pid"]):
            g["title"] = windows[p.info["pid"]]
    rows = list(groups.values())
    if not include_background and (windows or system.IS_WINDOWS):
        rows = [g for g in rows if g["title"]]
    return sorted(rows, key=lambda g: g["name"].lower())


class NetSpeed:
    """Whole-PC download / upload speed (bytes per second)."""

    def __init__(self, clock=time.time):
        self.clock = clock
        self.prev = None

    def rate(self):
        c = psutil.net_io_counters()
        now = self.clock()
        out = (0.0, 0.0)
        if self.prev and now - self.prev[0] > 0.2:
            dt = now - self.prev[0]
            out = (max(0, c.bytes_recv - self.prev[1]) / dt, max(0, c.bytes_sent - self.prev[2]) / dt)
        self.prev = (now, c.bytes_recv, c.bytes_sent)
        return out


# ---------------------------------------------------------------- per-app network (needs Administrator)
AF_INET, AF_INET6 = 2, 23
TCP_TABLE_OWNER_PID_ALL = 5
TCP_STATE_ESTABLISHED = 5
TCP_ESTATS_DATA = 1


def parse_tcp4_table(buf):
    """Rows of MIB_TCPROW_OWNER_PID -> [(state, laddr, lport, raddr, rport, pid)]."""
    n = struct.unpack_from("<I", buf, 0)[0]
    return [struct.unpack_from("<6I", buf, 4 + i * 24) for i in range(n)]


def parse_tcp6_table(buf):
    """Rows of MIB_TCP6ROW_OWNER_PID -> [(laddr, lscope, lport, raddr, rscope, rport, state, pid)]."""
    n = struct.unpack_from("<I", buf, 0)[0]
    return [struct.unpack_from("<16sII16sIIII", buf, 4 + i * 56) for i in range(n)]


class TcpEstats:
    """Bytes per second sent+received by a set of processes, from Windows' per-connection TCP statistics.
    Needs Administrator rights, sees TCP only (not UDP / QUIC) and is best-effort: when anything fails it
    simply reports that it is unavailable."""

    def __init__(self):
        self.last_error = ""
        self._prev = {}
        self._prev_t = None
        self._ready = None
        if system.IS_WINDOWS:
            import ctypes
            from ctypes import wintypes
            self.ct, self.wt = ctypes, wintypes

            class Row4(ctypes.Structure):
                _fields_ = [("State", wintypes.DWORD), ("LocalAddr", wintypes.DWORD), ("LocalPort", wintypes.DWORD),
                            ("RemoteAddr", wintypes.DWORD), ("RemotePort", wintypes.DWORD)]

            class Row6(ctypes.Structure):
                _fields_ = [("State", wintypes.DWORD), ("LocalAddr", ctypes.c_ubyte * 16),
                            ("LocalScope", wintypes.DWORD), ("LocalPort", wintypes.DWORD),
                            ("RemoteAddr", ctypes.c_ubyte * 16), ("RemoteScope", wintypes.DWORD),
                            ("RemotePort", wintypes.DWORD)]

            class Rw(ctypes.Structure):
                _fields_ = [("EnableCollection", ctypes.c_ubyte)]

            class Rod(ctypes.Structure):                 # TCP_ESTATS_DATA_ROD_v0
                _fields_ = [("DataBytesOut", ctypes.c_uint64), ("DataSegsOut", ctypes.c_uint64),
                            ("DataBytesIn", ctypes.c_uint64), ("DataSegsIn", ctypes.c_uint64),
                            ("SegsOut", ctypes.c_uint64), ("SegsIn", ctypes.c_uint64),
                            ("SoftErrors", wintypes.ULONG), ("SoftErrorReason", wintypes.ULONG),
                            ("SndUna", wintypes.ULONG), ("SndNxt", wintypes.ULONG), ("SndMax", wintypes.ULONG),
                            ("ThruBytesAcked", ctypes.c_uint64), ("RcvNxt", wintypes.ULONG),
                            ("ThruBytesReceived", ctypes.c_uint64)]
            self.Row4, self.Row6, self.Rw, self.Rod = Row4, Row6, Rw, Rod
            self.api = ctypes.windll.iphlpapi

    def available(self):
        return system.IS_WINDOWS and system.is_admin()

    def _table(self, af):
        ct = self.ct
        size = self.wt.DWORD(0)
        self.api.GetExtendedTcpTable(None, ct.byref(size), False, af, TCP_TABLE_OWNER_PID_ALL, 0)
        buf = ct.create_string_buffer(size.value)
        rc = self.api.GetExtendedTcpTable(buf, ct.byref(size), False, af, TCP_TABLE_OWNER_PID_ALL, 0)
        if rc != 0:
            raise OSError(f"GetExtendedTcpTable returned {rc}")
        return buf.raw

    def _connections(self, pids):
        """[(key, function_suffix, row)] for the established connections that belong to pids."""
        out = []
        for st, la, lp, ra, rp, pid in parse_tcp4_table(self._table(AF_INET)):
            if pid in pids and st == TCP_STATE_ESTABLISHED:
                out.append((("4", la, lp, ra, rp, pid), "", self.Row4(st, la, lp, ra, rp)))
        for la, ls, lp, ra, rs, rp, st, pid in parse_tcp6_table(self._table(AF_INET6)):
            if pid in pids and st == TCP_STATE_ESTABLISHED:
                row = self.Row6(st, (self.ct.c_ubyte * 16).from_buffer_copy(la), ls, lp,
                                (self.ct.c_ubyte * 16).from_buffer_copy(ra), rs, rp)
                out.append((("6", la, lp, ra, rp, pid), "6", row))
        return out

    def rate(self, pids, now):
        """Bytes/s for these processes, or None when it cannot be measured."""
        if not self.available():
            self.last_error = "needs Administrator" if system.IS_WINDOWS else "Windows only"
            return None
        try:
            ct = self.ct
            total = 0
            seen = set()
            for key, suffix, row in self._connections(set(pids)):
                seen.add(key)
                if key not in self._prev:                # switch statistics on for this connection
                    rw = self.Rw(1)
                    set_fn = getattr(self.api, f"SetPerTcp{suffix}ConnectionEStats")
                    rc = set_fn(ct.byref(row), TCP_ESTATS_DATA, ct.byref(rw), 0, ct.sizeof(rw), 0)
                    if rc != 0:
                        self.last_error = f"SetPerTcpConnectionEStats returned {rc}"
                        continue
                    self._prev[key] = 0
                rod = self.Rod()
                get_fn = getattr(self.api, f"GetPerTcp{suffix}ConnectionEStats")
                rc = get_fn(ct.byref(row), TCP_ESTATS_DATA, None, 0, 0, None, 0, 0,
                            ct.byref(rod), 0, ct.sizeof(rod))
                if rc != 0:
                    continue
                now_bytes = rod.DataBytesIn + rod.DataBytesOut
                total += max(0, now_bytes - self._prev[key])
                self._prev[key] = now_bytes
            for gone in set(self._prev) - seen:
                self._prev.pop(gone, None)
            dt = (now - self._prev_t) if self._prev_t else None
            self._prev_t = now
            self.last_error = ""
            return total / dt if dt and dt > 0.2 else 0.0
        except Exception as e:
            self.last_error = str(e)[:80]
            C.log_error(f"per-app network failed: {e}")
            return None


# ---------------------------------------------------------------- watching one app
class AppSampler:
    """Activity of every process with this program name, plus everything they started."""

    def __init__(self, name, clock=time.time, estats=None):
        self.name = name.lower()
        self.clock = clock
        self.estats = estats
        self.procs = {}
        self.prev_io = {}
        self.prev_t = None
        self.cores = psutil.cpu_count() or 1

    def _tree(self):
        by_parent, found = {}, set()
        for p in psutil.process_iter(["pid", "ppid", "name"]):
            info = p.info
            by_parent.setdefault(info.get("ppid"), []).append(info["pid"])
            if (info.get("name") or "").lower() == self.name:
                found.add(info["pid"])
        stack = list(found)
        while stack:
            for child in by_parent.get(stack.pop(), []):
                if child not in found:
                    found.add(child)
                    stack.append(child)
        return found

    def sample(self):
        now = self.clock()
        pids = self._tree()
        if not pids:
            self.procs.clear()
            self.prev_io.clear()
            self.prev_t = now
            return {"running": False, "cpu": 0.0, "io": 0.0, "net": None, "count": 0, "unreadable": 0}
        cpu, unreadable, io_now = 0.0, 0, {}
        for pid in pids:
            p = self.procs.get(pid)
            try:
                if p is None:
                    p = self.procs[pid] = psutil.Process(pid)
                    p.cpu_percent(None)                       # the first call only starts the measurement
                cpu += p.cpu_percent(None)
                c = p.io_counters()
                io_now[pid] = c.read_bytes + c.write_bytes
            except psutil.NoSuchProcess:
                continue
            except (psutil.AccessDenied, AttributeError, OSError):
                unreadable += 1
        for gone in set(self.procs) - pids:
            self.procs.pop(gone, None)
        dt = (now - self.prev_t) if self.prev_t else None
        io_rate = 0.0
        if dt and dt > 0.2:
            io_rate = sum(max(0, b - self.prev_io[pid]) / dt for pid, b in io_now.items() if pid in self.prev_io)
        self.prev_io, self.prev_t = io_now, now
        net = self.estats.rate(pids, now) if self.estats is not None else None
        return {"running": True, "cpu": cpu / self.cores, "io": io_rate, "net": net,
                "count": len(pids), "unreadable": unreadable}


class WatchJob:
    """Waits until the watched app has closed, or has been idle for long enough."""

    def __init__(self, cfg, sampler, clock=time.time):
        self.cfg = dict(cfg)
        self.app = cfg["app"]
        self.sampler = sampler
        self.clock = clock
        self.started = clock()
        self.state = "waiting"           # waiting | done | timeout
        self.reason = ""                 # closed | idle
        self.idle_since = None
        self.missing_since = None
        self.next_sample = 0.0
        self.last = None
        self.hist = {k: collections.deque(maxlen=60) for k in ("cpu", "io", "net")}

    def is_active(self, s):
        c = self.cfg
        if c["use_cpu"] and s["cpu"] > c["cpu_limit"]:
            return True
        if c["use_io"] and s["io"] / 1048576.0 > c["io_limit_mb"]:
            return True
        if c["use_net"] and s["net"] is not None and s["net"] / 1024.0 > c["net_limit_kb"]:
            return True
        return False

    def idle_left(self):
        """Seconds until the app counts as idle, or None while it is busy."""
        if self.idle_since is None:
            return None
        return max(0, self.cfg["idle_minutes"] * 60 - (self.clock() - self.idle_since))

    def tick(self, interval=2.0):
        if self.state != "waiting":
            return
        now = self.clock()
        c = self.cfg
        if c["max_hours"] and now - self.started >= c["max_hours"] * 3600:
            self.state = "timeout"
            return
        if now < self.next_sample:
            return
        self.next_sample = now + interval
        s = self.sampler.sample()
        self.last = s
        self.hist["cpu"].append(s["cpu"])
        self.hist["io"].append(s["io"] / 1048576.0)
        self.hist["net"].append((s["net"] or 0.0) / 1024.0)
        if not s["running"]:
            self.idle_since = None
            self.missing_since = self.missing_since or now
            if c["rule_close"] and now - self.missing_since >= 6:
                self.state, self.reason = "done", "closed"
            return
        self.missing_since = None
        if c["rule_idle"]:
            if self.is_active(s):
                self.idle_since = None
            else:
                self.idle_since = self.idle_since or now
                if now - self.idle_since >= c["idle_minutes"] * 60:
                    self.state, self.reason = "done", "idle"
