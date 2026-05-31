import math
import threading


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """回傳兩座標間的距離（公尺）。"""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


class PatrolController:
    """控制自動巡邏執行緒的生命週期（暫停/繼續/停止）。"""

    def __init__(self, location_fn):
        """
        location_fn: callable(lat: str, lng: str, save_history=False, _fetch_name=False)
            對應 set_location_direct，由外部注入以解耦 UI 依賴。
        """
        self._location_fn = location_fn
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # 預設不暫停
        self._thread = None
        self.is_running = False
        self.on_tick = None     # callable(idx, name, remaining_secs)
        self.on_travel = None   # callable(idx_to, name_to, remaining_m)
        self.on_finish = None   # callable() 走完一輪且不循環時呼叫
        self._speed_kmh = 0.0
        self._circle_speed_kmh = None   # None = 不分區，全用 _speed_kmh
        self._dwell_override = None     # None = 用 item 的 dwell
        self._mode = 'loop'     # 'loop' | 'once' | 'pingpong'

    def start(self, items, start_idx=0, speed_kmh=0.0,
              circle_speed_kmh=None, dwell_override=None, mode='loop'):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._pause_event.set()
        self._speed_kmh = max(0.0, float(speed_kmh))
        self._circle_speed_kmh = max(0.0, float(circle_speed_kmh)) if circle_speed_kmh is not None else None
        self._dwell_override = int(dwell_override) if dwell_override is not None else None
        self._mode = mode
        self.is_running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            args=(list(items), start_idx),
            daemon=True,
        )
        self._thread.start()

    def pause(self):
        self._pause_event.clear()

    def resume(self):
        self._pause_event.set()

    def stop(self):
        self._stop_event.set()
        self._pause_event.set()  # 解除可能的暫停阻塞
        self.is_running = False

    def _run_loop(self, items, start_idx):
        import time
        if not items:
            self.is_running = False
            return
        idx = start_idx
        direction = 1  # 1=正向, -1=反向（pingpong 用）
        prev_lat = prev_lng = None
        while not self._stop_event.is_set():
            if idx >= len(items):
                idx = 0
            if idx < 0:
                idx = 0
            item = items[idx]
            try:
                target_lat = float(item["lat"])
                target_lng = float(item["lng"])
            except (ValueError, KeyError):
                idx += 1
                continue
            in_zone = item.get("in_zone", False)
            seg_speed = (self._circle_speed_kmh
                         if (in_zone and self._circle_speed_kmh is not None)
                         else self._speed_kmh)
            if prev_lat is not None and seg_speed > 0:
                if not self._travel_between(prev_lat, prev_lng, target_lat, target_lng,
                                            idx, item["name"], speed_kmh=seg_speed):
                    break
            else:
                self._location_fn(item["lat"], item["lng"], save_history=False, _fetch_name=False)
            if self._stop_event.is_set():
                break
            prev_lat, prev_lng = target_lat, target_lng
            dwell = (self._dwell_override if self._dwell_override is not None
                     else max(0, int(item.get("dwell", 0))))
            for remaining in range(dwell, 0, -1):
                if self._stop_event.is_set():
                    break
                self._pause_event.wait()
                if self._stop_event.is_set():
                    break
                if self.on_tick:
                    try:
                        self.on_tick(idx, item["name"], remaining)
                    except Exception:
                        pass
                for _ in range(10):
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.1)
                if self._stop_event.is_set():
                    break
            if self._stop_event.is_set():
                break
            idx += direction
            if self._mode == 'pingpong':
                if idx >= len(items):
                    direction = -1
                    idx = max(0, len(items) - 2)
                elif idx < 0:
                    direction = 1
                    idx = min(len(items) - 1, 1)
            elif self._mode == 'once' and idx >= len(items):
                break
        self.is_running = False
        if not self._stop_event.is_set() and self.on_finish:
            try:
                self.on_finish()
            except Exception:
                pass

    def _travel_between(self, lat1, lng1, lat2, lng2, idx_to, name_to,
                         speed_kmh=None) -> bool:
        """從 (lat1,lng1) 模擬移動至 (lat2,lng2)。
        回傳 True 表示正常抵達，False 表示中途停止。"""
        import time
        dist_m = _haversine(lat1, lng1, lat2, lng2)
        if dist_m < 5:
            self._location_fn(str(lat2), str(lng2), save_history=False, _fetch_name=False)
            return True
        speed_mps = (speed_kmh if speed_kmh is not None else self._speed_kmh) * 1000 / 3600
        STEP_S = 5
        n_steps = max(1, round(dist_m / (speed_mps * STEP_S)))
        for step in range(1, n_steps + 1):
            if self._stop_event.is_set():
                return False
            self._pause_event.wait()
            if self._stop_event.is_set():
                return False
            t = step / n_steps
            lat = lat1 + (lat2 - lat1) * t
            lng = lng1 + (lng2 - lng1) * t
            self._location_fn(str(lat), str(lng), save_history=False, _fetch_name=False)
            if self.on_travel:
                try:
                    self.on_travel(idx_to, name_to, dist_m * (1 - t))
                except Exception:
                    pass
            for _ in range(STEP_S * 10):  # 0.1s × (STEP_S×10) = STEP_S 秒
                if self._stop_event.is_set():
                    return False
                time.sleep(0.1)
        return True
