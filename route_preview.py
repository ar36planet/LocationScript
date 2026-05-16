"""
路線預覽視窗

目前使用 tkinter Canvas 繪製（Option C）。
要升級為真實地圖，將 _build_map_widget() 內的 Canvas 換成 TkinterMapWidget，
並調整 _draw() 使用 map_widget.set_path() / set_marker() 即可。
"""

import tkinter as tk
import customtkinter as ctk
import math

import route_planner
from ui.theme import FONT_BODY, FONT_SMALL, SECONDARY, BTN_SECONDARY, BTN_SECONDARY_HOVER, BTN_TEXT

_CANVAS_SIZE = 500
_PAD = 36
_BG = "#1e1e2e"
_RADIUS_COLOR = "#44475a"
_ROUTE_COLOR = "#8be9fd"
_WP_DOT_COLOR = "#6272a4"
_FLOWER_COLOR = "#ff79c6"
_ARROW_COLOR = "#50fa7b"
_TEXT_COLOR = "#f8f8f2"


class RoutePreviewWindow(ctk.CTkToplevel):
    """
    路線預覽 Toplevel。

    Parameters
    ----------
    waypoints : list of (lat, lng)
        要顯示的路線點（依順序連接成 polyline）。
    flowers : list of (lat, lng) | None
        原始花點座標，若提供則繪製 40m 有效半徑圈。
    """

    def __init__(self, parent, waypoints, flowers=None):
        super().__init__(parent)
        self.title("路線預覽")
        self.resizable(True, True)
        self.minsize(400, 460)

        self._waypoints = waypoints or []
        self._flowers = flowers or []

        self._build_ui()
        self.after(50, self._draw)  # 等視窗算好尺寸再畫

    # ── UI ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # ── 地圖區塊（未來換成 TkinterMapWidget 的位置）──────────────────
        map_frame = ctk.CTkFrame(self, fg_color="#12121e", corner_radius=8)
        map_frame.grid(row=0, column=0, sticky="nsew", padx=12, pady=(12, 0))
        map_frame.columnconfigure(0, weight=1)
        map_frame.rowconfigure(0, weight=1)

        self._canvas = tk.Canvas(
            map_frame,
            width=_CANVAS_SIZE,
            height=_CANVAS_SIZE,
            bg=_BG,
            highlightthickness=0,
        )
        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._canvas.bind("<Configure>", lambda e: self._draw())
        # ── 地圖區塊結束 ─────────────────────────────────────────────────

        # 圖例
        legend_frame = ctk.CTkFrame(self, fg_color="transparent")
        legend_frame.grid(row=1, column=0, sticky="ew", padx=12, pady=(6, 0))
        for color, label in [
            (_FLOWER_COLOR, "花點"),
            (_RADIUS_COLOR, "有效範圍 40m"),
            (_ROUTE_COLOR,  "路線"),
        ]:
            ctk.CTkLabel(legend_frame, text="●", font=FONT_SMALL,
                         text_color=color).pack(side="left", padx=(8, 2))
            ctk.CTkLabel(legend_frame, text=label, font=FONT_SMALL,
                         text_color=SECONDARY).pack(side="left", padx=(0, 8))

        # 資訊列
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=8)

        n_f = len(self._flowers)
        n_w = len(self._waypoints)
        info_text = f"花點 {n_f} 個 · 路線點 {n_w} 個"
        if n_w >= 2:
            dist = sum(
                route_planner.haversine(self._waypoints[i], self._waypoints[(i+1) % n_w])
                for i in range(n_w)
            )
            info_text += f" · 總距離 {dist:.0f} m"

        ctk.CTkLabel(info_frame, text=info_text,
                     font=FONT_SMALL, text_color=SECONDARY).pack(side="left")
        ctk.CTkButton(info_frame, text="關閉", command=self.destroy,
                      width=60, height=28, font=FONT_BODY,
                      fg_color=BTN_SECONDARY, hover_color=BTN_SECONDARY_HOVER,
                      text_color=BTN_TEXT).pack(side="right")

    # ── 座標投影 ─────────────────────────────────────────────────────────────

    def _setup_projection(self, all_pts, cw, ch):
        """將所有點轉為 canvas 像素座標的映射參數（等比例、保持長寬比）。"""
        origin = all_pts[0]
        pts_m = [route_planner.to_meters(p, origin) for p in all_pts]

        xs = [p[0] for p in pts_m]
        ys = [p[1] for p in pts_m]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        x_span = max(max_x - min_x, 80)   # 至少 80m 範圍，避免縮放爆炸
        y_span = max(max_y - min_y, 80)

        margin = 0.18
        min_x -= x_span * margin
        max_x += x_span * margin
        min_y -= y_span * margin
        max_y += y_span * margin
        x_span = max_x - min_x
        y_span = max_y - min_y

        avail_w = cw - 2 * _PAD
        avail_h = ch - 2 * _PAD
        scale = min(avail_w / x_span, avail_h / y_span)

        # 置中偏移
        drawn_w = x_span * scale
        drawn_h = y_span * scale
        self._ox = _PAD + (avail_w - drawn_w) / 2 - min_x * scale
        self._oy = ch - _PAD - (avail_h - drawn_h) / 2 + min_y * scale
        self._scale = scale
        self._origin = origin

    def _to_px(self, lat, lng):
        mx, my = route_planner.to_meters((lat, lng), self._origin)
        return self._ox + mx * self._scale, self._oy - my * self._scale

    # ── 繪圖 ─────────────────────────────────────────────────────────────────

    def _draw(self):
        c = self._canvas
        c.delete("all")

        cw = c.winfo_width() or _CANVAS_SIZE
        ch = c.winfo_height() or _CANVAS_SIZE

        all_pts = self._flowers + self._waypoints
        if not all_pts:
            c.create_text(cw // 2, ch // 2, text="無資料", fill=_TEXT_COLOR)
            return

        self._setup_projection(all_pts, cw, ch)

        # 有效半徑圈（虛線）
        r_px = route_planner.FLOWER_RADIUS_M * self._scale
        for f in self._flowers:
            cx, cy = self._to_px(*f)
            c.create_oval(cx - r_px, cy - r_px, cx + r_px, cy + r_px,
                          outline=_RADIUS_COLOR, width=1, dash=(5, 4))

        # 路線 polyline
        wps = self._waypoints
        if len(wps) >= 2:
            coords = []
            for wp in wps:
                coords.extend(self._to_px(*wp))
            # 閉合
            coords.extend(self._to_px(*wps[0]))
            c.create_line(*coords, fill=_ROUTE_COLOR, width=1.5, smooth=False)

            # 方向箭頭（每隔若干點畫一個）
            step = max(1, len(wps) // 8)
            for i in range(0, len(wps), step):
                p1 = wps[i]
                p2 = wps[(i + 1) % len(wps)]
                x1, y1 = self._to_px(*p1)
                x2, y2 = self._to_px(*p2)
                mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                angle = math.atan2(y2 - y1, x2 - x1)
                self._draw_arrow(c, mx, my, angle, size=5)

        # waypoint 小點
        for wp in wps:
            x, y = self._to_px(*wp)
            c.create_oval(x - 2, y - 2, x + 2, y + 2,
                          fill=_WP_DOT_COLOR, outline="")

        # 花點（較大、帶數字標籤）
        for i, f in enumerate(self._flowers):
            x, y = self._to_px(*f)
            c.create_oval(x - 5, y - 5, x + 5, y + 5,
                          fill=_FLOWER_COLOR, outline="white", width=1)
            c.create_text(x, y - 13, text=str(i + 1),
                          fill=_FLOWER_COLOR, font=("", 9, "bold"))

        # 比例尺
        self._draw_scale(c, cw, ch)

    def _draw_arrow(self, canvas, x, y, angle, size=5):
        tip_x = x + math.cos(angle) * size
        tip_y = y + math.sin(angle) * size
        left_x = x + math.cos(angle + 2.5) * size * 0.7
        left_y = y + math.sin(angle + 2.5) * size * 0.7
        right_x = x + math.cos(angle - 2.5) * size * 0.7
        right_y = y + math.sin(angle - 2.5) * size * 0.7
        canvas.create_polygon(tip_x, tip_y, left_x, left_y, right_x, right_y,
                              fill=_ARROW_COLOR, outline="")

    def _draw_scale(self, canvas, cw, ch):
        """左下角比例尺，自動選 10/20/50/100/200/500m。"""
        candidates = [10, 20, 50, 100, 200, 500, 1000]
        target_px = 60
        scale_m = min(candidates, key=lambda m: abs(m * self._scale - target_px))
        scale_px = scale_m * self._scale

        sx1 = _PAD
        sx2 = _PAD + scale_px
        sy = ch - 14
        canvas.create_line(sx1, sy, sx2, sy, fill=_TEXT_COLOR, width=2)
        for sx in (sx1, sx2):
            canvas.create_line(sx, sy - 4, sx, sy + 4, fill=_TEXT_COLOR, width=2)
        label = f"{scale_m}m" if scale_m < 1000 else f"{scale_m//1000}km"
        canvas.create_text((sx1 + sx2) / 2, sy - 10,
                           text=label, fill=_TEXT_COLOR, font=("", 8))
