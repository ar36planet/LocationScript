import json
import threading
import tkinter as tk
from datetime import datetime, time
from tkinter import messagebox
from zoneinfo import ZoneInfo, available_timezones
import urllib.parse
import urllib.request


class WorldClockWindow:
    """彈出視窗：輸入時間範圍，查出現在哪些時區落在該範圍，可一鍵套用定位。"""

    def __init__(self, parent, *, location_fn, on_status):
        self._location_fn = location_fn
        self._on_status = on_status
        self._results: list[dict] = []

        self.win = tk.Toplevel(parent)
        self.win.title("世界時區查詢")
        self.win.geometry("500x520")
        self.win.resizable(True, True)
        self.win.minsize(420, 400)
        self.win.protocol("WM_DELETE_WINDOW", self.win.destroy)

        self._build_ui()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = tk.Frame(self.win, padx=12, pady=10)
        outer.pack(fill=tk.BOTH, expand=True)
        outer.rowconfigure(1, weight=1)
        outer.columnconfigure(0, weight=1)

        # 時間範圍列
        range_frame = tk.LabelFrame(outer, text="時間範圍", padx=8, pady=8)
        range_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        tk.Label(range_frame, text="從").pack(side=tk.LEFT)
        self._from_h = self._spinbox(range_frame, 0, 23, "00")
        tk.Label(range_frame, text=":").pack(side=tk.LEFT)
        self._from_m = self._spinbox(range_frame, 0, 59, "00")

        tk.Label(range_frame, text="  到", padx=4).pack(side=tk.LEFT)
        self._to_h = self._spinbox(range_frame, 0, 23, "02")
        tk.Label(range_frame, text=":").pack(side=tk.LEFT)
        self._to_m = self._spinbox(range_frame, 0, 59, "00")

        tk.Button(range_frame, text="查詢", command=self._search, width=6).pack(side=tk.LEFT, padx=(12, 0))

        self._count_label = tk.Label(range_frame, text="", fg="gray", font=("", 9))
        self._count_label.pack(side=tk.LEFT, padx=(8, 0))

        # 結果列表
        list_frame = tk.Frame(outer)
        list_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 8))
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.grid(row=0, column=1, sticky="ns")

        self._listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            font=("Menlo", 11),
            selectmode=tk.SINGLE,
            activestyle="none",
        )
        self._listbox.grid(row=0, column=0, sticky="nsew")
        scrollbar.config(command=self._listbox.yview)
        self._listbox.bind("<<ListboxSelect>>", self._on_select)

        # 底部按鈕列
        btn_frame = tk.Frame(outer)
        btn_frame.grid(row=2, column=0, sticky="ew")

        self._apply_btn = tk.Button(
            btn_frame, text="📍 套用定位", command=self._apply,
            state=tk.DISABLED, width=12,
        )
        self._apply_btn.pack(side=tk.LEFT)

        self._apply_label = tk.Label(btn_frame, text="", fg="gray", font=("", 9))
        self._apply_label.pack(side=tk.LEFT, padx=(8, 0))

        tk.Button(btn_frame, text="關閉", command=self.win.destroy, width=8).pack(side=tk.RIGHT)

    @staticmethod
    def _spinbox(parent, from_: int, to: int, default: str) -> tk.Spinbox:
        var = tk.StringVar(value=default)
        sb = tk.Spinbox(parent, from_=from_, to=to, width=3,
                        format="%02.0f", textvariable=var)
        sb.pack(side=tk.LEFT, padx=(4, 0))
        return sb

    # ── 查詢 ─────────────────────────────────────────────────────────────────

    def _parse_range(self) -> tuple[time, time] | None:
        try:
            return (
                time(int(self._from_h.get()), int(self._from_m.get())),
                time(int(self._to_h.get()),   int(self._to_m.get())),
            )
        except ValueError:
            return None

    @staticmethod
    def _in_range(t: time, start: time, end: time) -> bool:
        if start <= end:
            return start <= t <= end
        return t >= start or t <= end  # 跨午夜

    def _search(self):
        range_ = self._parse_range()
        if range_ is None:
            messagebox.showerror("錯誤", "時間格式無效", parent=self.win)
            return

        start, end = range_
        self._results = []

        for tz_name in sorted(available_timezones()):
            try:
                now = datetime.now(ZoneInfo(tz_name))
                t = now.time().replace(second=0, microsecond=0)
                if not self._in_range(t, start, end):
                    continue
                parts = tz_name.split("/")
                city = parts[-1].replace("_", " ")
                region = parts[0] if len(parts) > 1 else ""
                self._results.append({
                    "tz": tz_name,
                    "city": city,
                    "region": region,
                    "local_time": now.strftime("%H:%M"),
                    "sort_key": now.hour * 60 + now.minute,
                })
            except Exception:
                continue

        self._results.sort(key=lambda x: x["sort_key"])

        self._listbox.delete(0, tk.END)
        for r in self._results:
            suffix = f" ({r['region']})" if r["region"] else ""
            label = f"{r['city']}{suffix}".ljust(34) + r["local_time"]
            self._listbox.insert(tk.END, label)

        count = len(self._results)
        self._count_label.config(
            text=f"找到 {count} 個時區" if count else "找不到符合的時區"
        )
        self._apply_btn.config(state=tk.DISABLED)
        self._apply_label.config(text="")

    def _on_select(self, _event):
        sel = self._listbox.curselection()
        if not sel:
            return
        r = self._results[sel[0]]
        self._apply_btn.config(state=tk.NORMAL)
        self._apply_label.config(text=r["tz"])

    # ── 套用定位 ─────────────────────────────────────────────────────────────

    def _apply(self):
        sel = self._listbox.curselection()
        if not sel:
            return
        r = self._results[sel[0]]

        self._apply_btn.config(state=tk.DISABLED, text="查詢座標中…")
        self._apply_label.config(text="")

        def fetch():
            coords = (
                self._geocode(r["city"]) or
                self._geocode(r["tz"].split("/")[-1].replace("_", " ")) or
                self._geocode(r["tz"].replace("_", " ").replace("/", " "))
            )

            def done():
                self._apply_btn.config(text="📍 套用定位")
                if coords:
                    lat, lng = coords
                    self._location_fn(str(lat), str(lng))
                    self._on_status(f"✅ 已套用：{r['city']}（{r['tz']}）")
                    self.win.lower()
                else:
                    self._apply_btn.config(state=tk.NORMAL)
                    messagebox.showerror(
                        "座標查詢失敗",
                        f"無法取得「{r['city']}」的座標",
                        parent=self.win,
                    )

            self.win.after(0, done)

        threading.Thread(target=fetch, daemon=True).start()

    @staticmethod
    def _geocode(query: str) -> tuple[float, float] | None:
        try:
            url = (
                "https://nominatim.openstreetmap.org/search"
                f"?q={urllib.parse.quote(query)}&format=json&limit=1"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "iOS-LocationScript/1.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read())
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"])
        except Exception:
            pass
        return None
