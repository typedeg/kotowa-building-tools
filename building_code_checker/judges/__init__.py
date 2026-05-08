"""
建築法規チェックツール 共通型定義
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional
import re


# ── 和暦→西暦変換 ────────────────────────────────────────────────
_ERA_BASE = {
    "明治": 1868, "M": 1868,
    "大正": 1912, "T": 1912,
    "昭和": 1926, "S": 1926,
    "平成": 1989, "H": 1989,
    "令和": 2019, "R": 2019,
}

# 年月日あり: 昭和53年3月15日 / S53.3.15 / H5-3-15 / 令和5年3月15日
_PAT_FULL = re.compile(
    r"^(明治|大正|昭和|平成|令和|[MTSHRmtshr])(\d{1,2})[年.\-/](\d{1,2})[月.\-/](\d{1,2})日?$"
)
# 年のみ: 昭和53年 / S53 → 1月1日扱い
_PAT_YEAR = re.compile(
    r"^(明治|大正|昭和|平成|令和|[MTSHRmtshr])(\d{1,2})年?$"
)


def parse_date(s: str) -> date:
    """
    西暦（YYYY-MM-DD）または和暦文字列を date に変換する。
    解釈できない場合は ValueError を送出。

    対応形式:
      西暦: 1978-03-15
      和暦: 昭和53年3月15日 / 昭和53.3.15 / S53.3.15 / S53-3-15
            平成5年3月15日  / H5.3.15
            令和5年3月15日  / R5.3.15
      年のみ: 昭和53年 / S53  → その年の1月1日
    """
    s = s.strip()

    # 西暦 ISO形式
    try:
        return date.fromisoformat(s)
    except ValueError:
        pass

    # 和暦・年月日あり
    m = _PAT_FULL.match(s)
    if m:
        era, yr, mo, dy = m.groups()
        base = _ERA_BASE.get(era.upper()) or _ERA_BASE.get(era)
        if base:
            return date(base + int(yr) - 1, int(mo), int(dy))

    # 和暦・年のみ
    m = _PAT_YEAR.match(s)
    if m:
        era, yr = m.groups()
        base = _ERA_BASE.get(era.upper()) or _ERA_BASE.get(era)
        if base:
            return date(base + int(yr) - 1, 1, 1)

    raise ValueError(f"日付を解釈できません: {s}")


class Verdict(str, Enum):
    CONFORMING    = "適法"
    NONCONFORMING = "既存不適格"
    VIOLATION     = "違反"
    UNKNOWN       = "判定不能"


VERDICT_ICONS: dict[str, str] = {
    Verdict.CONFORMING:    "✅",
    Verdict.NONCONFORMING: "⚠️",
    Verdict.VIOLATION:     "❌",
    Verdict.UNKNOWN:       "❓",
}


@dataclass
class JudgeResult:
    """各判定モジュールの共通戻り値"""
    category: str
    verdict: Verdict
    law_reference: str
    summary: str
    details: list = field(default_factory=list)
    caution: Optional[str] = None
    recommendation: Optional[str] = None
    numeric: dict = field(default_factory=dict)
    table_rows: list = field(default_factory=list)  # 構造化テーブル行データ
    citation_text: Optional[str] = None              # 根拠条文テキスト（MCP Phase 2）


@dataclass
class BuildingData:
    """
    入力データ構造。すべてOptionalのため部分入力でも動作する。
    """
    # 基本情報
    address: Optional[str] = None
    owner_name: Optional[str] = None

    # 確認申請関連
    confirmation_date: Optional[str] = None   # "YYYY-MM-DD"

    # 構造・規模
    structure_type: Optional[str] = None      # 木造 / 鉄骨 / RC / その他
    stories: Optional[int] = None

    # 面積関係（m²）
    site_area: Optional[float] = None
    building_area: Optional[float] = None
    total_floor_area: Optional[float] = None
    existing_floor_area: Optional[float] = None  # 増改築時の既存部分床面積
    renovation_area: Optional[float] = None      # 増改築予定面積

    # 用途地域・規制値
    use_district: Optional[str] = None
    bcr_limit: Optional[float] = None         # 建ぺい率制限（%）
    far_limit: Optional[float] = None         # 容積率制限（%）

    # 接道
    road_width: Optional[float] = None        # 前面道路幅員（m）
    road_type: Optional[str] = None           # 42条1項 / 42条2項 / 位置指定道路 等
    contact_length: Optional[float] = None    # 接道長さ（m）

    # 用途
    building_use: Optional[str] = None

    # 省エネ関連（R7年4月義務化対応）
    climate_region: Optional[int] = None        # 地域区分 1〜8
    ua_value: Optional[float] = None            # 外皮平均熱貫流率 U_A [W/(m²·K)]
    eta_ac_value: Optional[float] = None        # 冷房期平均日射熱取得率 η_AC [-]
    bei: Optional[float] = None                 # 一次エネルギー消費量指標 BEI [-]
    is_new_construction: Optional[bool] = None  # True=新築, False=増改築
    is_climate_adapted: Optional[bool] = None   # 気候風土適応住宅（外皮基準除外対象）

    # 基礎形式（令38条・R7.4無筋禁止）
    foundation_type: Optional[str] = None       # 無筋コンクリート/布基礎（有筋）/ベタ基礎/玉石 等

    # 防火規制（法61条・62条・法22条）
    fire_zone: Optional[str] = None             # 防火地域/準防火地域/法22条区域/指定なし
    fire_resistance: Optional[str] = None       # 耐火建築物/準耐火建築物/その他

    # 用途変更計画（法48条・87条）
    planned_use: Optional[str] = None           # 用途変更計画がある場合の計画用途

    # 居住性能（法28条・28条の2・令116条の2）
    has_24h_ventilation: Optional[bool] = None        # 24時間換気設備あり=True/なし=False
    max_room_area: Optional[float] = None             # 最大居室面積 m²（採光チェック用）
    effective_daylight_area: Optional[float] = None   # 有効採光面積 m²（令19条算定値）
