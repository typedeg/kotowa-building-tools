"""
敷地・法規計算モジュール
建蔽率・容積率・接道義務・セットバックを計算し、建築可能ゾーンを算出する

ポリゴンモード（site_polygon 指定時）:
  shapely + polygon_site.py を使ってセットバック後の建築可能ゾーンと
  最大内接矩形（建物配置）を正確に計算する。
  shapely 未インストール時は矩形計算にフォールバックする（graceful degradation）。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, List, Optional
import math
import os as _os
import sys as _sys

# mcp_bridge パッケージをパスに追加（1回のみ）
_MCP_BRIDGE_PATH = _os.path.join(_os.path.dirname(__file__), '..', 'mcp_bridge')
if _MCP_BRIDGE_PATH not in _sys.path:
    _sys.path.insert(0, _MCP_BRIDGE_PATH)

try:
    from citation_verifier import get_citations_for_checks as _get_citations
except Exception:
    _get_citations = None

TATAMI = 1.62  # 1畳 = 1.62㎡（京間）


@dataclass
class SiteInput:
    """入力：敷地・法規条件"""
    site_area: float            # 敷地面積 (㎡)
    coverage_ratio: float       # 建蔽率 (%)
    floor_area_ratio: float     # 容積率 (%)
    road_direction: str         # 接道方位: 南/北/東/西
    road_width: float = 4.0     # 前面道路幅員 (m)
    fire_zone: str = 'なし'     # なし/準防火/防火
    site_shape: str = '矩形'    # 矩形/L字/旗竿/その他
    setback_front: float = 0.0  # 前面セットバック (m)
    height_limit: float = 0.0   # 高さ制限 (m, 0=制限なし)
    use_district: str = '第一種低層住居専用地域'
    # ── ポリゴンモード（省略時は矩形計算） ──────────────────────────
    site_polygon: Optional[list] = None   # [[x,y],...] 頂点座標リスト (m)
    setback_north: float = 0.5            # 北側セットバック (m)
    setback_side_l: float = 0.5          # 隣地左セットバック (m)
    setback_side_r: float = 0.5          # 隣地右セットバック (m)
    tsukiatari: Optional[dict] = None     # 突き当たり道路 {"direction":"west","terminus_x":4.53}
    climate_region: int = 6               # 省エネ地域区分 1〜8（デフォルト: 6地域・高松市）
    setback_exterior_wall: float = 0.0    # 外壁後退距離制限 (m, 0=指定なし)【建基法54条】


@dataclass
class OwnerInput:
    """入力：施主要望"""
    ldk_tatami: float = 20.0        # LDK (畳)
    num_rooms: int = 3              # 居室数（LDKを除く）
    room_tatami: float = 0.0        # 各居室の畳数（0=自動: 6畳）
    master_tatami: float = 0.0      # 主寝室の畳数（0=自動: 8畳）
    water_placement: str = 'おまかせ'  # 1F北/1F南/おまかせ
    parking: int = 1                # 駐車台数
    family: str = '夫婦+子2人'
    budget: str = '未定'
    has_washitsu: bool = False       # 和室希望
    has_pantry: bool = False         # パントリー希望


@dataclass
class CheckItem:
    """法規チェック項目"""
    item: str
    limit: str
    calc: str
    ok: bool
    note: str = ''
    law_ref: str = ''                    # 根拠条文キー（例: "建基法53条"）
    citation_text: Optional[str] = None  # 条文テキスト（citation_verifier が設定）


@dataclass
class SiteResult:
    """計算結果：敷地・法規"""
    # 法規上限
    max_building_area: float        # 最大建築面積 (㎡)
    max_floor_area: float           # 最大延床面積 (㎡)
    actual_far: float               # 実効容積率 (%)
    # 有効敷地
    effective_site_area: float      # セットバック後の有効面積
    # 推奨値
    recommended_building_area: float
    recommended_floors: int
    building_width: float           # 推奨建物幅員 (m)
    building_depth: float           # 推奨建物奥行き (m)
    # 必要面積
    required_floor_area: float
    room_areas: dict = field(default_factory=dict)  # 各室の推奨面積
    # 法規チェック
    checks: List[CheckItem] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    # ── ポリゴンモード拡張フィールド ────────────────────────────────
    polygon_data: Optional[Any] = None        # PolygonSiteData（ポリゴン時のみセット）
    buildable_zone_area: float = 0.0          # 建築可能ゾーン面積 (㎡)
    building_offset_x: float = 0.0           # 推奨建物の敷地原点からのXオフセット (m)
    building_offset_y: float = 0.0           # 推奨建物の敷地原点からのYオフセット (m)
    calculation_mode: str = 'rectangular'    # 'rectangular' or 'polygon'
    # ── 省エネ基準（R7年4月義務化） ─────────────────────────────────────
    energy_region: int = 6                      # 適用地域区分
    energy_region_label: str = '6地域（九州・四国・近畿南部）'
    ua_standard: Optional[float] = None         # U_A値義務基準 [W/(m²·K)]
    ua_zeh: Optional[float] = None              # U_A値ZEH水準 [W/(m²·K)]
    eta_ac_standard: Optional[float] = None     # η_AC値義務基準
    bei_mandatory: float = 1.0                  # BEI義務基準


def calculate(site: SiteInput, req: OwnerInput) -> SiteResult:
    """敷地・法規の全計算を実行する"""
    warnings: List[str] = []
    checks: List[CheckItem] = []
    polygon_data = None
    calculation_mode = 'rectangular'
    buildable_zone_area = 0.0
    building_offset_x = 0.0
    building_offset_y = 0.0
    polygon_building_width: Optional[float] = None
    polygon_building_depth: Optional[float] = None

    # ── 0. ポリゴンモード分岐 ────────────────────────────────────────
    if site.site_polygon:
        try:
            from polygon_site import analyze_polygon_site
            setbacks = {
                'front':  site.setback_front,
                'north':  site.setback_north,
                'side_l': site.setback_side_l,
                'side_r': site.setback_side_r,
            }
            polygon_data = analyze_polygon_site(
                site.site_polygon,
                site.road_direction,
                setbacks,
            )
            calculation_mode = 'polygon'
            buildable_zone_area = polygon_data.buildable_area_m2
            building_offset_x = polygon_data.inscribed_rect.x
            building_offset_y = polygon_data.inscribed_rect.y
            polygon_building_width = polygon_data.inscribed_rect.width_m
            polygon_building_depth = polygon_data.inscribed_rect.depth_m
            warnings.append(
                f'ポリゴン計算モード: 敷地面積（実測）{polygon_data.area_m2:.1f}㎡ / '
                f'建築可能ゾーン {buildable_zone_area:.1f}㎡'
            )
        except ImportError:
            warnings.append('shapely 未インストール → 矩形計算で代替（pip3 install shapely で有効化）')
        except Exception as e:
            warnings.append(f'ポリゴン計算エラー（矩形計算で代替）: {e}')

    # ── 1. セットバック後の有効面積 ────────────────────────────────
    if site.setback_front > 0:
        # 敷地幅 ≒ √(面積 × 0.7) で概算（矩形仮定）
        approx_width = math.sqrt(site.site_area * 0.7)
        sb_area = approx_width * site.setback_front
        effective_area = max(site.site_area - sb_area, site.site_area * 0.75)
        warnings.append(
            f"前面セットバック {site.setback_front}m 適用 → "
            f"有効面積 {effective_area:.1f}㎡（元 {site.site_area:.1f}㎡）"
        )
    else:
        effective_area = site.site_area

    # ── 2. 前面道路による容積率制限（建基法52条第2項） ──────────────
    # 住居系用途地域: 道路幅員 × 4/10
    if '工業' in site.use_district or '商業' in site.use_district:
        far_coeff = 6  # 非住居系: ×6/10
    else:
        far_coeff = 4  # 住居系: ×4/10
    far_by_road = site.road_width * far_coeff * 10  # → %に変換

    if far_by_road < site.floor_area_ratio:
        actual_far = far_by_road
        warnings.append(
            f"前面道路幅員 {site.road_width}m により容積率は "
            f"{actual_far:.0f}% に制限（指定 {site.floor_area_ratio:.0f}%）"
        )
    else:
        actual_far = site.floor_area_ratio

    # ── 3. 法規上限面積 ─────────────────────────────────────────────
    max_building_area = effective_area * site.coverage_ratio / 100
    max_floor_area = effective_area * actual_far / 100

    # ── 4. 必要延床面積の推計 ───────────────────────────────────────
    ldk_m2 = req.ldk_tatami * TATAMI
    master_m2 = (req.master_tatami if req.master_tatami > 0 else 8) * TATAMI
    room_tatami = req.room_tatami if req.room_tatami > 0 else 6
    other_rooms_m2 = max(0, req.num_rooms - 1) * room_tatami * TATAMI
    washitsu_m2 = 6 * TATAMI if req.has_washitsu else 0

    bath_m2 = 3.31     # 浴室（1坪）
    wash_m2 = 3.31     # 洗面室
    toilet1_m2 = 1.65  # トイレ1
    toilet2_m2 = 1.65  # トイレ2（2階）
    entrance_m2 = 3.31 # 玄関
    hall_m2 = 3.31     # ホール
    pantry_m2 = 2.0 if req.has_pantry else 0
    stair_m2 = 6.0     # 階段室（2階建て前提）
    closet_m2 = master_m2 * 0.25  # クロゼット（主寝室面積の25%）

    required_floor_area = (
        ldk_m2 + master_m2 + other_rooms_m2 + washitsu_m2
        + bath_m2 + wash_m2 + toilet1_m2 + toilet2_m2
        + entrance_m2 + hall_m2 + pantry_m2
        + stair_m2 + closet_m2
    )

    # ── 5. 推奨階数・建築面積 ───────────────────────────────────────
    if max_building_area >= required_floor_area * 0.95:
        floors = 1
        stair_m2 = 0  # 1階建てなので不要
        toilet2_m2 = 0
        required_floor_area -= (stair_m2 + toilet2_m2)
    elif max_building_area * 2 >= required_floor_area:
        floors = 2
    else:
        floors = 3

    # 推奨建築面積（法規上限の90%以内で必要面積を満たす最小値）
    rec_building_area = min(
        max_building_area * 0.90,
        math.ceil(required_floor_area / floors * 1.05 * 2) / 2  # 0.5㎡刻み
    )

    # ── 6. 建物寸法（間口:奥行き = 1:1.4 で矩形仮定） ───────────────
    aspect = 1.4
    w_raw = math.sqrt(rec_building_area / aspect)
    d_raw = rec_building_area / w_raw
    # 910mmモジュール（尺モジュール）に丸める
    building_width = round(w_raw / 0.91) * 0.91
    building_depth = round(d_raw / 0.91) * 0.91

    # ── 6b. ポリゴンモード：最大内接矩形で建物寸法を上書き ─────────
    if polygon_building_width is not None and polygon_building_depth is not None:
        building_width = polygon_building_width
        building_depth = polygon_building_depth
        rec_building_area = min(
            building_width * building_depth,
            max_building_area * 0.90
        )

    # ── 7. 法規チェック ─────────────────────────────────────────────
    bcr_actual = rec_building_area / effective_area * 100
    checks.append(CheckItem(
        item='建蔽率',
        limit=f"{site.coverage_ratio:.0f}%",
        calc=f"{rec_building_area:.1f}㎡ ÷ {effective_area:.1f}㎡ = {bcr_actual:.1f}%",
        ok=rec_building_area <= max_building_area,
        note='防火地域の耐火建築物は+10%緩和あり' if site.fire_zone == '防火' else '',
        law_ref='建基法53条',
    ))

    far_actual = required_floor_area / effective_area * 100
    _far_ref = '建基法52条2項' if far_by_road < site.floor_area_ratio else '建基法52条'
    checks.append(CheckItem(
        item='容積率',
        limit=f"{actual_far:.0f}%",
        calc=f"{required_floor_area:.1f}㎡ ÷ {effective_area:.1f}㎡ = {far_actual:.1f}%",
        ok=required_floor_area <= max_floor_area,
        note='車庫は延床の1/5まで容積率不算入',
        law_ref=_far_ref,
    ))

    checks.append(CheckItem(
        item='接道義務（建基法43条）',
        limit='前面道路幅員 4m 以上',
        calc=f"前面道路幅員 {site.road_width}m",
        ok=site.road_width >= 4.0,
        note='' if site.road_width >= 4.0 else f'セットバック要（{(4.0 - site.road_width) / 2:.2f}m）',
        law_ref='建基法43条',
    ))

    # ── 採光（建基法28条・令19条）──────────────────────────────────────
    # 居室の有効採光面積 ≥ 床面積 × 1/7（採光補正係数は設計時に算定）
    _daylight_rooms: list = [('LDK', ldk_m2), ('主寝室', master_m2)]
    if req.num_rooms > 1:
        _daylight_rooms.append((f'居室（×{req.num_rooms - 1}室）', room_tatami * TATAMI))
    for _room_name, _room_m2 in _daylight_rooms:
        _req_area = _room_m2 / 7
        checks.append(CheckItem(
            item=f'採光：{_room_name}',
            limit=f'床面積×1/7 = {_req_area:.2f}㎡以上',
            calc=f'居室面積 {_room_m2:.1f}㎡（採光補正係数は設計時に算定）',
            ok=True,
            note='採光補正係数（令19条）は窓位置・隣地距離により変動。設計時に確認要',
            law_ref='建基法28条・令19条',
        ))

    # ── 外壁後退距離（建基法54条）────────────────────────────────────
    # 第一・第二種低層住居専用地域で都市計画が指定する場合のみ適用
    if site.setback_exterior_wall > 0:
        ew_ok = site.setback_front >= site.setback_exterior_wall
        checks.append(CheckItem(
            item='外壁後退距離（建基法54条）',
            limit=f'{site.setback_exterior_wall:.1f}m以上',
            calc=f'前面セットバック {site.setback_front:.1f}m',
            ok=ew_ok,
            note='' if ew_ok else f'外壁後退が {site.setback_exterior_wall:.1f}m 未満のため要確認',
            law_ref='建基法54条',
        ))

    # ── 8. 各室面積まとめ ────────────────────────────────────────────
    room_areas = {
        'LDK': ldk_m2,
        '主寝室': master_m2,
        '各居室': room_tatami * TATAMI,
        '居室数': req.num_rooms,
        '浴室': bath_m2,
        '洗面室': wash_m2,
        'トイレ①': toilet1_m2,
        'トイレ②': toilet2_m2,
        '玄関': entrance_m2,
        'ホール': hall_m2,
        'クロゼット': closet_m2,
    }
    if req.has_washitsu:
        room_areas['和室'] = washitsu_m2
    if req.has_pantry:
        room_areas['パントリー'] = pantry_m2

    # ── 9. 条文引用テキストを付加（MCP Phase 2 / Graceful Degradation） ────
    if _get_citations is not None:
        try:
            _get_citations(checks)
        except Exception:
            pass

    # ── 10. 省エネ基準値の取得（R7年4月義務化） ──────────────────────────
    try:
        _es_path = _os.path.join(_os.path.dirname(__file__), '..', 'building-code-checker')
        if _es_path not in _sys.path:
            _sys.path.insert(0, _es_path)
        from judges.energy_standards import (
            get_ua_standard, get_ua_zeh, get_eta_ac_standard,
            region_label, BEI_RESIDENTIAL_MANDATORY,
        )
        _region = site.climate_region
        _ua_std = get_ua_standard(_region)
        _ua_zeh = get_ua_zeh(_region)
        _eta_std = get_eta_ac_standard(_region)
        _region_label = region_label(_region)
        _energy_fields = dict(
            energy_region=_region,
            energy_region_label=_region_label,
            ua_standard=_ua_std,
            ua_zeh=_ua_zeh,
            eta_ac_standard=_eta_std,
            bei_mandatory=BEI_RESIDENTIAL_MANDATORY,
        )
    except Exception:
        _energy_fields = {}

    return SiteResult(
        max_building_area=round(max_building_area, 2),
        max_floor_area=round(max_floor_area, 2),
        actual_far=actual_far,
        effective_site_area=round(effective_area, 2),
        recommended_building_area=round(rec_building_area, 2),
        recommended_floors=floors,
        building_width=round(building_width, 2),
        building_depth=round(building_depth, 2),
        required_floor_area=round(required_floor_area, 2),
        room_areas=room_areas,
        checks=checks,
        warnings=warnings,
        polygon_data=polygon_data,
        buildable_zone_area=round(buildable_zone_area, 2),
        building_offset_x=round(building_offset_x, 3),
        building_offset_y=round(building_offset_y, 3),
        calculation_mode=calculation_mode,
        **_energy_fields,
    )
