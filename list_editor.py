import tkinter as tk
from tkinter import messagebox, filedialog
import re
import json

import customtkinter as ctk

import route_planner
import gpx_to_route
from route_preview import RoutePreviewWindow
from ui.theme import (
    PRIMARY, SECONDARY, FONT_BODY, FONT_SMALL, FONT_MONO,
    PAD_SM, PAD_MD, CORNER_RADIUS, BUTTON_HEIGHT, BTN_SECONDARY, BTN_SECONDARY_HOVER, BTN_TEXT,
)


class ListEditorWindow:
    """另開 Toplevel 視窗，提供多行座標輸入與解析，套用後可在主視窗清單面板巡邏。"""

    def __init__(self, parent, *, location_fn, coord_list_items, on_apply, on_status):
        self._location_fn = location_fn
        self._coord_list_items = coord_list_items
        self._on_apply = on_apply
        self._on_status = on_status
        self._items: list = []
        self._selected_idx: int | None = None
        self._row_buttons: list[ctk.CTkButton] = []
        self._source_flowers: list | None = None  # 記錄種花路線的原始花點，供預覽用

        self.win = ctk.CTkToplevel(parent)
        self.win.title("清單編輯器")
        self.win.geometry("960x800")
        self.win.resizable(True, True)
        self.win.protocol("WM_DELETE_WINDOW", self.win.destroy)

        self._build_ui()

    def _build_ui(self):
        outer = ctk.CTkFrame(self.win, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=PAD_MD, pady=PAD_MD)
        outer.rowconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)
        outer.columnconfigure(0, weight=1)

        # ── 輸入區 ────────────────────────────────────────────────────────────
        input_section = ctk.CTkFrame(outer, corner_radius=CORNER_RADIUS)
        input_section.grid(row=0, column=0, sticky="nsew", pady=(0, PAD_SM))
        input_section.rowconfigure(2, weight=1)
        input_section.columnconfigure(0, weight=1)

        ctk.CTkLabel(input_section, text="輸入座標（每行一筆）",
                     font=FONT_SMALL, text_color=SECONDARY).grid(
            row=0, column=0, sticky="w", padx=PAD_MD, pady=(PAD_SM, 2)
        )

        hint_text = (
            "格式（每行一筆，# 開頭為註解）：\n"
            "  緯度,經度          →  25.033,121.565\n"
            "  緯度 經度          →  25.040 121.570\n"
            "  名稱 緯度 經度     →  台北車站 25.047924 121.517081"
        )
        ctk.CTkLabel(input_section, text=hint_text, font=FONT_SMALL,
                     text_color=SECONDARY, justify="left").grid(
            row=1, column=0, sticky="w", padx=PAD_MD, pady=(0, 4)
        )

        self.text_input = ctk.CTkTextbox(
            input_section, height=120, font=FONT_MONO,
        )
        self.text_input.grid(row=2, column=0, sticky="nsew", padx=PAD_MD, pady=(0, PAD_SM))

        ctrl_row = ctk.CTkFrame(input_section, fg_color="transparent")
        ctrl_row.grid(row=3, column=0, sticky="ew", padx=PAD_MD, pady=(0, PAD_SM))

        ctk.CTkLabel(ctrl_row, text="預設停留秒數：", font=FONT_BODY).pack(side="left")
        self.dwell_entry = ctk.CTkEntry(ctrl_row, width=60, height=BUTTON_HEIGHT, font=FONT_BODY)
        self.dwell_entry.insert(0, "1")
        self.dwell_entry.pack(side="left", padx=(4, 0))

        ctk.CTkButton(ctrl_row, text="✅ 解析並載入", command=self._parse_and_load,
                      height=BUTTON_HEIGHT, font=FONT_BODY).pack(side="left", padx=(PAD_MD, 0))
        ctk.CTkButton(ctrl_row, text="📂 匯入 GPX", command=self._import_gpx,
                      height=BUTTON_HEIGHT, font=FONT_BODY,
                      fg_color=BTN_SECONDARY, hover_color=BTN_SECONDARY_HOVER, text_color=BTN_TEXT).pack(side="left", padx=(PAD_SM, 0))

        # ── 解析結果區 ────────────────────────────────────────────────────────
        result_section = ctk.CTkFrame(outer, corner_radius=CORNER_RADIUS)
        result_section.grid(row=1, column=0, sticky="nsew")
        result_section.rowconfigure(1, weight=1)
        result_section.columnconfigure(0, weight=1)

        ctk.CTkLabel(result_section, text="解析結果",
                     font=FONT_SMALL, text_color=SECONDARY).grid(
            row=0, column=0, sticky="w", padx=PAD_MD, pady=(PAD_SM, 2)
        )

        list_top = ctk.CTkFrame(result_section, fg_color="transparent")
        list_top.grid(row=0, column=0, sticky="ew", padx=PAD_MD, pady=(PAD_SM, 2))

        self.count_label = ctk.CTkLabel(list_top, text="共 0 筆",
                                        font=FONT_SMALL, text_color=SECONDARY)
        self.count_label.pack(side="left")

        ctk.CTkButton(list_top, text="🌸 規劃最佳路線", command=self._plan_route,
                      height=BUTTON_HEIGHT, font=FONT_BODY,
                      fg_color=BTN_SECONDARY, hover_color=BTN_SECONDARY_HOVER, text_color=BTN_TEXT).pack(side="right", padx=(0, PAD_SM))
        ctk.CTkButton(list_top, text="🔄 外圈巡邏", command=self._orbit_route,
                      height=BUTTON_HEIGHT, font=FONT_BODY,
                      fg_color=BTN_SECONDARY, hover_color=BTN_SECONDARY_HOVER, text_color=BTN_TEXT).pack(side="right", padx=(0, PAD_SM))
        ctk.CTkButton(list_top, text="🍎 種果路線", command=self._fruit_route,
                      height=BUTTON_HEIGHT, font=FONT_BODY,
                      fg_color=BTN_SECONDARY, hover_color=BTN_SECONDARY_HOVER, text_color=BTN_TEXT).pack(side="right", padx=(0, PAD_SM))
        ctk.CTkButton(list_top, text="👁 預覽路線", command=self._preview_route,
                      height=BUTTON_HEIGHT, font=FONT_BODY,
                      fg_color=BTN_SECONDARY, hover_color=BTN_SECONDARY_HOVER, text_color=BTN_TEXT).pack(side="right", padx=(0, PAD_SM))

        speed_frame = ctk.CTkFrame(list_top, fg_color="transparent")
        speed_frame.pack(side="right", padx=(0, PAD_SM))
        ctk.CTkLabel(speed_frame, text="速度(km/h)：",
                     font=FONT_SMALL, text_color=SECONDARY).pack(side="left")
        self.plan_speed_entry = ctk.CTkEntry(speed_frame, width=48, height=BUTTON_HEIGHT, font=FONT_BODY)
        self.plan_speed_entry.insert(0, "20")
        self.plan_speed_entry.pack(side="left")

        self._result_list = ctk.CTkScrollableFrame(result_section, corner_radius=CORNER_RADIUS)
        self._result_list.grid(row=1, column=0, sticky="nsew",
                               padx=PAD_MD, pady=(0, PAD_SM))
        self._result_list.columnconfigure(0, weight=1)

        action_bar = ctk.CTkFrame(result_section, fg_color="transparent")
        action_bar.grid(row=2, column=0, sticky="ew", padx=PAD_MD, pady=(0, PAD_MD))
        ctk.CTkButton(action_bar, text="✅ 套用到主視窗", command=self._apply_to_main,
                      height=BUTTON_HEIGHT, font=FONT_BODY).pack(side="right")
        ctk.CTkButton(action_bar, text="💾 儲存 JSON", command=self._save_json,
                      height=BUTTON_HEIGHT, font=FONT_BODY,
                      fg_color=BTN_SECONDARY, hover_color=BTN_SECONDARY_HOVER,
                      text_color=BTN_TEXT).pack(side="right", padx=(0, PAD_SM))

    # ── 資料 ──────────────────────────────────────────────────────────────────

    def load_from_items(self, items: list):
        if not items:
            return
        lines = []
        for it in items:
            name = it.get("name", "")
            lat = it.get("lat", "")
            lng = it.get("lng", "")
            if name and name != f"{lat}, {lng}":
                lines.append(f"{name} {lat} {lng}")
            else:
                lines.append(f"{lat},{lng}")
        self.text_input.delete("1.0", "end")
        self.text_input.insert("1.0", "\n".join(lines))
        self.dwell_entry.delete(0, "end")
        self.dwell_entry.insert(0, str(items[0].get("dwell", 60)))
        self._parse_and_load()

    def _parse_lines(self, text: str, default_dwell: int) -> list:
        items = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r'^([-\d.]+)\s*,\s*([-\d.]+)$', line)
            if m:
                lat, lng = m.group(1), m.group(2)
                items.append({"name": f"{lat}, {lng}", "lat": lat, "lng": lng, "dwell": default_dwell})
                continue
            parts = line.split()
            if len(parts) >= 2:
                try:
                    lng = parts[-1]
                    lat = parts[-2]
                    float(lat)
                    float(lng)
                    name = " ".join(parts[:-2]) if len(parts) > 2 else f"{lat}, {lng}"
                    items.append({"name": name, "lat": lat, "lng": lng, "dwell": default_dwell})
                except ValueError:
                    pass
        return items

    def _refresh_result_list(self):
        for btn in self._row_buttons:
            btn.destroy()
        self._row_buttons.clear()
        self._selected_idx = None

        for idx, item in enumerate(self._items):
            label = f"{item['name']}  ({item['dwell']}s)"
            btn = ctk.CTkButton(
                self._result_list,
                text=label,
                font=FONT_MONO,
                anchor="w",
                fg_color="transparent",
                text_color=("black", "white"),
                hover_color=("gray85", "gray25"),
                height=28,
                command=lambda i=idx: self._select_row(i),
            )
            btn.grid(row=idx, column=0, sticky="ew", pady=1)
            self._row_buttons.append(btn)

        self.count_label.configure(text=f"共 {len(self._items)} 筆")

    def _select_row(self, idx: int):
        if self._selected_idx is not None and self._selected_idx < len(self._row_buttons):
            self._row_buttons[self._selected_idx].configure(fg_color="transparent")
        self._selected_idx = idx
        self._row_buttons[idx].configure(fg_color=(PRIMARY, PRIMARY))

    def _parse_and_load(self):
        try:
            default_dwell = max(1, int(self.dwell_entry.get().strip()))
        except ValueError:
            default_dwell = 60
        text = self.text_input.get("1.0", "end")
        self._items = self._parse_lines(text, default_dwell)
        self._refresh_result_list()

    def _import_gpx(self):
        filepath = filedialog.askopenfilename(
            title="選擇 GPX 檔案",
            filetypes=[("GPX 檔案", "*.gpx"), ("所有檔案", "*.*")],
        )
        if not filepath:
            return
        try:
            default_dwell = max(1, int(self.dwell_entry.get().strip()))
        except ValueError:
            default_dwell = 60
        try:
            points = gpx_to_route.parse_gpx(filepath)
        except Exception as e:
            messagebox.showerror("匯入失敗", str(e))
            return
        if not points:
            messagebox.showwarning("無座標", "GPX 檔案中找不到任何座標點")
            return
        self._items = gpx_to_route.to_route_json(points, dwell=default_dwell)
        self._refresh_result_list()

    def _plan_route(self):
        if len(self._items) < 1:
            messagebox.showwarning("花點不足", "請先解析至少 1 個座標")
            return

        try:
            speed_kmh = max(1.0, float(self.plan_speed_entry.get().strip()))
        except ValueError:
            speed_kmh = 20.0

        try:
            default_dwell = max(0, int(self.dwell_entry.get().strip()))
        except ValueError:
            default_dwell = 0

        flowers = [(float(it["lat"]), float(it["lng"])) for it in self._items]
        self._source_flowers = flowers  # 記下原始花點供預覽使用
        result = route_planner.flower_circles_route(flowers)
        waypoints = result["waypoints"]

        if not waypoints:
            msg = "無法產生路線"
            if result["warnings"]:
                msg += "\n\n" + "\n".join(result["warnings"])
            messagebox.showerror("規劃失敗", msg)
            return

        in_zones = result.get("in_zones", [False] * len(waypoints))
        self._items = [
            {"name": f"WP{k+1:02d}", "lat": f"{wp[0]:.8f}",
             "lng": f"{wp[1]:.8f}", "dwell": default_dwell,
             "in_zone": in_zones[k]}
            for k, wp in enumerate(waypoints)
        ]
        self._refresh_result_list()

        dist = result["total_dist"]
        speed_mps = speed_kmh / 3.6
        msg = (
            f"花點：{len(flowers)} 個\n"
            f"路線點：{len(waypoints)} 個\n"
            f"總距離：{dist:.0f} 公尺\n"
            f"預估時間：{dist/speed_mps/60:.1f} 分鐘（{speed_kmh:.0f} km/h）"
        )
        if result["warnings"]:
            msg += "\n\n" + "\n".join(result["warnings"])
        messagebox.showinfo("路線規劃完成", msg)

    def _fruit_route(self):
        if len(self._items) < 2:
            messagebox.showwarning("座標不足", "請先解析至少 2 個座標")
            return

        flowers = [(float(it["lat"]), float(it["lng"])) for it in self._items]
        self._source_flowers = flowers
        result = route_planner.fruit_route(flowers)
        route = result["route"]

        lookup = {(float(it["lat"]), float(it["lng"])): it for it in self._items}
        reordered = [lookup[pt] for pt in route if pt in lookup]

        if not reordered:
            messagebox.showerror("規劃失敗", "無法映射路線到清單")
            return

        self._items = reordered
        self._refresh_result_list()

        dist = result["total_dist"]
        try:
            speed_kmh = max(1.0, float(self.plan_speed_entry.get().strip()))
        except ValueError:
            speed_kmh = 20.0
        speed_mps = speed_kmh / 3.6
        messagebox.showinfo(
            "種果路線規劃完成",
            f"總距離：{dist:.0f} 公尺\n"
            f"預估時間：{dist/speed_mps/60:.1f} 分鐘（{speed_kmh:.0f} km/h）\n\n"
            f"建議主視窗使用「單次」巡邏模式",
        )

    def _orbit_route(self):
        if not self._items:
            messagebox.showwarning("花點不足", "請先解析至少 1 個座標")
            return

        try:
            default_dwell = max(0, int(self.dwell_entry.get().strip()))
        except ValueError:
            default_dwell = 0

        flowers = [(float(it["lat"]), float(it["lng"])) for it in self._items]
        self._source_flowers = flowers
        result = route_planner.orbit_route(flowers)
        waypoints = result["waypoints"]

        if not waypoints:
            msg = "無法產生外圈路線"
            if result["warnings"]:
                msg += "\n\n" + "\n".join(result["warnings"])
            messagebox.showerror("規劃失敗", msg)
            return

        self._items = [
            {"name": f"WP{k+1:02d}", "lat": f"{wp[0]:.8f}", "lng": f"{wp[1]:.8f}", "dwell": default_dwell}
            for k, wp in enumerate(waypoints)
        ]
        self._refresh_result_list()

        n = len(waypoints)
        dist = sum(route_planner.haversine(waypoints[i], waypoints[(i + 1) % n])
                   for i in range(n))
        try:
            speed_kmh = max(1.0, float(self.plan_speed_entry.get().strip()))
        except ValueError:
            speed_kmh = 20.0
        speed_mps = speed_kmh / 3.6
        info_msg = (
            f"已產生 {n} 個路徑點\n"
            f"安全半徑：{result['radius_used']:.1f} 公尺\n"
            f"軌道總距離：{dist:.0f} 公尺\n"
            f"預估時間：{dist/speed_mps/60:.1f} 分鐘（{speed_kmh:.0f} km/h）"
        )
        if result["warnings"]:
            info_msg += "\n\n" + "\n".join(result["warnings"])
        messagebox.showinfo("外圈巡邏路線", info_msg)

    def _preview_route(self):
        if not self._items:
            messagebox.showwarning("清單為空", "請先解析或規劃路線")
            return
        waypoints = [(float(it["lat"]), float(it["lng"])) for it in self._items]
        RoutePreviewWindow(self.win, waypoints, flowers=self._source_flowers)

    def _apply_to_main(self):
        self._coord_list_items.clear()
        self._coord_list_items.extend(self._items)
        self._on_apply()
        self._on_status(f"✅ 已套用 {len(self._coord_list_items)} 筆到主視窗")

    def _save_json(self):
        if not self._items:
            messagebox.showwarning("清單為空", "請先解析座標")
            return
        filepath = filedialog.asksaveasfilename(
            title="儲存座標清單",
            defaultextension=".json",
            filetypes=[("JSON 檔案", "*.json")],
        )
        if not filepath:
            return
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self._items, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("儲存成功", f"已儲存 {len(self._items)} 筆")
        except Exception as e:
            messagebox.showerror("儲存失敗", str(e))
