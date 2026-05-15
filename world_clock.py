import json
import threading
import tkinter as tk
from datetime import datetime, time
from pathlib import Path
from tkinter import messagebox
from zoneinfo import ZoneInfo, available_timezones
import urllib.parse
import urllib.request

import customtkinter as ctk


def _load_tz_country() -> dict[str, str]:
    """timezone name → ISO-2 country code, parsed from IANA zone.tab."""
    for p in [Path("/usr/share/zoneinfo/zone.tab"),
              Path("/usr/share/zoneinfo/zone1970.tab")]:
        try:
            result = {}
            for line in p.read_text().splitlines():
                if line.startswith("#") or not line.strip():
                    continue
                parts = line.split("\t")
                if len(parts) >= 3:
                    result.setdefault(parts[2], parts[0].lower())
            if result:
                return result
        except Exception:
            continue
    return {}


_TZ_COUNTRY: dict[str, str] = _load_tz_country()

from ui.theme import (
    PRIMARY, SECONDARY, FONT_BODY, FONT_SMALL, FONT_MONO,
    PAD_SM, PAD_MD, PAD_LG, CORNER_RADIUS, BUTTON_HEIGHT, BTN_SECONDARY, BTN_SECONDARY_HOVER, BTN_TEXT,
)


class WorldClockWindow:
    """彈出視窗：輸入時間範圍，查出現在哪些時區落在該範圍，可一鍵套用定位。"""

    def __init__(self, parent, *, location_fn, on_status):
        self._location_fn = location_fn
        self._on_status = on_status
        self._results: list[dict] = []
        self._selected_idx: int | None = None

        self.win = ctk.CTkToplevel(parent)
        self.win.title("世界時區查詢")
        self.win.geometry("520x560")
        self.win.resizable(True, True)
        self.win.minsize(420, 420)
        self.win.protocol("WM_DELETE_WINDOW", self.win.destroy)

        self._build_ui()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = ctk.CTkFrame(self.win, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=PAD_MD, pady=PAD_MD)
        outer.rowconfigure(1, weight=1)
        outer.columnconfigure(0, weight=1)

        # 時間範圍區塊
        range_section = ctk.CTkFrame(outer, corner_radius=CORNER_RADIUS)
        range_section.grid(row=0, column=0, sticky="ew", pady=(0, PAD_SM))

        ctk.CTkLabel(range_section, text="時間範圍", font=FONT_SMALL,
                     text_color=SECONDARY).pack(anchor="w", padx=PAD_MD, pady=(PAD_SM, 2))

        range_row = ctk.CTkFrame(range_section, fg_color="transparent")
        range_row.pack(fill="x", padx=PAD_MD, pady=(0, PAD_SM))

        ctk.CTkLabel(range_row, text="從", font=FONT_BODY).pack(side="left")
        self._from_h = self._time_entry(range_row, "00")
        ctk.CTkLabel(range_row, text=":", font=FONT_BODY).pack(side="left")
        self._from_m = self._time_entry(range_row, "00")

        ctk.CTkLabel(range_row, text="  到", font=FONT_BODY).pack(side="left", padx=(PAD_SM, 0))
        self._to_h = self._time_entry(range_row, "02")
        ctk.CTkLabel(range_row, text=":", font=FONT_BODY).pack(side="left")
        self._to_m = self._time_entry(range_row, "00")

        ctk.CTkButton(
            range_row, text="查詢", command=self._search,
            width=60, height=BUTTON_HEIGHT, font=FONT_BODY,
        ).pack(side="left", padx=(PAD_MD, 0))

        self._count_label = ctk.CTkLabel(
            range_row, text="", font=FONT_SMALL, text_color=SECONDARY
        )
        self._count_label.pack(side="left", padx=(PAD_SM, 0))

        # 結果列表
        _list_outer = ctk.CTkFrame(outer, corner_radius=CORNER_RADIUS)
        _list_outer.grid(row=1, column=0, sticky="nsew", pady=(0, PAD_SM))
        _list_outer.rowconfigure(0, weight=1)
        _list_outer.columnconfigure(0, weight=1)

        self._listbox = tk.Listbox(
            _list_outer,
            font=FONT_MONO,
            selectmode="single",
            activestyle="none",
            relief="flat",
            bd=0,
            highlightthickness=0,
            selectbackground=PRIMARY,
            selectforeground="#FFFFFF",
        )
        _sb = tk.Scrollbar(_list_outer, orient="vertical", command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=_sb.set)
        self._listbox.grid(row=0, column=0, sticky="nsew", padx=(PAD_SM, 0), pady=PAD_SM)
        _sb.grid(row=0, column=1, sticky="ns", padx=(0, PAD_SM), pady=PAD_SM)
        self._listbox.bind("<<ListboxSelect>>", self._on_select)

        # 底部按鈕列
        btn_frame = ctk.CTkFrame(outer, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew")

        self._apply_btn = ctk.CTkButton(
            btn_frame, text="填入座標", command=self._apply,
            state="disabled", width=100, height=BUTTON_HEIGHT, font=FONT_BODY,
        )
        self._apply_btn.pack(side="left")

        self._apply_label = ctk.CTkLabel(
            btn_frame, text="", font=FONT_SMALL, text_color=SECONDARY
        )
        self._apply_label.pack(side="left", padx=(PAD_SM, 0))

        ctk.CTkButton(
            btn_frame, text="關閉", command=self.win.destroy,
            width=80, height=BUTTON_HEIGHT, font=FONT_BODY,
            fg_color=BTN_SECONDARY, hover_color=BTN_SECONDARY_HOVER, text_color=BTN_TEXT,
        ).pack(side="right")

    @staticmethod
    def _time_entry(parent, default: str) -> ctk.CTkEntry:
        e = ctk.CTkEntry(parent, width=44, height=BUTTON_HEIGHT, justify="center", font=FONT_BODY)
        e.insert(0, default)
        e.pack(side="left", padx=(4, 0))
        return e

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
        self._count_label.configure(text="查詢中…")
        self._listbox.delete(0, "end")
        self._selected_idx = None
        self._apply_btn.configure(state="disabled")
        self._apply_label.configure(text="")

        def scan():
            results = []
            for tz_name in sorted(available_timezones()):
                try:
                    now = datetime.now(ZoneInfo(tz_name))
                    t = now.time().replace(second=0, microsecond=0)
                    if not self._in_range(t, start, end):
                        continue
                    parts = tz_name.split("/")
                    city = parts[-1].replace("_", " ")
                    region = parts[0] if len(parts) > 1 else ""
                    results.append({
                        "tz": tz_name,
                        "city": city,
                        "region": region,
                        "local_time": now.strftime("%H:%M"),
                        "sort_key": now.hour * 60 + now.minute,
                    })
                except Exception:
                    continue
            results.sort(key=lambda x: x["sort_key"])

            def update_ui():
                self._results = results
                self._listbox.delete(0, "end")
                for r in results:
                    suffix = f" ({r['region']})" if r["region"] else ""
                    self._listbox.insert("end", f"{r['city']}{suffix:<30}  {r['local_time']}")
                count = len(results)
                self._count_label.configure(
                    text=f"找到 {count} 個時區" if count else "找不到符合的時區"
                )

            self.win.after(0, update_ui)

        threading.Thread(target=scan, daemon=True).start()

    def _on_select(self, _event=None):
        sel = self._listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx >= len(self._results):
            return
        self._selected_idx = idx
        r = self._results[idx]
        self._apply_btn.configure(state="normal")
        self._apply_label.configure(text=r["tz"])

    # ── 套用定位 ─────────────────────────────────────────────────────────────

    def _apply(self):
        if self._selected_idx is None:
            return
        r = self._results[self._selected_idx]

        self._apply_btn.configure(state="disabled", text="查詢中…")
        self._apply_label.configure(text="")

        def fetch():
            cc = _TZ_COUNTRY.get(r["tz"], "")
            coords = (
                self._geocode(r["city"], cc) or
                self._geocode(r["city"]) or
                self._geocode(r["tz"].split("/")[-1].replace("_", " "))
            )

            def done():
                self._apply_btn.configure(state="normal", text="填入座標")
                if coords:
                    lat, lng = coords
                    self._location_fn(str(lat), str(lng))
                    self._on_status(f"📋 已填入：{r['city']}（{r['tz']}）— 確認後按設定位置")
                    self.win.lower()
                else:
                    messagebox.showerror(
                        "座標查詢失敗",
                        f"無法取得「{r['city']}」的座標",
                        parent=self.win,
                    )

            self.win.after(0, done)

        threading.Thread(target=fetch, daemon=True).start()

    @staticmethod
    def _geocode(query: str, countrycodes: str = "") -> tuple[float, float] | None:
        try:
            params = f"q={urllib.parse.quote(query)}&format=json&limit=1"
            if countrycodes:
                params += f"&countrycodes={countrycodes}"
            url = f"https://nominatim.openstreetmap.org/search?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": "iOS-LocationScript/1.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read())
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"])
        except Exception:
            pass
        return None
