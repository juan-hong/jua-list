"""jua-list 바탕화면 위젯. 등록한 .md 체크리스트를 보여주고 고치고, Claude에게 일을 맡김."""
import ctypes
import os
import re
import sys
import time
import traceback
import tkinter as tk
from ctypes import wintypes
from tkinter import ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jua_core as core  # noqa: E402
from jua_core import JuaError, log  # noqa: E402
from jua_i18n import _  # noqa: E402

BG, CARD, LINE = "#18191e", "#23252d", "#2e3039"
FG, DIM, ACC, GOOD, BAD, WARN = "#e6e7ea", "#7d808a", "#8ab4f8", "#7dd3a0", "#f28b82", "#f6c177"
FAMILY = "Malgun Gothic"
RADIUS = 14
PLACEHOLDER = _("할 일 추가 후 Enter  (앞에 @claude 붙이면 Claude에게 맡김)")

# ---------- Win32 ----------
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
gdi32 = ctypes.windll.gdi32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

H = wintypes.HWND
for _n, _a, _r in [
    ("FindWindowW", [wintypes.LPCWSTR, wintypes.LPCWSTR], H),
    ("FindWindowExW", [H, H, wintypes.LPCWSTR, wintypes.LPCWSTR], H),
    ("SetParent", [H, H], H),
    ("GetAncestor", [H, wintypes.UINT], H),
    ("MoveWindow", [H, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.BOOL], wintypes.BOOL),
    ("ScreenToClient", [H, ctypes.POINTER(wintypes.POINT)], wintypes.BOOL),
    ("GetCursorPos", [ctypes.POINTER(wintypes.POINT)], wintypes.BOOL),
    ("SetWindowPos", [H, H, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT], wintypes.BOOL),
    ("SendMessageTimeoutW", [H, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM, wintypes.UINT,
                             wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)], wintypes.LPARAM),
    ("GetWindowLongPtrW", [H, ctypes.c_int], ctypes.c_ssize_t),
    ("SetWindowLongPtrW", [H, ctypes.c_int, ctypes.c_ssize_t], ctypes.c_ssize_t),
    ("GetForegroundWindow", [], H),
    ("SetLayeredWindowAttributes", [H, wintypes.DWORD, ctypes.c_ubyte, wintypes.DWORD], wintypes.BOOL),
    ("SetWindowRgn", [H, wintypes.HRGN, wintypes.BOOL], ctypes.c_int),
]:
    _f = getattr(user32, _n)
    _f.argtypes, _f.restype = _a, _r
gdi32.CreateRoundRectRgn.restype = wintypes.HRGN
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, H, wintypes.LPARAM)
user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]

GWL_STYLE, WS_CHILD, WS_POPUP = -16, 0x40000000, 0x80000000
GWL_EXSTYLE, WS_EX_LAYERED, LWA_ALPHA = -20, 0x80000, 0x2
SWP_NOMOVE, SWP_NOSIZE, SWP_NOACTIVATE = 0x2, 0x1, 0x10


def desktop_host():
    """아이콘 층(SHELLDLL_DefView)을 품은 창 찾음. 24H2는 Progman, 예전은 WorkerW."""
    progman = user32.FindWindowW("Progman", None)
    if not progman:
        return None
    res = ctypes.c_size_t()
    # WorkerW 만들라고 찌름
    user32.SendMessageTimeoutW(progman, 0x052C, 0xD, 0x1, 0, 1000, ctypes.byref(res))
    if user32.FindWindowExW(progman, None, "SHELLDLL_DefView", None):
        return progman
    found = []

    @WNDENUMPROC
    def cb(h, _):
        if user32.FindWindowExW(h, None, "SHELLDLL_DefView", None):
            found.append(h)
            return False
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else None


def cursor():
    p = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def rr_points(x1, y1, x2, y2, r):
    # smooth 폴리곤으로 둥근 사각형
    return [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2,
            x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]


# ---------- 위젯 ----------
class App:
    def __init__(self):
        self.quit = False
        self.editing = False
        self.moving = False
        self.undo = None
        self._drag = None
        self.runs = {}  # id -> 실행 정보
        try:
            self.cfg = core.load_cfg()
        except JuaError as e:
            log(str(e))
            self.cfg = core._merge(core.DEFAULT_CFG, {})
        self.cfg_mtime = core.cfg_mtime()
        self.docs = []
        self.load_docs()
        self.tab = min(int(self.cfg.get("tab", 0)), max(len(self.docs) - 1, 0))

        r = self.root = tk.Tk()
        r.title("jua-list")
        r.overrideredirect(True)
        r.configure(bg=BG)
        r.report_callback_exception = lambda *a: log("".join(traceback.format_exception(*a)))
        self.fonts()
        self._style()
        self._build()
        r.geometry(f"{self.cfg['w']}x{self.cfg['h']}+{self.cfg['x']}+{self.cfg['y']}")
        r.update_idletasks()
        self.hwnd = user32.GetAncestor(r.winfo_id(), 2)
        self.host = None
        self.cur_rect = None
        self.pin()
        self.render()
        r.after(1000, self.poll)

    def fonts(self):
        s = max(8, min(16, int(self.cfg.get("font_size", 10))))
        self.f = {"n": (FAMILY, s), "done": (FAMILY, s, "overstrike"), "b": (FAMILY, s, "bold"),
                  "s": (FAMILY, max(7, s - 1)), "xs": (FAMILY, max(7, s - 2)), "tab": (FAMILY, s + 1, "bold")}
        self.box = int(s * 1.7)

    # --- 설정·파일 ---
    def patch(self, fn):
        """설정 일부만 고쳐 저장. 남(Claude)이 고친 키는 안 날림."""
        try:
            self.cfg = core.update_cfg(fn)
            self.cfg_mtime = core.cfg_mtime()
        except JuaError as e:
            self.toast(str(e), BAD)

    def load_docs(self):
        self.docs = []
        for e in core.entries(self.cfg):
            d = core.Doc(e["path"], e["name"], e["cwd"])
            d.load()
            self.docs.append(d)

    def doc(self):
        return self.docs[self.tab] if self.docs else None

    # --- 창 위치 ---
    def pin(self):
        if self.cfg.get("pin") == "desktop":
            host = desktop_host()
            if host:
                style = user32.GetWindowLongPtrW(self.hwnd, GWL_STYLE)
                user32.SetWindowLongPtrW(self.hwnd, GWL_STYLE, (style | WS_CHILD) & ~WS_POPUP)
                user32.SetParent(self.hwnd, host)
                # 24H2 Progman은 레이어드 자식만 그려줌
                ex = user32.GetWindowLongPtrW(self.hwnd, GWL_EXSTYLE)
                user32.SetWindowLongPtrW(self.hwnd, GWL_EXSTYLE, ex | WS_EX_LAYERED)
                self.host = host
            else:
                log(_("바탕화면 창 못 찾음. bottom 모드로 대체"))
        self.apply_alpha()
        self.place(self.cfg["x"], self.cfg["y"], self.cfg["w"], self.cfg["h"])

    def apply_alpha(self):
        a = max(60, min(255, int(self.cfg.get("alpha", 255))))
        if self.host:
            user32.SetLayeredWindowAttributes(self.hwnd, 0, a, LWA_ALPHA)
        else:
            self.root.attributes("-alpha", a / 255)

    def place(self, x, y, w, h):
        cx, cy = x, y
        if self.host:
            p = wintypes.POINT(x, y)
            user32.ScreenToClient(self.host, ctypes.byref(p))
            cx, cy = p.x, p.y
        user32.MoveWindow(self.hwnd, cx, cy, w, h, True)
        if not self.cur_rect or self.cur_rect[2:] != (w, h):
            # 영역 넘기면 창이 소유함. 따로 해제 안 함
            user32.SetWindowRgn(self.hwnd, gdi32.CreateRoundRectRgn(0, 0, w + 1, h + 1, RADIUS * 2, RADIUS * 2), True)
        self.cur_rect = (x, y, w, h)

    def to_bottom(self):
        if not self.host and user32.GetForegroundWindow() != self.hwnd:
            user32.SetWindowPos(self.hwnd, H(1), 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

    def drag_start(self, _e, mode):
        if self.moving:
            self._drag = (mode, cursor(), self.cur_rect)

    def drag_move(self, _e):
        if not self._drag:
            return
        mode, (sx, sy), (x0, y0, w0, h0) = self._drag
        x, y = cursor()
        dx, dy = x - sx, y - sy
        if mode == "move":
            self.place(x0 + dx, y0 + dy, w0, h0)
        else:
            self.place(x0, y0, max(280, w0 + dx), max(240, h0 + dy))

    def drag_end(self, _e):
        if self._drag:
            resized = self._drag[0] == "size"
            self._drag = None
            if resized:
                self.render()

    def set_moving(self, on):
        self.moving = on
        if on:
            self.root.configure(bg=ACC)
            self.frame.pack_configure(padx=2, pady=2)
            self.banner.pack(after=self.head, fill="x", padx=12, pady=(0, 6))
            self.grip.place(relx=1.0, rely=1.0, anchor="se", x=-3, y=-3)
            self.grip.lift()
            self.head.configure(cursor="fleur")
        else:
            self.root.configure(bg=BG)
            self.frame.pack_configure(padx=0, pady=0)
            self.banner.pack_forget()
            self.grip.place_forget()
            self.head.configure(cursor="")
            x, y, w, h = self.cur_rect
            self.patch(lambda c: c.update(x=x, y=y, w=w, h=h))
            self.render()

    # --- UI 뼈대 ---
    def _style(self):
        s = ttk.Style(self.root)
        s.theme_use("clam")
        s.configure("TCombobox", fieldbackground=CARD, background=CARD, foreground=DIM, arrowcolor=DIM,
                    bordercolor=CARD, lightcolor=CARD, darkcolor=CARD, selectbackground=CARD,
                    selectforeground=FG, padding=(6, 3))
        s.map("TCombobox", fieldbackground=[("readonly", CARD)], foreground=[("readonly", DIM)],
              selectbackground=[("readonly", CARD)], selectforeground=[("readonly", DIM)])
        self.root.option_add("*TCombobox*Listbox.background", CARD)
        self.root.option_add("*TCombobox*Listbox.foreground", FG)
        self.root.option_add("*TCombobox*Listbox.selectBackground", ACC)
        self.root.option_add("*TCombobox*Listbox.font", self.f["s"])

    def _drag_bind(self, w, mode):
        w.bind("<ButtonPress-1>", lambda e: self.drag_start(e, mode), add="+")
        w.bind("<B1-Motion>", self.drag_move, add="+")
        w.bind("<ButtonRelease-1>", self.drag_end, add="+")

    def _hover_color(self, w, normal, hot):
        w.bind("<Enter>", lambda e: w.configure(fg=hot), add="+")
        w.bind("<Leave>", lambda e: w.configure(fg=normal), add="+")

    def _build(self):
        f = self.f
        fr = self.frame = tk.Frame(self.root, bg=BG)
        fr.pack(fill="both", expand=True)

        head = self.head = tk.Frame(fr, bg=BG)
        head.pack(fill="x", padx=12, pady=(10, 6))
        self._drag_bind(head, "move")
        self.tabbar = tk.Frame(head, bg=BG)
        self.tabbar.pack(side="left", fill="x", expand=True)
        self._drag_bind(self.tabbar, "move")
        self.menu_btn = tk.Label(head, text="⋯", bg=BG, fg=DIM, font=f["tab"], cursor="hand2", padx=6)
        self.menu_btn.pack(side="right")
        self.menu_btn.bind("<Button-1>", lambda e: self.menu())
        self._hover_color(self.menu_btn, DIM, FG)
        self.run_lbl = tk.Label(head, text="", bg=BG, fg=ACC, font=f["s"])
        self.run_lbl.pack(side="right", padx=4)

        bn = self.banner = tk.Frame(fr, bg=CARD, cursor="fleur")
        bl = tk.Label(bn, text=_("끌어서 옮기기 · ◢ 끌어서 크기 조절"), bg=CARD, fg=FG, font=f["s"], cursor="fleur")
        bl.pack(side="left", padx=10, pady=6)
        ok = tk.Label(bn, text=_("완료"), bg=ACC, fg=BG, font=f["b"], cursor="hand2", padx=12, pady=2)
        ok.pack(side="right", padx=6, pady=4)
        ok.bind("<Button-1>", lambda e: self.set_moving(False))
        self._drag_bind(bn, "move")
        self._drag_bind(bl, "move")

        tk.Frame(fr, bg=LINE, height=1).pack(fill="x", padx=12)
        self.toast_lbl = tk.Label(fr, text="", bg=BG, fg=BAD, font=f["s"], anchor="w", justify="left")

        foot = tk.Frame(fr, bg=BG)
        foot.pack(side="bottom", fill="x", padx=12, pady=(6, 12))
        bar = tk.Frame(foot, bg=CARD)
        bar.pack(fill="x")
        tk.Label(bar, text="+", bg=CARD, fg=ACC, font=f["b"]).pack(side="left", padx=(10, 4))
        self.sec_var = tk.StringVar()
        self.sec_box = ttk.Combobox(bar, textvariable=self.sec_var, state="readonly", font=f["s"], width=10)
        self.sec_box.pack(side="right", padx=(4, 4), pady=4)
        self.entry = tk.Entry(bar, bg=CARD, fg=DIM, insertbackground=FG, relief="flat", font=f["s"],
                              highlightthickness=0, bd=0)
        self.entry.pack(side="left", fill="x", expand=True, ipady=6)
        self.entry.insert(0, PLACEHOLDER)
        self.entry_ph = True
        self.entry.bind("<FocusIn>", self._ph_in)
        self.entry.bind("<FocusOut>", self._ph_out)
        self.entry.bind("<Return>", lambda e: self.add())

        wrap = tk.Frame(fr, bg=BG)
        wrap.pack(fill="both", expand=True, padx=2, pady=(2, 0))
        self.canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0, bd=0, yscrollincrement=20)
        self.canvas.pack(fill="both", expand=True)
        self.body = tk.Frame(self.canvas, bg=BG)
        self.body_id = self.canvas.create_window(0, 0, window=self.body, anchor="nw")
        self.body.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.body_id, width=e.width))
        self.root.bind_all("<MouseWheel>", self.wheel)

        self.grip = tk.Label(fr, text="◢", bg=BG, fg=ACC, font=f["b"], cursor="size_nw_se")
        self._drag_bind(self.grip, "size")

    def toast(self, text, color=BAD, ms=5000):
        self.toast_lbl.configure(text=text, fg=color)
        self.toast_lbl.pack(after=self.head, fill="x", padx=14, pady=(0, 4))
        if getattr(self, "_toast_job", None):
            self.root.after_cancel(self._toast_job)
        self._toast_job = self.root.after(ms, self.toast_lbl.pack_forget)

    def _ph_in(self, _e):
        if self.entry_ph:
            self.entry.delete(0, "end")
            self.entry.configure(fg=FG, font=self.f["n"])
            self.entry_ph = False

    def _ph_out(self, _e):
        if not self.entry.get():
            self.entry.insert(0, PLACEHOLDER)
            self.entry.configure(fg=DIM, font=self.f["s"])
            self.entry_ph = True

    def wheel(self, e):
        if self.body.winfo_reqheight() > self.canvas.winfo_height():
            self.canvas.yview_scroll(-int(e.delta / 120), "units")

    # --- 그리기 ---
    def draw_box(self, cv, status, bg=BG):
        cv.delete("all")
        cv.configure(bg=bg)
        s = self.box
        pts = rr_points(1, 1, s - 1, s - 1, max(3, s // 4))
        mid = s / 2
        if status == "done":
            cv.create_polygon(pts, smooth=True, fill=GOOD, outline=GOOD)
            cv.create_line(s * .27, s * .52, s * .44, s * .69, s * .75, s * .34, fill=BG, width=2,
                           capstyle="round", joinstyle="round")
        elif status == "doing":
            cv.create_polygon(pts, smooth=True, fill="", outline=ACC, width=1.5)
            r = s * .17
            cv.create_oval(mid - r, mid - r, mid + r, mid + r, fill=ACC, outline=ACC)
        elif status == "review":
            cv.create_polygon(pts, smooth=True, fill=WARN, outline=WARN)
            cv.create_text(mid, mid, text="?", fill=BG, font=(FAMILY, max(7, int(s * .5)), "bold"))
        elif status == "blocked":
            cv.create_polygon(pts, smooth=True, fill=BAD, outline=BAD)
            cv.create_text(mid, mid, text="!", fill=BG, font=(FAMILY, max(7, int(s * .5)), "bold"))
        else:
            cv.create_polygon(pts, smooth=True, fill="", outline=DIM, width=1.5)

    def render(self):
        f = self.f
        top = self.canvas.yview()[0]
        for c in self.tabbar.winfo_children():
            c.destroy()
        for i, d in enumerate(self.docs):
            on = i == self.tab
            waiting = sum(t["status"] in ("review", "blocked") for t in d.items())
            b = tk.Label(self.tabbar, text=d.name + (f" •{waiting}" if waiting else ""), bg=BG,
                         fg=FG if on else DIM, font=f["tab"] if on else f["n"], cursor="hand2", padx=4)
            b.pack(side="left", padx=(0, 6))
            b.bind("<Button-1>", lambda e, i=i: self.switch(i))
            if not on:
                self._hover_color(b, DIM, FG)
        self.run_lbl.configure(text=_("● Claude 작업 {0}").format(len(self.runs)) if self.runs else "")

        for c in self.body.winfo_children():
            c.destroy()
        doc = self.doc()
        if not doc:
            self._msg(_("등록된 목록 없음. jua new <경로> 또는 ⋯ → 설정 파일 열기"))
            self.sec_box["values"] = []
            return
        if doc.error:
            self._msg(f"⚠ {doc.error}\n{doc.path}")
        secs = doc.sections()
        width = self.canvas.winfo_width()
        width = width if width > 50 else self.cfg["w"] - 10
        wrap = max(120, width - self.box - 130)
        collapsed = set(self.cfg.get("collapsed", {}).get(doc.path, []))
        shown = False
        for s in secs:
            if s["items"]:
                shown = True
                self._section(doc, s, s["title"] in collapsed, wrap)
        if not shown and not doc.error:
            self._msg(_("할 일이 없음. 아래 칸에서 추가"))

        self.sec_list = [(s["head"], s["title"]) for s in secs if s["head"] >= 0]
        names = [t for _, t in self.sec_list] or [_("(파일 끝)")]
        self.sec_box["values"] = names
        if self.sec_var.get() not in names:
            first = next((s["title"] for s in secs if s["items"] and s["head"] >= 0), names[0])
            self.sec_var.set(first)
        self.root.update_idletasks()
        self.canvas.yview_moveto(top)

    def _msg(self, text):
        tk.Label(self.body, text=text, bg=BG, fg=DIM, font=self.f["s"], justify="left").pack(
            anchor="w", padx=14, pady=12)

    def _section(self, doc, s, collapsed, wrap):
        f = self.f
        title = s["title"] or doc.name
        total = len(s["items"])
        done = sum(t["status"] == "done" for t in s["items"])
        hdr = tk.Frame(self.body, bg=BG, cursor="hand2")
        hdr.pack(fill="x", padx=12, pady=(14, 0))
        a = tk.Label(hdr, text="▸" if collapsed else "▾", bg=BG, fg=DIM, font=f["s"], width=2, anchor="w")
        a.pack(side="left")
        t = tk.Label(hdr, text=title, bg=BG, fg=FG, font=f["b"], anchor="w")
        t.pack(side="left")
        c = tk.Label(hdr, text=f"{done}/{total}", bg=BG, fg=GOOD if done == total else DIM, font=f["s"])
        c.pack(side="right")
        for w in (hdr, a, t, c):
            w.bind("<Button-1>", lambda e, k=s["title"]: self.toggle_section(doc, k))

        bar = tk.Canvas(self.body, height=3, bg=LINE, highlightthickness=0, bd=0)
        bar.pack(fill="x", padx=12, pady=(5, 6))
        ratio = done / total
        bar.bind("<Configure>", lambda e, cv=bar: (cv.delete("all"), cv.create_rectangle(
            0, 0, e.width * ratio, 3, width=0, fill=GOOD if ratio == 1 else ACC)))
        if collapsed:
            return
        hide = self.cfg.get("hide_done")
        for task in s["items"]:
            if not (hide and task["status"] == "done"):
                self._row(doc, task, wrap)
        add = tk.Label(self.body, text=_("+ 추가"), bg=BG, fg=DIM, font=f["s"], cursor="hand2", anchor="w")
        add.pack(fill="x", padx=(16 + self.box + 8, 12), pady=(2, 0))
        add.bind("<Button-1>", lambda e: self.inline_add(doc, s, add))
        self._hover_color(add, DIM, ACC)

    def _row(self, doc, t, wrap):
        f = self.f
        ind = t["indent"] * 20
        st = t["status"]
        running = t["id"] in self.runs
        outer = tk.Frame(self.body, bg=BG)
        outer.pack(fill="x", padx=(10 + ind, 10), pady=1)
        row = tk.Frame(outer, bg=BG)
        row.pack(fill="x")
        cb = tk.Canvas(row, width=self.box, height=self.box, bg=BG, highlightthickness=0, bd=0, cursor="hand2")
        self.draw_box(cb, st)
        cb.pack(side="left", anchor="n", padx=(6, 8), pady=(4, 4))

        btns = tk.Frame(row, bg=BG)
        btns.pack(side="right", anchor="n", pady=(2, 0))
        bdefs = []
        if t["claude"]:
            bdefs.append(("■" if running else "▶", "stop" if running else "run", BAD if running else ACC))
        bdefs += [("@", "assign", ACC), ("✎", "edit", ACC), ("✕", "delete", BAD)]
        blabels = []
        for txt, kind, hot in bdefs:
            b = tk.Label(btns, text=txt, bg=BG, fg=BG, font=f["n"], cursor="hand2", padx=4)
            b.pack(side="left")
            blabels.append((b, kind, hot))

        mid = tk.Frame(row, bg=BG)
        mid.pack(side="left", fill="x", expand=True, anchor="w")
        text = re.sub(r"\*\*|`", "", t["text"])
        done = st == "done"
        lbl = tk.Label(mid, text=text, bg=BG, fg=DIM if done else FG, font=f["done"] if done else f["n"],
                       justify="left", anchor="w", wraplength=wrap - ind, cursor="hand2")
        lbl.pack(side="top", fill="x", anchor="w", pady=(3, 1))
        parts = [outer, row, cb, btns, mid, lbl] + [b for b, _, _ in blabels]
        chips = tk.Frame(mid, bg=BG)
        if t["claude"] or st in ("doing", "review", "blocked"):
            chips.pack(side="top", anchor="w", pady=(0, 2))
            parts.append(chips)
            if t["claude"]:
                parts.append(self._chip(chips, "Claude", ACC))
            if st != "todo" and st != "done":
                parts.append(self._chip(chips, (_("작업 중") if running else core.STATUS_KO[st]),
                                        {"doing": ACC, "review": WARN, "blocked": BAD}[st]))
        if t["result"]:
            res = tk.Label(mid, text="↳ " + t["result"], bg=BG, fg=DIM, font=f["xs"], justify="left", anchor="w",
                           wraplength=wrap - ind)
            res.pack(side="top", fill="x", anchor="w", pady=(0, 3))
            parts.append(res)

        hover = {"on": False}
        rp = str(outer)

        def show(on):
            if hover["on"] == on:
                return
            hover["on"] = on
            bg = CARD if on else BG
            for w in parts:
                if isinstance(w, tk.Canvas):
                    continue
                if w in [x for x, _, _ in blabels]:
                    w.configure(bg=bg, fg=DIM if on else bg)
                else:
                    w.configure(bg=bg)
            self.draw_box(cb, st, bg)

        def leave(_e):
            w = self.root.winfo_containing(*cursor())
            if w is None or not (str(w) == rp or str(w).startswith(rp + ".")):
                show(False)

        for w in parts:
            w.bind("<Enter>", lambda e: show(True), add="+")
            w.bind("<Leave>", leave, add="+")
            w.bind("<Button-3>", lambda e: self.item_menu(doc, t, row, mid, lbl, btns))
        for b, kind, hot in blabels:
            b.bind("<Enter>", lambda e, b=b, hot=hot: b.configure(fg=hot), add="+")
            b.bind("<Leave>", lambda e, b=b: hover["on"] and b.configure(fg=DIM), add="+")
            # 숨은 상태에선 안 눌리게
            b.bind("<Button-1>", lambda e, kind=kind: hover["on"] and self.button(kind, doc, t, row, mid, lbl, btns))
        cb.bind("<Button-1>", lambda e: self.click_box(doc, t))
        lbl.bind("<Button-1>", lambda e: self.click_box(doc, t))

    def _chip(self, parent, text, color):
        c = tk.Label(parent, text=text, bg=BG, fg=color, font=self.f["xs"], padx=0)
        c.pack(side="left", padx=(0, 8))
        return c

    # --- 동작 ---
    def safe(self, fn, *a):
        try:
            return fn(*a)
        except (JuaError, OSError) as e:
            self.toast(str(e))
            return None

    def click_box(self, doc, t):
        nxt = {"todo": "done", "done": "todo", "review": "done", "blocked": "todo"}.get(t["status"])
        if nxt is None:
            self.toast(_("Claude가 작업 중. ⋯ 버튼 대신 ■로 멈출 수 있음"), ACC)
            return
        self.safe(doc.set_status, t, nxt)
        self.render()

    def button(self, kind, doc, t, row, mid, lbl, btns):
        if kind == "run":
            self.run(doc, t)
        elif kind == "stop":
            self.stop(t["id"])
        elif kind == "assign":
            self.safe(doc.set_claude, t, not t["claude"])
            self.render()
        elif kind == "edit":
            self.start_edit(doc, t, row, mid, lbl, btns)
        elif kind == "delete":
            self.delete(doc, t)

    def delete(self, doc, t):
        if t["id"] in self.runs:
            self.toast(_("작업 중인 항목은 먼저 ■로 멈추세요"))
            return
        r = self.safe(doc.delete, t)
        if r:
            self.undo = (doc.path, *r)
            self.toast(_("지움. ⋯ → 삭제 되돌리기"), DIM, 4000)
        self.render()

    def undo_delete(self):
        if not self.undo:
            return
        path, idx, lines = self.undo
        doc = next((d for d in self.docs if d.path == path), None)
        if doc:
            self.safe(doc.restore, idx, lines)
        self.undo = None
        self.render()

    def run(self, doc, t):
        if t["status"] == "done":
            self.toast(_("완료된 항목. 먼저 체크를 푸세요"), DIM)
            return
        r = self.safe(core.start_run, self.cfg, doc, t)
        if r:
            self.runs[r["id"]] = r
            self.toast(_("Claude 시작: {0}").format(t['text'][:30]), ACC, 3000)
        self.render()

    def stop(self, iid):
        r = self.runs.pop(iid, None)
        if r:
            core.stop_run(r)
            r["proc"].wait(5)
            doc = next((d for d in self.docs if d.path == r["path"]), None)
            if doc:
                self.safe(core.finish_run, r, doc, _("사용자가 멈춤"))
        self.render()

    def check_runs(self):
        changed = False
        for iid, r in list(self.runs.items()):
            code = r["proc"].poll()
            late = time.time() - r["start"] > r["timeout"]
            if code is None and not late:
                continue
            reason = None
            if code is None:
                core.stop_run(r)
                r["proc"].wait(5)
                reason = _("시간 초과")
            del self.runs[iid]
            doc = next((d for d in self.docs if d.path == r["path"]), None) or core.Doc(r["path"])
            self.safe(core.finish_run, r, doc, reason)
            changed = True
        return changed

    def _entry(self, parent, text=""):
        e = tk.Entry(parent, bg=CARD, fg=FG, insertbackground=FG, relief="flat", font=self.f["n"],
                     highlightthickness=1, highlightcolor=ACC, highlightbackground=LINE, bd=0)
        e.insert(0, text)
        return e

    def _inline(self, ent, on_save):
        self.editing = True
        ent.focus_set()
        ent.select_range(0, "end")

        def done(save):
            if not self.editing:
                return
            self.editing = False
            val = ent.get().strip()
            if save and val:
                on_save(val)
            self.render()

        got = {"focus": False}

        def focus_in(_e):
            got["focus"] = True

        def focus_out(_e):
            # 메뉴 닫힐 때 오는 가짜 FocusOut 무시. 진짜로 다른 데 누르면 저장
            if got["focus"]:
                done(True)

        ent.bind("<FocusIn>", focus_in)
        ent.bind("<Return>", lambda e: done(True))
        ent.bind("<Escape>", lambda e: done(False))
        ent.bind("<FocusOut>", focus_out)
        self.root.after(50, ent.focus_force)

    def start_edit(self, doc, t, row, mid, lbl, btns):
        mid.pack_forget()
        btns.pack_forget()
        ent = self._entry(row, t["text"])
        ent.pack(side="left", fill="x", expand=True, ipady=4, pady=2)
        self._inline(ent, lambda v: v != t["text"] and self.safe(doc.edit, t, v))

    def inline_add(self, doc, s, add_lbl):
        ent = self._entry(self.body)
        ent.pack(after=add_lbl, fill="x", padx=(16 + self.box + 8, 12), pady=(2, 0), ipady=4)
        add_lbl.pack_forget()
        self._inline(ent, lambda v: self.safe(doc.add, v, s["title"] or None))

    def add(self):
        text = "" if self.entry_ph else self.entry.get().strip()
        doc = self.doc()
        if not text or not doc:
            return
        title = self.sec_var.get()
        sec = title if any(n == title for _, n in getattr(self, "sec_list", [])) else None
        if self.safe(doc.add, text, sec):
            self.entry.delete(0, "end")
        self.render()

    # --- 메뉴 ---
    def _menu(self):
        return tk.Menu(self.root, tearoff=0, bg=CARD, fg=FG, activebackground=ACC, activeforeground=BG,
                       font=self.f["s"], bd=0, relief="flat")

    def item_menu(self, doc, t, row, mid, lbl, btns):
        m = self._menu()
        if t["claude"]:
            if t["id"] in self.runs:
                m.add_command(label=_("■ Claude 멈추기"), command=lambda: self.stop(t["id"]))
            else:
                m.add_command(label=_("▶ Claude 실행"), command=lambda: self.run(doc, t))
        m.add_command(label=_("Claude 맡김 해제") if t["claude"] else _("@ Claude에게 맡기기"),
                      command=lambda: self.button("assign", doc, t, row, mid, lbl, btns))
        sm = self._menu()
        for k in core.MARK:
            sm.add_command(label=core.STATUS_KO[k], command=lambda k=k: (self.safe(doc.set_status, t, k), self.render()))
        m.add_cascade(label=_("상태 바꾸기"), menu=sm)
        if t["result"]:
            m.add_command(label=_("결과 줄 지우기"), command=lambda: (self.safe(doc.set_result, t, ""), self.render()))
        m.add_separator()
        m.add_command(label=_("위로"), command=lambda: (self.safe(doc.move, t, None, -1), self.render()))
        m.add_command(label=_("아래로"), command=lambda: (self.safe(doc.move, t, None, 1), self.render()))
        mv = self._menu()
        for _, name in getattr(self, "sec_list", []):
            if name != t["section"]:
                mv.add_command(label=name, command=lambda n=name: (self.safe(doc.move, t, n), self.render()))
        m.add_cascade(label=_("섹션 옮기기"), menu=mv)
        m.add_separator()
        m.add_command(label=_("수정"), command=lambda: self.start_edit(doc, t, row, mid, lbl, btns))
        m.add_command(label=_("삭제"), command=lambda: self.delete(doc, t))
        m.tk_popup(*cursor())

    def menu(self):
        m = self._menu()
        m.add_command(label=_("완료 항목 보이기") if self.cfg.get("hide_done") else _("완료 항목 숨기기"),
                      command=lambda: self.set_cfg(hide_done=not self.cfg.get("hide_done")))
        m.add_command(label=_("창 옮기기·크기 조절"), command=lambda: self.set_moving(True))
        m.add_command(label=_("글자 크게"), command=lambda: self.set_cfg(font_size=min(16, self.cfg["font_size"] + 1)))
        m.add_command(label=_("글자 작게"), command=lambda: self.set_cfg(font_size=max(8, self.cfg["font_size"] - 1)))
        if self.undo:
            m.add_command(label=_("삭제 되돌리기"), command=self.undo_delete)
        m.add_separator()
        if self.doc():
            m.add_command(label=_("md 파일 열기"), command=lambda: os.startfile(self.doc().path))
        m.add_command(label=_("Claude 실행 기록 폴더"), command=self.open_runs)
        m.add_command(label=_("설정 파일 열기"), command=lambda: os.startfile(core.CFG_PATH))
        m.add_command(label=_("다시 읽기"), command=self.reload)
        m.add_separator()
        m.add_command(label=_("종료"), command=self.exit)
        m.tk_popup(*cursor())

    def open_runs(self):
        os.makedirs(core.RUNS_DIR, exist_ok=True)
        os.startfile(core.RUNS_DIR)

    def set_cfg(self, **kv):
        self.patch(lambda c: c.update(kv))
        self.apply_cfg()

    def apply_cfg(self):
        self.fonts()
        self.entry.configure(font=self.f["s"] if self.entry_ph else self.f["n"])
        self.apply_alpha()
        r = (self.cfg["x"], self.cfg["y"], self.cfg["w"], self.cfg["h"])
        if not self.moving and r != self.cur_rect:
            self.place(*r)
        self.render()

    def toggle_section(self, doc, title):
        def fn(c):
            col = c.setdefault("collapsed", {}).setdefault(doc.path, [])
            col.remove(title) if title in col else col.append(title)
        self.patch(fn)
        self.render()

    def switch(self, i):
        self.tab = i
        self.sec_var.set("")
        self.patch(lambda c: c.update(tab=i))
        self.canvas.yview_moveto(0)
        self.render()

    def reload(self):
        try:
            self.cfg = core.load_cfg()
        except JuaError as e:
            self.toast(str(e))
        self.cfg_mtime = core.cfg_mtime()
        self.load_docs()
        self.tab = min(self.tab, max(len(self.docs) - 1, 0))
        self.apply_cfg()

    def exit(self):
        if self.runs:
            self.toast(_("Claude 작업 {0}개 진행 중. 위젯을 꺼도 작업은 계속되지만 상태 정리는 안 됨").format(len(self.runs)), WARN)
        self.quit = True
        self.root.destroy()

    def poll(self):
        try:
            busy = self.editing or self.moving
            if core.cfg_mtime() != self.cfg_mtime:
                try:
                    new = core.load_cfg()
                    self.cfg_mtime = core.cfg_mtime()
                    files_changed = core.entries(new) != core.entries(self.cfg)
                    self.cfg = new
                    if files_changed:
                        self.load_docs()
                    self.tab = min(int(new.get("tab", self.tab)), max(len(self.docs) - 1, 0))
                    if not busy:
                        self.apply_cfg()
                except JuaError as e:
                    # 깨진 설정은 무시하고 기존 값 유지
                    self.cfg_mtime = core.cfg_mtime()
                    self.toast(str(e))
            changed = self.check_runs()
            for d in self.docs:
                if d.stat() != d.mtime:
                    d.load()
                    changed = True
            if changed and not busy:
                self.render()
            self.to_bottom()
        except Exception:
            log(traceback.format_exc())
        self.root.after(1000, self.poll)


def main():
    kernel32.CreateMutexW(None, False, "Local\\jua-list")
    if kernel32.GetLastError() == 183:  # 이미 실행 중
        return
    fails = 0
    while True:
        app = None
        try:
            app = App()
            app.root.mainloop()
        except Exception:
            log(traceback.format_exc())
        if app and app.quit:
            break
        fails = fails + 1 if not app else 0
        if fails >= 5:
            log(_("시작 계속 실패. 종료"))
            break
        # 탐색기 재시작 등으로 부모 창 날아감. 잠깐 쉬고 다시 띄움
        log(_("창이 닫힘. 다시 띄움"))
        time.sleep(3)


if __name__ == "__main__":
    main()
