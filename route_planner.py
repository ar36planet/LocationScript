"""
花點路線規劃器
==============
輸入：花點座標（十進位經緯度）
輸出：最佳循環路線，5 分鐘內不走重複路徑，最大化有效花點數

規則：
- 每個花點半徑 40 公尺為有效範圍，路線經過即可計入
- 5 分鐘內不能走重複路徑（兩線段實際相交或重疊才算重複）
- 自動選最佳起點
- 目標：最大化經過的有效花點數
"""

import math
import itertools
import heapq
from typing import List, Tuple, Optional

# ── 型別別名 ──────────────────────────────────────────────
Point = Tuple[float, float]   # (lat, lng)

# ── 常數 ──────────────────────────────────────────────────
FLOWER_RADIUS_M = 40.0        # 有效半徑（公尺）
WALK_SPEED_MPS  = 1.4         # 步行速度（公尺/秒），約 5 km/h
TIME_LIMIT_SEC  = 5 * 60      # 5 分鐘
MAX_WALK_DIST_M = WALK_SPEED_MPS * TIME_LIMIT_SEC  # 約 420 公尺


# ════════════════════════════════════════════════════════════
# 工具函式
# ════════════════════════════════════════════════════════════

def haversine(p1: Point, p2: Point) -> float:
    """兩點間距離（公尺）"""
    R = 6_371_000
    lat1, lon1 = math.radians(p1[0]), math.radians(p1[1])
    lat2, lon2 = math.radians(p2[0]), math.radians(p2[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def to_meters(p: Point, origin: Point) -> Tuple[float, float]:
    """將經緯度轉換為以 origin 為原點的平面座標（公尺）"""
    cos_lat = math.cos(math.radians(origin[0]))
    x = (p[1] - origin[1]) * 111320 * cos_lat
    y = (p[0] - origin[0]) * 111320
    return (x, y)


def from_meters(p_m: Tuple[float, float], origin: Point) -> Point:
    """平面座標（公尺）轉回經緯度"""
    cos_lat = math.cos(math.radians(origin[0]))
    lat = origin[0] + p_m[1] / 111320
    lng = origin[1] + p_m[0] / (111320 * cos_lat)
    return (lat, lng)


def _convex_hull_ccw(pts_m: List[Tuple[float, float]]) -> List[int]:
    """Andrew's monotone chain，回傳逆時針凸包的索引列表"""
    n = len(pts_m)
    if n <= 1:
        return list(range(n))
    idx = sorted(range(n), key=lambda i: (pts_m[i][0], pts_m[i][1]))

    def cross(o, a, b):
        return ((pts_m[a][0] - pts_m[o][0]) * (pts_m[b][1] - pts_m[o][1])
                - (pts_m[a][1] - pts_m[o][1]) * (pts_m[b][0] - pts_m[o][0]))

    lower: List[int] = []
    for i in idx:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], i) <= 0:
            lower.pop()
        lower.append(i)

    upper: List[int] = []
    for i in reversed(idx):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], i) <= 0:
            upper.pop()
        upper.append(i)

    return lower[:-1] + upper[:-1]


def orbit_route(flowers: List[Point],
                radius_m: float = FLOWER_RADIUS_M,
                arc_steps: int = 8) -> dict:
    """
    生成沿所有花點圓外側邊界的封閉軌道路線。
    自動依花點間距計算安全半徑，確保直線段中點也在有效範圍內：
      safe_r = sqrt(radius_m² - (最長凸包邊/2)²)
    回傳 dict：
      waypoints    - 路徑點列表（首尾不重複）
      radius_used  - 實際使用的半徑（公尺）
      warnings     - 警告訊息列表
    """
    if not flowers:
        return {"waypoints": [], "radius_used": 0.0, "warnings": []}

    origin = flowers[0]
    pts_m = [to_meters(f, origin) for f in flowers]
    hull_idx = _convex_hull_ccw(pts_m)
    hull_m = [pts_m[i] for i in hull_idx]
    n = len(hull_m)

    warnings: List[str] = []

    # 計算最大安全半徑（讓所有直線段中點都在有效範圍內）
    if n == 1:
        safe_r = radius_m
    else:
        max_edge = max(
            math.hypot(hull_m[(i+1) % n][0] - hull_m[i][0],
                       hull_m[(i+1) % n][1] - hull_m[i][1])
            for i in range(n)
        )
        if max_edge / 2 >= radius_m:
            warnings.append(
                f"⚠️  花點最大間距 {max_edge:.0f}m 超過有效直徑 {radius_m*2:.0f}m，"
                "圓不相交，無法建立有效軌道"
            )
            return {"waypoints": [], "radius_used": 0.0, "warnings": warnings}
        safe_r = math.sqrt(radius_m ** 2 - (max_edge / 2) ** 2)
        if safe_r < radius_m * 0.5:
            warnings.append(
                f"⚠️  花點間距較大，安全半徑已縮減至 {safe_r:.0f}m"
            )

    waypoints: List[Point] = []

    for i in range(n):
        V      = hull_m[i]
        V_prev = hull_m[(i - 1) % n]
        V_next = hull_m[(i + 1) % n]

        d_in  = math.degrees(math.atan2(V[1] - V_prev[1], V[0] - V_prev[0]))
        d_out = math.degrees(math.atan2(V_next[1] - V[1], V_next[0] - V[0]))

        arc_start = (d_in  - 90) % 360
        arc_end   = (d_out - 90) % 360

        if arc_end <= arc_start:
            arc_end += 360
        arc_span = arc_end - arc_start

        steps = max(1, round(arc_steps * arc_span / 360))
        for j in range(steps + 1):
            angle = arc_start + arc_span * j / steps
            x = V[0] + safe_r * math.cos(math.radians(angle))
            y = V[1] + safe_r * math.sin(math.radians(angle))
            waypoints.append(from_meters((x, y), origin))

    return {"waypoints": waypoints, "radius_used": safe_r, "warnings": warnings}


def _two_opt_open(route: List[Point], max_iter: int = 500) -> List[Point]:
    """2-opt 改良（開放路徑版，無需回起點）"""
    best = route[:]
    improved = True
    iters = 0
    while improved and iters < max_iter:
        improved = False
        iters += 1
        n = len(best)
        for i in range(n - 1):
            for j in range(i + 2, n):
                candidate = best[:i+1] + best[i+1:j+1][::-1] + best[j+1:]
                if route_distance(candidate) < route_distance(best) - 1e-6:
                    best = candidate
                    improved = True
    return best


def fruit_route(flowers: List[Point]) -> dict:
    """
    種果模式：最短單向路徑，依序經過所有花點（不回起點）。
    回傳 dict：
      route      - 最佳路線（花點順序列表）
      total_dist - 總距離（公尺）
    """
    if not flowers:
        return {"route": [], "total_dist": 0}
    if len(flowers) == 1:
        return {"route": flowers[:], "total_dist": 0}

    n = len(flowers)
    best_route: Optional[List[Point]] = None
    best_dist = float('inf')

    for start_idx in range(n):
        visited = [False] * n
        route = [flowers[start_idx]]
        visited[start_idx] = True
        current = start_idx

        while True:
            next_idx, next_d = None, float('inf')
            for j in range(n):
                if not visited[j]:
                    d = haversine(flowers[current], flowers[j])
                    if d < next_d:
                        next_d, next_idx = d, j
            if next_idx is None:
                break
            route.append(flowers[next_idx])
            visited[next_idx] = True
            current = next_idx

        route = _two_opt_open(route)
        dist = route_distance(route)
        if dist < best_dist:
            best_dist, best_route = dist, route

    return {"route": best_route, "total_dist": best_dist}


def cross2d(ax, ay, bx, by) -> float:
    return ax * by - ay * bx


def segments_intersect(p1: Point, p2: Point, p3: Point, p4: Point,
                        origin: Point) -> bool:
    """
    判斷線段 p1-p2 與 p3-p4 是否相交或重疊（平面近似）
    共端點不算相交（允許路線在節點銜接）
    """
    def eq(a, b):
        return abs(a[0]-b[0]) < 1e-9 and abs(a[1]-b[1]) < 1e-9

    # 共端點：允許
    if eq(p1,p3) or eq(p1,p4) or eq(p2,p3) or eq(p2,p4):
        return False

    a  = to_meters(p1, origin)
    b  = to_meters(p2, origin)
    c  = to_meters(p3, origin)
    d  = to_meters(p4, origin)

    abx, aby = b[0]-a[0], b[1]-a[1]
    cdx, cdy = d[0]-c[0], d[1]-c[1]

    denom = cross2d(abx, aby, cdx, cdy)

    acx, acy = c[0]-a[0], c[1]-a[1]

    if abs(denom) < 1e-9:
        # 平行或共線：檢查是否重疊
        # 先確認共線
        if abs(cross2d(acx, acy, abx, aby)) > 1e-6:
            return False  # 平行但不共線
        # 投影到主軸
        def proj(p, q, r):
            dx, dy = q[0]-p[0], q[1]-p[1]
            denom = dx*dx + dy*dy
            if denom < 1e-12:
                return 0.0
            return ((r[0]-p[0])*dx + (r[1]-p[1])*dy) / denom
        t0 = proj(a, b, c)
        t1 = proj(a, b, d)
        lo, hi = min(t0, t1), max(t0, t1)
        # 重疊條件（排除剛好端點碰觸）
        overlap = min(hi, 1.0) - max(lo, 0.0)
        return overlap > 1e-6

    t = cross2d(acx, acy, cdx, cdy) / denom
    u = cross2d(acx, acy, abx, aby) / denom

    return (1e-9 < t < 1-1e-9) and (1e-9 < u < 1-1e-9)


def route_has_crossing(route: List[Point], origin: Point) -> bool:
    """檢查路線中是否有任兩線段相交"""
    segs = [(route[i], route[i+1]) for i in range(len(route)-1)]
    for i in range(len(segs)):
        for j in range(i+2, len(segs)):
            if segments_intersect(segs[i][0], segs[i][1],
                                   segs[j][0], segs[j][1], origin):
                return True
    return False


def flowers_covered(route: List[Point], flowers: List[Point]) -> List[int]:
    """回傳路線覆蓋到的花點索引（任一線段端點在有效範圍內即算）"""
    covered = set()
    for pt in route:
        for i, f in enumerate(flowers):
            if haversine(pt, f) <= FLOWER_RADIUS_M:
                covered.add(i)
    # 也檢查線段上的最近點
    origin = flowers[0] if flowers else route[0]
    for i, f in enumerate(flowers):
        if i in covered:
            continue
        fm = to_meters(f, origin)
        for k in range(len(route)-1):
            am = to_meters(route[k],   origin)
            bm = to_meters(route[k+1], origin)
            d  = point_to_segment_dist(fm, am, bm)
            if d <= FLOWER_RADIUS_M:
                covered.add(i)
                break
    return sorted(covered)


def point_to_segment_dist(p, a, b) -> float:
    """點 p 到線段 ab 的最短距離（平面，公尺）"""
    dx, dy = b[0]-a[0], b[1]-a[1]
    if dx == 0 and dy == 0:
        return math.hypot(p[0]-a[0], p[1]-a[1])
    t = ((p[0]-a[0])*dx + (p[1]-a[1])*dy) / (dx*dx + dy*dy)
    t = max(0.0, min(1.0, t))
    nx, ny = a[0]+t*dx, a[1]+t*dy
    return math.hypot(p[0]-nx, p[1]-ny)


def route_distance(route: List[Point]) -> float:
    return sum(haversine(route[i], route[i+1]) for i in range(len(route)-1))


# ════════════════════════════════════════════════════════════
# 核心演算法：貪婪 + 回溯改良
# ════════════════════════════════════════════════════════════

def greedy_route(flowers: List[Point], start_idx: int) -> List[Point]:
    """
    從指定花點出發，貪婪地找下一個最近且未訪問的花點，
    最後回到起點，形成循環路線。
    """
    n = len(flowers)
    visited = [False] * n
    route = [flowers[start_idx]]
    visited[start_idx] = True
    current = start_idx

    while True:
        best_next = None
        best_dist = float('inf')
        for j in range(n):
            if not visited[j]:
                d = haversine(flowers[current], flowers[j])
                if d < best_dist:
                    best_dist = d
                    best_next = j
        if best_next is None:
            break
        route.append(flowers[best_next])
        visited[best_next] = True
        current = best_next

    route.append(flowers[start_idx])  # 回起點
    return route


def two_opt(route: List[Point], origin: Point,
            max_iter: int = 500) -> List[Point]:
    """
    2-opt 改良：嘗試交換線段以縮短距離，同時確保不產生路徑交叉。
    循環路線（首尾相同），操作 route[1:-1] 部分。
    """
    best = route[:]
    improved = True
    iters = 0
    while improved and iters < max_iter:
        improved = False
        iters += 1
        n = len(best) - 1  # 不含最後的重複起點
        for i in range(1, n - 1):
            for j in range(i + 1, n):
                # 反轉 i..j 段
                candidate = best[:i] + best[i:j+1][::-1] + best[j+1:]
                if route_has_crossing(candidate, origin):
                    continue
                if route_distance(candidate) < route_distance(best) - 1e-6:
                    best = candidate
                    improved = True
    return best


def flower_circles_route(
    flowers: List[Point],
    circle_radius_m: float = 25.0,
    circle_steps: int = 8,
) -> dict:
    """
    種花路線：TSP 排序後在每個花點繞一完整圓圈，圈與圈之間直線移動。

    每個花點生成 circle_steps 個 waypoint，從「上一個花點方向」開始逆時針走一圈，
    自然銜接下一個花點的圓圈，不折返。

    回傳 dict：
      waypoints      - 所有 waypoint 列表（循環路線，不重複首尾）
      total_dist     - 總距離（公尺）
      ordered_flowers - TSP 排序後的花點順序
      warnings       - 警告訊息
    """
    if not flowers:
        return {"waypoints": [], "total_dist": 0.0,
                "ordered_flowers": [], "warnings": []}

    warnings: List[str] = []
    if circle_radius_m > FLOWER_RADIUS_M:
        warnings.append(
            f"⚠️ 圓圈半徑 {circle_radius_m:.0f}m 超過有效範圍 {FLOWER_RADIUS_M:.0f}m，"
            f"自動縮減至 {FLOWER_RADIUS_M * 0.9:.0f}m"
        )
        circle_radius_m = FLOWER_RADIUS_M * 0.9

    if len(flowers) == 1:
        origin = flowers[0]
        fm = to_meters(flowers[0], origin)
        waypoints = [
            from_meters(
                (fm[0] + circle_radius_m * math.cos(math.radians(90 + 360 * j / circle_steps)),
                 fm[1] + circle_radius_m * math.sin(math.radians(90 + 360 * j / circle_steps))),
                origin,
            )
            for j in range(circle_steps)
        ]
        # j=0 是從上一圈抵達的過渡點，其餘為圈內
        in_zones = [j > 0 for j in range(circle_steps)]
        n = len(waypoints)
        total_dist = sum(haversine(waypoints[i], waypoints[(i+1) % n]) for i in range(n))
        return {"waypoints": waypoints, "in_zones": in_zones, "total_dist": total_dist,
                "ordered_flowers": flowers[:], "warnings": warnings}

    # TSP 排序（借用 fruit_route 的最短路徑邏輯）
    fr = fruit_route(flowers)
    ordered = fr["route"]
    origin = flowers[0]
    waypoints: List[Point] = []
    in_zones: List[bool] = []

    for i, flower in enumerate(ordered):
        fm = to_meters(flower, origin)
        prev_flower = ordered[i - 1]
        prev_m = to_meters(prev_flower, origin)
        start_angle = math.degrees(math.atan2(prev_m[1] - fm[1], prev_m[0] - fm[0]))

        for j in range(circle_steps):
            angle = start_angle + 360.0 * j / circle_steps
            x = fm[0] + circle_radius_m * math.cos(math.radians(angle))
            y = fm[1] + circle_radius_m * math.sin(math.radians(angle))
            waypoints.append(from_meters((x, y), origin))
            in_zones.append(j > 0)  # j=0 是圈間過渡抵達點，j>0 是圈內移動

    n = len(waypoints)
    total_dist = sum(haversine(waypoints[i], waypoints[(i+1) % n]) for i in range(n))

    return {
        "waypoints": waypoints,
        "in_zones": in_zones,
        "total_dist": total_dist,
        "ordered_flowers": ordered,
        "warnings": warnings,
    }


def plan_route(flowers: List[Point], speed_kmh: float = WALK_SPEED_MPS * 3.6) -> dict:
    """
    主函式：嘗試所有起點，回傳最佳結果。
    speed_kmh: 移動速度（km/h），用於計算時間限制，預設同 WALK_SPEED_MPS
    回傳 dict：
      route       - 完整路線（含回起點）
      covered     - 有效花點索引列表
      total_dist  - 總距離（公尺）
      valid       - 是否符合時間與無交叉限制
      warnings    - 警告訊息列表
    """
    if not flowers:
        return {"route": [], "covered": [], "total_dist": 0,
                "valid": False, "warnings": ["未輸入任何花點"]}

    speed_mps = max(speed_kmh / 3.6, 0.1)
    max_dist  = speed_mps * TIME_LIMIT_SEC

    origin = flowers[0]
    best_result = None
    best_score  = -1

    for start_idx in range(len(flowers)):
        # 1. 貪婪初始路線
        route = greedy_route(flowers, start_idx)

        # 2. 2-opt 改良（縮短距離、消除交叉）
        route = two_opt(route, origin)

        # 3. 評估
        dist     = route_distance(route)
        covered  = flowers_covered(route, flowers)
        crossing = route_has_crossing(route, origin)
        score    = len(covered) * 1000 - dist  # 優先最多花，次要最短路

        if score > best_score:
            best_score  = score
            best_result = {
                "route":      route,
                "covered":    covered,
                "total_dist": dist,
                "crossing":   crossing,
            }

    route    = best_result["route"]
    covered  = best_result["covered"]
    dist     = best_result["total_dist"]
    crossing = best_result["crossing"]

    warnings = []
    if dist > max_dist:
        warnings.append(
            f"⚠️  總距離 {dist:.0f}m 超過 5 分鐘上限"
            f"（{speed_kmh:.1f} km/h 可走約 {max_dist:.0f}m）"
        )
    if crossing:
        warnings.append("⚠️  路線仍存在交叉（花點分佈複雜，建議手動調整）")

    return {
        "route":      route,
        "covered":    covered,
        "total_dist": dist,
        "valid":      dist <= max_dist and not crossing,
        "warnings":   warnings,
        "speed_mps":  speed_mps,
    }


# ════════════════════════════════════════════════════════════
# 輸出格式化
# ════════════════════════════════════════════════════════════

def print_result(flowers: List[Point], result: dict):
    route    = result["route"]
    covered  = result["covered"]
    dist     = result["total_dist"]
    warnings = result["warnings"]

    print("=" * 55)
    print("  🌸 花點路線規劃結果")
    print("=" * 55)

    print(f"\n📍 輸入花點（共 {len(flowers)} 個）：")
    for i, f in enumerate(flowers):
        tag = "✅" if i in covered else "❌"
        print(f"   花點 {i+1:>2}  {f[0]:.8f}, {f[1]:.9f}  {tag}")

    print(f"\n🗺️  最佳路線（共 {len(route)-1} 段）：")
    for i, pt in enumerate(route):
        label = "（起點）" if i == 0 else ("（回起點）" if i == len(route)-1 else "")
        print(f"   WP{i+1:02d}  {pt[0]:.8f}, {pt[1]:.9f}  {label}")

    print(f"\n📊 統計：")
    print(f"   有效花點數：{len(covered)} / {len(flowers)}")
    print(f"   總距離：    {dist:.1f} 公尺")
    print(f"   預估時間：  {dist/WALK_SPEED_MPS/60:.1f} 分鐘（步行 {WALK_SPEED_MPS*3.6:.1f} km/h）")
    print(f"   5 分鐘限制：{'✅ 符合' if dist <= MAX_WALK_DIST_M else '❌ 超過'}")

    if warnings:
        print("\n⚠️  警告：")
        for w in warnings:
            print(f"   {w}")

    print("\n" + "=" * 55)


# ════════════════════════════════════════════════════════════
# 主程式入口
# ════════════════════════════════════════════════════════════

def parse_input() -> List[Point]:
    """互動式輸入花點座標"""
    print("=" * 55)
    print("  🌸 花點路線規劃器")
    print("=" * 55)
    print("輸入格式：緯度,經度  （每行一點）")
    print("輸入完畢後按 Enter 留空行結束\n")

    flowers = []
    while True:
        try:
            line = input(f"  花點 {len(flowers)+1}：").strip()
        except EOFError:
            break
        if not line:
            if len(flowers) >= 2:
                break
            print("  ⚠️  請至少輸入 2 個花點")
            continue
        try:
            parts = line.replace("，", ",").split(",")
            lat = float(parts[0].strip())
            lng = float(parts[1].strip())
            if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                raise ValueError
            flowers.append((lat, lng))
            print(f"         ✅ 已加入 ({lat:.6f}, {lng:.6f})")
        except (ValueError, IndexError):
            print("  ❌ 格式錯誤，請輸入如：25.021056,121.739472")

    return flowers


# ════════════════════════════════════════════════════════════
# 種果安全路線
# ════════════════════════════════════════════════════════════

def _is_safe_m(
    p: Tuple[float, float],
    flowers_m: List[Tuple[float, float]],
    avoid_r: float,
    max_r: float,
) -> bool:
    """True if p is outside every forbidden zone AND within max_r of at least one flower."""
    near = False
    for f in flowers_m:
        d = math.hypot(p[0] - f[0], p[1] - f[1])
        if d < avoid_r:
            return False
        if d <= max_r:
            near = True
    return near


def _seg_safe_m(
    a: Tuple[float, float],
    b: Tuple[float, float],
    flowers_m: List[Tuple[float, float]],
    avoid_r: float,
    max_r: float,
    step: float = 5.0,
) -> bool:
    """True if the segment a→b stays entirely in the safe zone (sampled every step metres)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return _is_safe_m(a, flowers_m, avoid_r, max_r)
    n_steps = max(2, int(length / step) + 1)
    for i in range(n_steps + 1):
        t = i / n_steps
        if not _is_safe_m((a[0] + t * dx, a[1] + t * dy), flowers_m, avoid_r, max_r):
            return False
    return True


def _dijkstra_path(
    adj: List[List[Tuple[int, float]]],
    src: int,
    dst: int,
) -> Tuple[float, List[int]]:
    """Dijkstra on adjacency list. Returns (distance, node-index path). path=[] if unreachable."""
    n = len(adj)
    dist = [math.inf] * n
    prev = [-1] * n
    dist[src] = 0.0
    pq: List[Tuple[float, int]] = [(0.0, src)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        if u == dst:
            break
        for v, w in adj[u]:
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))
    if math.isinf(dist[dst]):
        return math.inf, []
    path, u = [], dst
    while u != -1:
        path.append(u)
        u = prev[u]
    return dist[dst], path[::-1]


def safe_fruit_route(
    flowers: List[Point],
    start: Optional[Point] = None,
    end: Optional[Point] = None,
    avoid_radius_m: float = FLOWER_RADIUS_M,
    max_dist_m: float = 80.0,
    margin_m: float = 5.0,
    n_candidates: int = 24,
) -> dict:
    """
    種果安全路線：全程在所有花點有效範圍外（> avoid_radius_m），
    且不離最近花點超過 max_dist_m。

    end=None  → 循環路線，自動遍訪每個花點旁最佳種果點後回起點
    start/end → 單向最短安全路徑

    回傳 dict：
      waypoints    - 完整路線（經緯度列表）
      total_dist   - 總距離（公尺）
      is_loop      - bool
      fruit_spots  - 每個花點對應最佳種果座標（None 表示找不到）
      warnings     - 警告列表
      avoid_radius_m, max_dist_m - 使用的參數
    """
    is_loop = end is None
    warnings: List[str] = []

    if not flowers:
        return {"waypoints": [], "total_dist": 0.0, "is_loop": is_loop,
                "fruit_spots": [], "warnings": ["未輸入花點"],
                "avoid_radius_m": avoid_radius_m, "max_dist_m": max_dist_m}

    origin = flowers[0]
    flowers_m = [to_meters(f, origin) for f in flowers]
    safe_r = avoid_radius_m + margin_m

    for i in range(len(flowers_m)):
        for j in range(i + 1, len(flowers_m)):
            d = math.hypot(flowers_m[i][0] - flowers_m[j][0],
                           flowers_m[i][1] - flowers_m[j][1])
            if d < 2 * avoid_radius_m:
                warnings.append(
                    f"⚠️ 花點 {i+1} 與 {j+1} 距離 {d:.0f}m，禁區重疊"
                    f"（< {2*avoid_radius_m:.0f}m）"
                )

    # ── 1. 生成候選節點 ────────────────────────────────────
    per_flower_cands: List[List[Tuple[float, float]]] = []
    all_cands: List[Tuple[float, float]] = []

    for fi, f_m in enumerate(flowers_m):
        cands: List[Tuple[float, float]] = []
        for k in range(n_candidates):
            angle = 2 * math.pi * k / n_candidates
            p = (f_m[0] + safe_r * math.cos(angle),
                 f_m[1] + safe_r * math.sin(angle))
            if _is_safe_m(p, flowers_m, avoid_radius_m, max_dist_m):
                cands.append(p)
        per_flower_cands.append(cands)
        all_cands.extend(cands)

    # 補充花點對之間的通道中點候選（避免窄通道無節點）
    for i in range(len(flowers_m)):
        for j in range(i + 1, len(flowers_m)):
            d = math.hypot(flowers_m[i][0] - flowers_m[j][0],
                           flowers_m[i][1] - flowers_m[j][1])
            if d >= 2 * max_dist_m:
                continue
            dx_n = (flowers_m[j][0] - flowers_m[i][0]) / d
            dy_n = (flowers_m[j][1] - flowers_m[i][1]) / d
            mid = ((flowers_m[i][0] + flowers_m[j][0]) / 2,
                   (flowers_m[i][1] + flowers_m[j][1]) / 2)
            for off in (0.0, safe_r * 0.5, -safe_r * 0.5, safe_r, -safe_r):
                p = (mid[0] - dy_n * off, mid[1] + dx_n * off)
                if _is_safe_m(p, flowers_m, avoid_radius_m, max_dist_m):
                    all_cands.append(p)

    # 去重（1m 內視為同點）
    unique_cands: List[Tuple[float, float]] = []
    for p in all_cands:
        if not any(math.hypot(p[0] - q[0], p[1] - q[1]) < 1.0 for q in unique_cands):
            unique_cands.append(p)
    all_cands = unique_cands

    if not all_cands:
        return {"waypoints": [], "total_dist": 0.0, "is_loop": is_loop,
                "fruit_spots": [], "warnings": warnings + ["所有候選點均落入禁區，無法規劃路線"],
                "avoid_radius_m": avoid_radius_m, "max_dist_m": max_dist_m}

    # ── 2. 選各花點代表種果點 ─────────────────────────────
    # 選最靠近其他花點重心的候選（傾向內側，縮短迴路）
    fruit_spots_m: List[Optional[Tuple[float, float]]] = []
    for fi, f_m in enumerate(flowers_m):
        if not per_flower_cands[fi]:
            fruit_spots_m.append(None)
            warnings.append(f"⚠️ 花點 {fi+1} 附近無安全種果點")
            continue
        others = [flowers_m[j] for j in range(len(flowers_m)) if j != fi]
        if others:
            cx = sum(o[0] for o in others) / len(others)
            cy = sum(o[1] for o in others) / len(others)
            spot = min(per_flower_cands[fi],
                       key=lambda p: math.hypot(p[0] - cx, p[1] - cy))
        else:
            spot = per_flower_cands[fi][0]
        fruit_spots_m.append(spot)

    # ── 3. 建立可見度圖 ────────────────────────────────────
    nodes: List[Tuple[float, float]] = list(all_cands)

    def _add_node(p_m: Optional[Tuple[float, float]]) -> Optional[int]:
        if p_m is None:
            return None
        for i, n in enumerate(nodes):
            if math.hypot(n[0] - p_m[0], n[1] - p_m[1]) < 0.1:
                return i
        idx = len(nodes)
        nodes.append(p_m)
        return idx

    start_m = to_meters(start, origin) if start is not None else None
    end_m   = to_meters(end,   origin) if end   is not None else None
    start_idx = _add_node(start_m)
    end_idx   = _add_node(end_m) if not is_loop else None
    spot_idx  = [_add_node(s) for s in fruit_spots_m]

    n_nodes = len(nodes)
    adj: List[List[Tuple[int, float]]] = [[] for _ in range(n_nodes)]
    for i in range(n_nodes):
        for j in range(i + 1, n_nodes):
            if _seg_safe_m(nodes[i], nodes[j], flowers_m, avoid_radius_m, max_dist_m):
                d = math.hypot(nodes[i][0] - nodes[j][0], nodes[i][1] - nodes[j][1])
                adj[i].append((j, d))
                adj[j].append((i, d))

    # ── 4a. 循環路線 ──────────────────────────────────────
    if is_loop:
        tsp_nodes = [idx for idx in spot_idx if idx is not None]
        if not tsp_nodes:
            return {"waypoints": [], "total_dist": 0.0, "is_loop": True,
                    "fruit_spots": [from_meters(s, origin) if s else None for s in fruit_spots_m],
                    "warnings": warnings + ["無可用種果點"],
                    "avoid_radius_m": avoid_radius_m, "max_dist_m": max_dist_m}

        n_t = len(tsp_nodes)

        # All-pairs Dijkstra
        ap_d: List[List[float]] = [[math.inf] * n_t for _ in range(n_t)]
        ap_p: List[List[List[int]]] = [[[] for _ in range(n_t)] for _ in range(n_t)]
        for i in range(n_t):
            ap_d[i][i] = 0.0
            ap_p[i][i] = [tsp_nodes[i]]
        for i in range(n_t):
            for j in range(i + 1, n_t):
                dij, pij = _dijkstra_path(adj, tsp_nodes[i], tsp_nodes[j])
                ap_d[i][j] = ap_d[j][i] = dij
                ap_p[i][j] = pij
                ap_p[j][i] = pij[::-1]

        # 貪婪 TSP（每個起點都試一次）
        best_tour: Optional[List[int]] = None
        best_dist_tsp = math.inf
        for s in range(n_t):
            vis = [False] * n_t
            tour = [s]
            vis[s] = True
            total = 0.0
            cur = s
            while len(tour) < n_t:
                nxt = min(
                    (j for j in range(n_t) if not vis[j]),
                    key=lambda j: ap_d[cur][j],
                    default=None,
                )
                if nxt is None or math.isinf(ap_d[cur][nxt]):
                    break
                tour.append(nxt)
                vis[nxt] = True
                total += ap_d[cur][nxt]
                cur = nxt
            total += ap_d[cur][s]
            if len(tour) == n_t and total < best_dist_tsp:
                best_dist_tsp = total
                best_tour = tour[:]

        if best_tour is None:
            return {"waypoints": [], "total_dist": 0.0, "is_loop": True,
                    "fruit_spots": [from_meters(s, origin) if s else None for s in fruit_spots_m],
                    "warnings": warnings + ["無法建立連通迴路（部分花點可能被禁區包圍）"],
                    "avoid_radius_m": avoid_radius_m, "max_dist_m": max_dist_m}

        # 2-opt 改良
        improved = True
        while improved:
            improved = False
            for i in range(n_t - 1):
                for j in range(i + 2, n_t):
                    if i == 0 and j == n_t - 1:
                        continue
                    old_c = (ap_d[best_tour[i]][best_tour[i + 1]] +
                             ap_d[best_tour[j]][best_tour[(j + 1) % n_t]])
                    new_c = (ap_d[best_tour[i]][best_tour[j]] +
                             ap_d[best_tour[i + 1]][best_tour[(j + 1) % n_t]])
                    if new_c < old_c - 1e-6:
                        best_tour[i + 1:j + 1] = best_tour[i + 1:j + 1][::-1]
                        best_dist_tsp = sum(
                            ap_d[best_tour[k]][best_tour[(k + 1) % n_t]]
                            for k in range(n_t)
                        )
                        improved = True
                        break
                if improved:
                    break

        # 重建完整路徑
        path_nodes: List[int] = []
        for k in range(n_t):
            seg = ap_p[best_tour[k]][best_tour[(k + 1) % n_t]]
            if not seg:
                warnings.append(
                    f"⚠️ 種果點 {best_tour[k]+1}→{best_tour[(k+1)%n_t]+1} 無法連接"
                )
                continue
            if path_nodes and path_nodes[-1] == seg[0]:
                path_nodes.extend(seg[1:])
            else:
                path_nodes.extend(seg)

        waypoints = [from_meters(nodes[i], origin) for i in path_nodes]

    # ── 4b. 單向路線 ──────────────────────────────────────
    else:
        if start_idx is None or end_idx is None:
            return {"waypoints": [], "total_dist": 0.0, "is_loop": False,
                    "fruit_spots": [], "warnings": warnings + ["缺少起點或終點"],
                    "avoid_radius_m": avoid_radius_m, "max_dist_m": max_dist_m}
        _, path = _dijkstra_path(adj, start_idx, end_idx)
        if not path:
            return {"waypoints": [], "total_dist": 0.0, "is_loop": False,
                    "fruit_spots": [from_meters(s, origin) if s else None for s in fruit_spots_m],
                    "warnings": warnings + ["找不到安全路徑（嘗試增大 max_dist_m）"],
                    "avoid_radius_m": avoid_radius_m, "max_dist_m": max_dist_m}
        waypoints = [from_meters(nodes[i], origin) for i in path]

    total_dist = sum(haversine(waypoints[i], waypoints[i + 1])
                     for i in range(len(waypoints) - 1))
    fruit_spots = [from_meters(s, origin) if s is not None else None for s in fruit_spots_m]

    return {
        "waypoints":      waypoints,
        "total_dist":     total_dist,
        "is_loop":        is_loop,
        "fruit_spots":    fruit_spots,
        "warnings":       warnings,
        "avoid_radius_m": avoid_radius_m,
        "max_dist_m":     max_dist_m,
    }


def print_safe_fruit_result(flowers: List[Point], result: dict):
    waypoints   = result["waypoints"]
    fruit_spots = result["fruit_spots"]
    dist        = result["total_dist"]
    warnings    = result["warnings"]
    is_loop     = result["is_loop"]

    print("=" * 55)
    print("  🔒 種果安全路線規劃結果")
    print("=" * 55)
    print(f"  避開半徑：{result['avoid_radius_m']:.0f}m  "
          f"最大距離：{result['max_dist_m']:.0f}m  "
          f"{'循環' if is_loop else '單向'}")

    print(f"\n📍 花點與最佳種果點（共 {len(flowers)} 個）：")
    for i, (f, spot) in enumerate(zip(flowers, fruit_spots)):
        if spot:
            d = haversine(f, spot)
            print(f"   花點 {i+1:>2}  {f[0]:.8f}, {f[1]:.9f}")
            print(f"   種果點    {spot[0]:.8f}, {spot[1]:.9f}  （距花點 {d:.1f}m）")
        else:
            print(f"   花點 {i+1:>2}  {f[0]:.8f}, {f[1]:.9f}  ⚠️ 無安全種果點")

    if waypoints:
        print(f"\n🗺️  安全路線（共 {len(waypoints)} 個 waypoint）：")
        for i, pt in enumerate(waypoints):
            label = ""
            if i == 0:
                label = "（起點）"
            elif is_loop and i == len(waypoints) - 1:
                label = "（回起點）"
            print(f"   WP{i+1:03d}  {pt[0]:.8f}, {pt[1]:.9f}  {label}")
    else:
        print("\n❌ 未能生成路線")

    print(f"\n📊 統計：")
    print(f"   總距離：{dist:.1f} 公尺")
    print(f"   預估時間：{dist / WALK_SPEED_MPS / 60:.1f} 分鐘"
          f"（步行 {WALK_SPEED_MPS * 3.6:.1f} km/h）")

    if warnings:
        print("\n⚠️  警告：")
        for w in warnings:
            print(f"   {w}")
    print("\n" + "=" * 55)


if __name__ == "__main__":
    # ── 互動模式 ──────────────────────────────────────────
    flowers = parse_input()

    if len(flowers) < 2:
        print("花點不足，無法規劃路線。")
    else:
        print("\n⏳ 計算最佳路線中...\n")
        result = plan_route(flowers)
        print_result(flowers, result)

    # ── 也可直接呼叫 plan_route() 程式化使用 ──────────────
    # flowers = [
    #     (25.021056, 121.739472),
    #     (25.021278, 121.739500),
    #     (25.021500, 121.739600),
    # ]
    # result = plan_route(flowers)
    # print_result(flowers, result)