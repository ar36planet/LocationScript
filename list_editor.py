import tkinter as tk
from tkinter import messagebox, filedialog
import re
import json
import route_planner
import gpx_to_route


class ListEditorWindow:
    """另開 Toplevel 視窗，提供多行座標輸入與解析，套用後可在主視窗清單面板巡邏。"""

    def __init__(self, parent, *, location_fn, coord_list_items, on_apply, on_status):
        """
        parent:           Tk root 視窗
        location_fn:      set_location_direct 的參照
        coord_list_items: 主視窗共用的清單物件（直接操作同一個 list）
        on_apply():       套用後呼叫（負責更新主視窗 listbox）
        on_status(text):  更新主視窗狀態列
        """
        self._location_fn = location_fn
        self._coord_list_items = coord_list_items
        self._on_apply = on_apply
        self._on_status = on_status
        self._items: list = []

        self.win = tk.Toplevel(parent)
        self.win.title("清單編輯器")
        self.win.geometry("820x440")
        self.win.resizable(True, True)
        self.win.protocol("WM_DELETE_WINDOW", self.win.destroy)

        self._build_ui()

    def _build_ui(self):
        outer = tk.Frame(self.win, padx=12, pady=10)
        outer.pack(fill=tk.BOTH, expand=True)

        input_lf = tk.LabelFrame(outer, text="輸入座標（每行一筆）", padx=8, pady=8)
        input_lf.pack(fill=tk.BOTH, expand=True)

        hint_text = (
            "格式（每行一筆，# 開頭為註解）：\n"
            "  緯度,經度          →  25.033,121.565\n"
            "  緯度 經度          →  25.040 121.570\n"
            "  名稱 緯度 經度     →  台北車站 25.047924 121.517081"
        )
        tk.Label(input_lf, text=hint_text, fg="gray", font=("Menlo", 10), justify="left").pack(anchor="w", pady=(0, 4))

        text_frame = tk.Frame(input_lf)
        text_frame.pack(fill=tk.BOTH, expand=True)
        vsb = tk.Scrollbar(text_frame)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_input = tk.Text(text_frame, height=8, yscrollcommand=vsb.set, font=("Menlo", 12))
        self.text_input.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.config(command=self.text_input.yview)

        ctrl_row = tk.Frame(input_lf)
        ctrl_row.pack(fill=tk.X, pady=(6, 0))
        tk.Label(ctrl_row, text="預設停留秒數：").pack(side=tk.LEFT)
        self.dwell_entry = tk.Entry(ctrl_row, width=6)
        self.dwell_entry.insert(0, "60")
        self.dwell_entry.pack(side=tk.LEFT)
        tk.Button(ctrl_row, text="✅ 解析並載入", command=self._parse_and_load).pack(side=tk.LEFT, padx=10)
        tk.Button(ctrl_row, text="📂 匯入 GPX", command=self._import_gpx).pack(side=tk.LEFT)

        result_lf = tk.LabelFrame(outer, text="解析結果", padx=8, pady=8)
        result_lf.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        list_top = tk.Frame(result_lf)
        list_top.pack(fill=tk.X)
        self.count_label = tk.Label(list_top, text="共 0 筆", fg="gray")
        self.count_label.pack(side=tk.LEFT)
        tk.Button(list_top, text="✅ 套用到主視窗", command=self._apply_to_main).pack(side=tk.RIGHT)
        tk.Button(list_top, text="💾 儲存 JSON", command=self._save_json).pack(side=tk.RIGHT, padx=4)
        tk.Button(list_top, text="🌸 規劃最佳路線", command=self._plan_route).pack(side=tk.RIGHT, padx=4)
        tk.Button(list_top, text="🔄 外圈巡邏", command=self._orbit_route).pack(side=tk.RIGHT, padx=4)
        tk.Button(list_top, text="🍎 種果路線", command=self._fruit_route).pack(side=tk.RIGHT, padx=4)
        self.plan_speed_entry = tk.Entry(list_top, width=5, font=("", 9))
        self.plan_speed_entry.insert(0, "20")
        self.plan_speed_entry.pack(side=tk.RIGHT)
        tk.Label(list_top, text="速度(km/h)：", font=("", 9), fg="gray").pack(side=tk.RIGHT, padx=(4, 0))

        lb_frame = tk.Frame(result_lf)
        lb_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        lb_sb = tk.Scrollbar(lb_frame)
        lb_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.result_lb = tk.Listbox(lb_frame, yscrollcommand=lb_sb.set, height=5, font=("Menlo", 12))
        self.result_lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        lb_sb.config(command=self.result_lb.yview)
        self.result_lb.bind("<<ListboxSelect>>", self._on_lb_select)

    def load_from_items(self, items: list):
        """以主視窗現有清單預填文字輸入區並觸發解析。"""
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
        self.text_input.delete("1.0", tk.END)
        self.text_input.insert("1.0", "\n".join(lines))
        self.dwell_entry.delete(0, tk.END)
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

    def _parse_and_load(self):
        try:
            default_dwell = max(1, int(self.dwell_entry.get().strip()))
        except ValueError:
            default_dwell = 60
        text = self.text_input.get("1.0", tk.END)
        self._items = self._parse_lines(text, default_dwell)
        self.result_lb.delete(0, tk.END)
        for item in self._items:
            self.result_lb.insert(tk.END, f"{item['name']}  ({item['dwell']}s)")
        self.count_label.config(text=f"共 {len(self._items)} 筆")

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
        self.result_lb.delete(0, tk.END)
        for item in self._items:
            self.result_lb.insert(tk.END, f"{item['name']}  ({item['dwell']}s)")
        self.count_label.config(text=f"共 {len(self._items)} 筆")

    def _on_lb_select(self, _event):
        sel = self.result_lb.curselection()
        if not sel:
            return
        item = self._items[sel[0]]
        self._location_fn(item["lat"], item["lng"])

    def _plan_route(self):
        if len(self._items) < 2:
            messagebox.showwarning("花點不足", "請先解析至少 2 個座標")
            return

        try:
            speed_kmh = max(1.0, float(self.plan_speed_entry.get().strip()))
        except ValueError:
            speed_kmh = 20.0

        flowers = [(float(it["lat"]), float(it["lng"])) for it in self._items]
        result = route_planner.plan_route(flowers, speed_kmh=speed_kmh)
        route = result["route"][:-1]  # 去掉回起點的重複點

        # 將路線座標映射回原始 items（以 lat/lng 浮點值比對）
        lookup = {(float(it["lat"]), float(it["lng"])): it for it in self._items}
        reordered = [lookup[pt] for pt in route if pt in lookup]

        if not reordered:
            messagebox.showerror("規劃失敗", "無法映射路線到清單")
            return

        self._items = reordered
        self.result_lb.delete(0, tk.END)
        for item in self._items:
            self.result_lb.insert(tk.END, f"{item['name']}  ({item['dwell']}s)")
        self.count_label.config(text=f"共 {len(self._items)} 筆")

        covered = len(result["covered"])
        total = len(flowers)
        dist = result["total_dist"]
        speed_mps = result["speed_mps"]
        msg = f"有效花點：{covered}/{total}\n總距離：{dist:.0f} 公尺\n預估時間：{dist/speed_mps/60:.1f} 分鐘（{speed_kmh:.0f} km/h）"
        if result["warnings"]:
            msg += "\n\n" + "\n".join(result["warnings"])
        messagebox.showinfo("路線規劃完成", msg)

    def _fruit_route(self):
        if len(self._items) < 2:
            messagebox.showwarning("座標不足", "請先解析至少 2 個座標")
            return

        flowers = [(float(it["lat"]), float(it["lng"])) for it in self._items]
        result = route_planner.fruit_route(flowers)
        route = result["route"]

        lookup = {(float(it["lat"]), float(it["lng"])): it for it in self._items}
        reordered = [lookup[pt] for pt in route if pt in lookup]

        if not reordered:
            messagebox.showerror("規劃失敗", "無法映射路線到清單")
            return

        self._items = reordered
        self.result_lb.delete(0, tk.END)
        for item in self._items:
            self.result_lb.insert(tk.END, f"{item['name']}  ({item['dwell']}s)")
        self.count_label.config(text=f"共 {len(self._items)} 筆")

        dist = result["total_dist"]
        try:
            speed_kmh = max(1.0, float(self.plan_speed_entry.get().strip()))
        except ValueError:
            speed_kmh = 20.0
        speed_mps = speed_kmh / 3.6
        messagebox.showinfo("種果路線規劃完成",
            f"總距離：{dist:.0f} 公尺\n"
            f"預估時間：{dist/speed_mps/60:.1f} 分鐘（{speed_kmh:.0f} km/h）\n\n"
            f"建議主視窗使用「單次」巡邏模式")

    def _orbit_route(self):
        if not self._items:
            messagebox.showwarning("花點不足", "請先解析至少 1 個座標")
            return

        try:
            default_dwell = max(0, int(self.dwell_entry.get().strip()))
        except ValueError:
            default_dwell = 0

        flowers = [(float(it["lat"]), float(it["lng"])) for it in self._items]
        result = route_planner.orbit_route(flowers)
        waypoints = result["waypoints"]

        if not waypoints:
            msg = "無法產生外圈路線"
            if result["warnings"]:
                msg += "\n\n" + "\n".join(result["warnings"])
            messagebox.showerror("規劃失敗", msg)
            return

        new_items = []
        for k, wp in enumerate(waypoints):
            new_items.append({
                "name": f"WP{k+1:02d}",
                "lat":  f"{wp[0]:.8f}",
                "lng":  f"{wp[1]:.8f}",
                "dwell": default_dwell,
            })

        self._items = new_items
        self.result_lb.delete(0, tk.END)
        for item in self._items:
            self.result_lb.insert(tk.END, f"{item['name']}  ({item['dwell']}s)")
        self.count_label.config(text=f"共 {len(self._items)} 筆")

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
