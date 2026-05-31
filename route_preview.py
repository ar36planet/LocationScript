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
_INZONE_COLOR = "#50fa7b"
_WP_DOT_COLOR = "#6272a4"
_FLOWER_COLOR = "#ff79c6"
_ARROW_COLOR = "#ffb86c"
_TEXT_COLOR = "#f8f8f2"


def draw_on_canvas(canvas, waypoints, flowers=None, in_zones=None):
    """Draw a route preview onto an existing tk.Canvas widget."""
    c = canvas
    c.delete("all")
    cw = c.winfo_width() or _CANVAS_SIZE
    ch = c.winfo_height() or _CANVAS_SIZE

    flowers = list(flowers) if flowers else []
    waypoints = list(waypoints) if waypoints else []
    all_pts = flowers + waypoints
    if not all_pts:
        c.create_text(cw // 2, ch // 2, text="無資料", fill=_TEXT_COLOR)
        return

    origin = all_pts[0]
    pts_m = [route_planner.to_meters(p, origin) for p in all_pts]
    xs = [p[0] for p in pts_m]
    ys = [p[1] for p in pts_m]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    x_span = max(max_x - min_x, 80)
    y_span = max(max_y - min_y, 80)
    mg = 0.18
    min_x -= x_span * mg;  max_x += x_span * mg
    min_y -= y_span * mg;  max_y += y_span * mg
    x_span = max_x - min_x
    y_span = max_y - min_y
    avail_w = cw - 2 * _PAD
    avail_h = ch - 2 * _PAD
    scale = min(avail_w / x_span, avail_h / y_span)
    ox = _PAD + (avail_w - x_span * scale) / 2 - min_x * scale
    oy = ch - _PAD - (avail_h - y_span * scale) / 2 + min_y * scale

    def to_px(lat, lng):
        mx, my = route_planner.to_meters((lat, lng), origin)
        return ox + mx * scale, oy - my * scale

    r_px = route_planner.FLOWER_RADIUS_M * scale
    for f in flowers:
        cx, cy = to_px(*f)
        c.create_oval(cx - r_px, cy - r_px, cx + r_px, cy + r_px,
                      outline=_RADIUS_COLOR, width=1, dash=(5, 4))

    iz = in_zones or []
    wps = waypoints
    if len(wps) >= 2:
        # 逐段依 in_zone 上色：進入圈內的段用綠色，過境用藍色
        for i in range(len(wps)):
            j = (i + 1) % len(wps)
            seg_inzone = iz[j] if j < len(iz) else False
            color = _INZONE_COLOR if seg_inzone else _ROUTE_COLOR
            x1, y1 = to_px(*wps[i])
            x2, y2 = to_px(*wps[j])
            c.create_line(x1, y1, x2, y2, fill=color, width=1.5)

        step = max(1, len(wps) // 8)
        for i in range(0, len(wps), step):
            x1, y1 = to_px(*wps[i])
            x2, y2 = to_px(*wps[(i + 1) % len(wps)])
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            angle = math.atan2(y2 - y1, x2 - x1)
            sz = 5
            c.create_polygon(
                mx + math.cos(angle) * sz, my + math.sin(angle) * sz,
                mx + math.cos(angle + 2.5) * sz * 0.7, my + math.sin(angle + 2.5) * sz * 0.7,
                mx + math.cos(angle - 2.5) * sz * 0.7, my + math.sin(angle - 2.5) * sz * 0.7,
                fill=_ARROW_COLOR, outline="",
            )

    for i, wp in enumerate(wps):
        x, y = to_px(*wp)
        inzone = iz[i] if i < len(iz) else False
        color = _INZONE_COLOR if inzone else _WP_DOT_COLOR
        r = 3 if inzone else 2
        c.create_oval(x - r, y - r, x + r, y + r, fill=color, outline="")

    for i, f in enumerate(flowers):
        x, y = to_px(*f)
        c.create_oval(x - 5, y - 5, x + 5, y + 5,
                      fill=_FLOWER_COLOR, outline="white", width=1)
        c.create_text(x, y - 13, text=str(i + 1), fill=_FLOWER_COLOR, font=("", 9, "bold"))

    candidates = [10, 20, 50, 100, 200, 500, 1000]
    scale_m = min(candidates, key=lambda m: abs(m * scale - 60))
    scale_px = scale_m * scale
    sx1, sy = _PAD, ch - 14
    sx2 = sx1 + scale_px
    c.create_line(sx1, sy, sx2, sy, fill=_TEXT_COLOR, width=2)
    for sx in (sx1, sx2):
        c.create_line(sx, sy - 4, sx, sy + 4, fill=_TEXT_COLOR, width=2)
    lbl = f"{scale_m}m" if scale_m < 1000 else f"{scale_m // 1000}km"
    c.create_text((sx1 + sx2) / 2, sy - 10, text=lbl, fill=_TEXT_COLOR, font=("", 8))


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
        draw_on_canvas(self._canvas, self._waypoints, self._flowers)

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
