"""
斜線制限計算モジュール（建基法第56条・建基法施行令第132〜135条の12）

計算する制限の種類:
  1. 道路斜線制限   - 建基法56条1項1号（全用途地域）
  2. 隣地斜線制限   - 建基法56条1項2号（低層系以外で適用）
  3. 北側斜線制限   - 建基法56条1項3号（低層・中高層系で適用）
  4. 絶対高さ制限   - 建基法55条（第一・第二種低層住居専用地域）

参照: 建基法別表第3（道路斜線の勾配・適用距離）
      建基法56条1項2号（隣地斜線の起算高さ・勾配）
      建基法56条1項3号（北側斜線の起算高さ・勾配）
      建基法55条（低層住居専用地域の絶対高さ制限: 10m or 12m）

コトとワ。デザイン　長尾賢 一級建築士 第326774号・住宅医
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List


# ── 用途地域グループ ────────────────────────────────────────────────
_LOW_RISE    = frozenset({'第一種低層住居専用地域', '第二種低層住居専用地域'})
_MID_RISE    = frozenset({'第一種中高層住居専用地域', '第二種中高層住居専用地域'})
_RESIDENTIAL = frozenset({'第一種住居地域', '第二種住居地域', '準住居地域'})
_COMMERCIAL  = frozenset({'近隣商業地域', '商業地域', '準工業地域'})
_INDUSTRIAL  = frozenset({'工業地域', '工業専用地域'})


# ── 道路斜線制限テーブル（建基法別表第3） ────────────────────────────
# key: 用途地域, value: (勾配, 適用距離m)
# 勾配1.25 = 水平1mにつき高さ1.25m、勾配1.5 = 水平1mにつき高さ1.5m
_ROAD_TABLE: dict[str, tuple[float, float]] = {
    '第一種低層住居専用地域':   (1.25, 20.0),
    '第二種低層住居専用地域':   (1.25, 20.0),
    '第一種中高層住居専用地域': (1.25, 20.0),
    '第二種中高層住居専用地域': (1.25, 20.0),
    '第一種住居地域':           (1.25, 25.0),
    '第二種住居地域':           (1.25, 25.0),
    '準住居地域':               (1.25, 25.0),
    '近隣商業地域':             (1.5,  20.0),
    '商業地域':                 (1.5,  25.0),
    '準工業地域':               (1.5,  25.0),
    '工業地域':                 (1.5,  30.0),
    '工業専用地域':             (1.5,  30.0),
}
_ROAD_DEFAULT = (1.25, 25.0)  # 未登録地域のデフォルト


@dataclass
class SetbackPoint:
    """断面図描画用の（距離, 高さ）点"""
    dist_m: float      # 基準境界線からの水平距離 (m)
    height_m: float    # その点での最大建築高さ (m)


@dataclass
class SetbackLineResult:
    """3種類の斜線制限 + 絶対高さ制限の計算結果"""

    # ── 道路斜線制限 ──────────────────────────────────────────────
    road_slope: float                             # 勾配 (例: 1.25)
    road_applicable_dist: float                   # 適用距離 (m)
    road_points: List[SetbackPoint] = field(default_factory=list)
    # 道路斜線は全用途地域に適用

    # ── 隣地斜線制限 ──────────────────────────────────────────────
    adj_applicable: bool = False                  # 適用有無
    adj_base_h: float = 0.0                       # 起算高さ (m): 住居系20m / 商業系31m
    adj_slope: float = 0.0                        # 勾配: 住居系1.25 / 商業系2.5
    adj_points: List[SetbackPoint] = field(default_factory=list)

    # ── 北側斜線制限 ──────────────────────────────────────────────
    north_applicable: bool = False                # 適用有無
    north_base_h: float = 0.0                     # 起算高さ (m): 低層5m / 中高層10m
    north_slope: float = 1.25                     # 勾配 (常に1.25)
    north_points: List[SetbackPoint] = field(default_factory=list)
    # north_points の dist_m は「北側境界からの距離（南方向）」

    # ── 絶対高さ制限 ──────────────────────────────────────────────
    abs_height_limit: float = 0.0                 # 0 = 制限なし

    # ── 実効最大高さ（全制限の最小値） ────────────────────────────
    # 建物の前面(道路側)・後面(奥側)でのそれぞれの上限高さ
    effective_max_height_front: float = 0.0
    effective_max_height_rear: float = 0.0

    # ── 注記 ────────────────────────────────────────────────────
    notes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    # ── 境界ごとの実効最大高さ（ポリゴンモード時に設定） ─────────────
    per_boundary_limits: dict = field(default_factory=dict)
    # 例: {'front': 6.3, 'north': 7.8, 'side_l': 21.2, 'side_r': 21.2}

    # ── 突き当たり道路（外部からセット） ─────────────────────────────
    tsukiatari_direction: str = ''     # 突き当たり方向: 'west'/'east'/'south'/'north'
    tsukiatari_x_term: float = 0.0    # 入隅X座標（3D座標系、to3d変換後）


def calc_setback_lines(
    use_district: str,
    road_direction: str,
    road_width: float,
    site_area: float,
    building_width: float,
    building_depth: float,
    setback_front: float = 0.0,
    height_limit: float = 0.0,
    polygon_data=None,           # PolygonSiteData（ポリゴンモード時）
) -> SetbackLineResult:
    """
    斜線制限を計算して SetbackLineResult を返す。

    Parameters
    ----------
    use_district    : 用途地域（例: '第一種低層住居専用地域'）
    road_direction  : 接道方位（'南'/'北'/'東'/'西'）
    road_width      : 前面道路幅員 (m)
    site_area       : 敷地面積 (㎡)
    building_width  : 推奨建物間口 (m)  ← calculator.py の SiteResult から
    building_depth  : 推奨建物奥行き (m) ← calculator.py の SiteResult から
    setback_front   : 前面セットバック量 (m)
    height_limit    : 入力絶対高さ制限 (m, 0=なし)
    """
    notes: List[str] = []
    warnings: List[str] = []
    per_boundary_limits: dict = {}

    # 敷地の概算奥行き（ポリゴンモード時はより正確な値を使用）
    if polygon_data is not None:
        # ポリゴンの最大内接矩形から正確な建物配置を取得
        rect = polygon_data.inscribed_rect
        building_depth = rect.depth_m
        # 前面境界からの建物前面オフセット（南接道: Y座標が前面境界からの距離）
        setback_front = rect.y
        est_site_depth = site_area / max(building_width, 1.0)
    else:
        est_site_depth = site_area / max(building_width, 1.0)

    # ── 1. 道路斜線制限（建基法56条1項1号・別表第3） ──────────────────
    road_slope, road_app_dist = _ROAD_TABLE.get(use_district, _ROAD_DEFAULT)

    notes.append(
        f'【道路斜線制限】建基法56条1項1号・別表第3\n'
        f'  用途地域: {use_district}\n'
        f'  勾配 = 1:{road_slope:.2f}  適用距離 = {road_app_dist:.0f}m（道路反対側境界線から）\n'
        f'  算定式: H ≦ D × {road_slope:.2f}  （D: 前面道路の反対側の境界線からの水平距離）\n'
        f'  ※ 敷地境界線での高さ上限 = {road_width:.1f}m × {road_slope:.2f} = {road_width * road_slope:.2f}m\n'
        f'  参照: 国土交通省 建築基準法別表第3 い欄・ろ欄'
    )

    # road_points の dist_m = 道路の反対側境界線からの水平距離 D
    # H = D × slope  （D = road_width + 敷地内距離）
    road_points: List[SetbackPoint] = []
    D = 0.0
    while D <= road_app_dist + 0.5:
        road_points.append(SetbackPoint(D, D * road_slope))
        D += 0.5

    # ── 2. 隣地斜線制限（建基法56条1項2号） ────────────────────────────
    adj_applicable = True
    adj_base_h = 0.0
    adj_slope = 0.0
    adj_points: List[SetbackPoint] = []

    if use_district in _LOW_RISE:
        adj_applicable = False
        notes.append(
            '【隣地斜線制限】建基法56条1項2号\n'
            '  低層住居専用地域のため不適用\n'
            '  ※ 代わりに絶対高さ制限（建基法55条）が適用されます'
        )
    elif use_district in (_MID_RISE | _RESIDENTIAL):
        adj_applicable = True
        adj_base_h = 20.0
        adj_slope = 1.25
        notes.append(
            '【隣地斜線制限】建基法56条1項2号\n'
            f'  起算高さ = 20m  勾配 = 1:{adj_slope:.2f}\n'
            '  算定式: H ≦ 20 + d × 1.25  （d: 隣地境界線からの距離）'
        )
    else:  # 商業系・工業系
        adj_applicable = True
        adj_base_h = 31.0
        adj_slope = 2.5
        notes.append(
            '【隣地斜線制限】建基法56条1項2号\n'
            f'  起算高さ = 31m  勾配 = 1:{adj_slope:.2f}\n'
            '  算定式: H ≦ 31 + d × 2.5  （d: 隣地境界線からの距離）'
        )

    if adj_applicable:
        d = 0.0
        while d <= est_site_depth + 1.0:
            adj_points.append(SetbackPoint(d, adj_base_h + d * adj_slope))
            d += 0.5

    # ── 3. 北側斜線制限（建基法56条1項3号） ────────────────────────────
    north_applicable = False
    north_base_h = 0.0
    north_points: List[SetbackPoint] = []

    if use_district in _LOW_RISE:
        north_applicable = True
        north_base_h = 5.0
        notes.append(
            '【北側斜線制限】建基法56条1項3号\n'
            '  低層住居専用地域: 起算高さ = 5m  勾配 = 1:1.25\n'
            '  算定式: H ≦ 5 + x × 1.25  （x: 北側境界からの水平距離）\n'
            '  ※ 北側境界に建築する場合、最高高さは5m。南に離れるほど緩和される。'
        )
    elif use_district in _MID_RISE:
        north_applicable = True
        north_base_h = 10.0
        notes.append(
            '【北側斜線制限】建基法56条1項3号\n'
            '  中高層住居専用地域: 起算高さ = 10m  勾配 = 1:1.25\n'
            '  算定式: H ≦ 10 + x × 1.25  （x: 北側境界からの水平距離）'
        )

    if north_applicable:
        # north_points: x = 北側境界からの距離（南方向）
        x = 0.0
        while x <= est_site_depth + 1.0:
            north_points.append(SetbackPoint(x, north_base_h + x * 1.25))
            x += 0.5

    # ── 4. 絶対高さ制限（建基法55条・第一・第二種低層住居専用地域） ─────
    abs_h = height_limit
    if use_district in _LOW_RISE and abs_h == 0:
        abs_h = 10.0  # デフォルト10m（市町村指定で12mの地域あり）
        notes.append(
            '【絶対高さ制限】建基法55条\n'
            '  低層住居専用地域: 10m（都市計画で12m指定の地域あり）\n'
            '  ※ 地区計画・条例によって異なるため、市町村への事前確認を推奨'
        )
        warnings.append('絶対高さ制限10mを適用（高松市条例等は事前確認が必要）')

    # ── 5. 実効最大高さの算出 ────────────────────────────────────────
    # 建物前面（setback_front の位置）と後面（setback_front + building_depth）での上限
    front_dist_from_road = setback_front            # 道路境界からの距離（敷地内）
    rear_dist_from_road  = setback_front + building_depth

    # 道路斜線による高さ上限
    # D = road_width + 敷地境界からの距離（= 道路反対側境界からの総距離）
    D_front = road_width + front_dist_from_road
    D_rear  = road_width + rear_dist_from_road
    h_road_front = D_front * road_slope
    # 後面が適用距離を超える場合は道路斜線の制限なし
    h_road_rear  = D_rear * road_slope if D_rear <= road_app_dist else float('inf')

    # 北側斜線による高さ上限（南接道の場合: 建物後面が北境界に近い）
    # road_direction が '南' または '東'/'西' の場合は後面が北側に近い
    if north_applicable and road_direction in ('南', '東', '西'):
        # 北境界から建物後面・前面までの距離（x）
        x_rear  = max(0.0, est_site_depth - rear_dist_from_road)
        x_front = max(0.0, est_site_depth - front_dist_from_road)
        h_north_front = north_base_h + x_front * 1.25
        h_north_rear  = north_base_h + x_rear  * 1.25
    elif north_applicable and road_direction == '北':
        # 北接道: 北境界 = 道路境界、建物前面が北境界に近い
        x_front = front_dist_from_road   # 北境界（道路側）からの距離
        x_rear  = rear_dist_from_road
        h_north_front = north_base_h + x_front * 1.25
        h_north_rear  = north_base_h + x_rear  * 1.25
    else:
        h_north_front = float('inf')
        h_north_rear  = float('inf')

    # 絶対高さ制限
    h_abs = abs_h if abs_h > 0 else float('inf')

    # 前面高さの保護（セットバックなし=0mの場合、道路斜線=0になるが建物の壁はそこにない）
    eff_front = min(h_road_front, h_north_front, h_abs)
    eff_rear  = min(h_road_rear,  h_north_rear,  h_abs)

    if eff_front <= 0.0:
        eff_front = eff_rear  # 前面セットバック=0の場合は後面値を使用

    # ── 境界ごとの実効最大高さ（ポリゴンモード時） ──────────────────
    if polygon_data is not None:
        for b in polygon_data.boundaries:
            d_from_front = b.setback_m  # 境界からのセットバック量
            if b.direction == '前面':
                D = road_width + d_from_front  # 道路反対側境界からの距離
                h = min(D * road_slope, h_abs)
                per_boundary_limits['front'] = round(h, 2)
            elif b.direction == '北側':
                x = d_from_front  # 北境界からの距離
                h_n = (north_base_h + x * 1.25) if north_applicable else float('inf')
                per_boundary_limits['north'] = round(min(h_n, h_abs), 2)
            elif b.direction == '隣地左':
                h_a = (adj_base_h + d_from_front * adj_slope) if adj_applicable else float('inf')
                per_boundary_limits['side_l'] = round(min(h_a, h_abs), 2)
            elif b.direction == '隣地右':
                h_a = (adj_base_h + d_from_front * adj_slope) if adj_applicable else float('inf')
                per_boundary_limits['side_r'] = round(min(h_a, h_abs), 2)

    return SetbackLineResult(
        road_slope=road_slope,
        road_applicable_dist=road_app_dist,
        road_points=road_points,
        adj_applicable=adj_applicable,
        adj_base_h=adj_base_h,
        adj_slope=adj_slope,
        adj_points=adj_points,
        north_applicable=north_applicable,
        north_base_h=north_base_h,
        north_slope=1.25,
        north_points=north_points,
        abs_height_limit=abs_h,
        effective_max_height_front=round(eff_front, 2),
        effective_max_height_rear=round(eff_rear, 2),
        notes=notes,
        warnings=warnings,
        per_boundary_limits=per_boundary_limits,
    )
