"""
省エネ基準定数テーブル
建築物省エネ法（R7年4月施行・改正建築物省エネ法）

出典:
  国土交通省「省エネ基準適合義務制度の解説【第二版】」(001852347.pdf)
  R7年度省エネ基準適合義務制度対応版
"""
from __future__ import annotations
from datetime import date

# ─── 住宅の外皮性能基準 ────────────────────────────────────────────────────

# UA値（外皮平均熱貫流率）基準値 [W/(m²·K)]
# 地域区分1〜8 → None は基準なし（8地域＝沖縄等）
UA_STANDARD: dict[int, float | None] = {
    1: 0.46,
    2: 0.46,
    3: 0.56,
    4: 0.75,
    5: 0.87,
    6: 0.87,
    7: 0.87,
    8: None,
}

# ZEH水準のUA値目標 [W/(m²·K)]（2030年以降の誘導目標）
UA_ZEH: dict[int, float | None] = {
    1: 0.40,
    2: 0.40,
    3: 0.50,
    4: 0.60,
    5: 0.60,
    6: 0.60,
    7: 0.60,
    8: None,
}

# ηAC値（冷房期の平均日射熱取得率）基準値 [-]
# 地域区分1〜4 は基準なし（None）
ETA_AC_STANDARD: dict[int, float | None] = {
    1: None,
    2: None,
    3: None,
    4: None,
    5: 3.0,
    6: 2.8,
    7: 2.7,
    8: 6.7,
}

# ─── 一次エネルギー消費量基準（BEI） ────────────────────────────────────────

# 住宅のBEI基準値（義務基準）
BEI_RESIDENTIAL_MANDATORY = 1.0

# 住宅の誘導基準（ZEH水準）
BEI_RESIDENTIAL_GUIDED = 0.8

# 非住宅BEI基準値（大規模：2,000㎡以上、2024年4月施行済み）
# 用途カテゴリ: 工場等 / 事務所・学校・ホテル等 / 病院・飲食店・集会所等
BEI_NONRESIDENTIAL_LARGE: dict[str, float] = {
    "工場等":                         0.75,
    "事務所等・学校等・ホテル等・百貨店等": 0.80,
    "病院等・飲食店等・集会所等":       0.85,
}

# 非住宅BEI基準値（小・中規模：300〜2,000㎡未満・300㎡未満）
# 中規模は2026年4月以降に大規模と同水準への引上げ予定
BEI_NONRESIDENTIAL_STANDARD = 1.0

# 規模区分の閾値（延べ床面積 m²）
SCALE_LARGE_THRESHOLD  = 2000.0   # 大規模（BEI引上げ済）
SCALE_MEDIUM_THRESHOLD = 300.0    # 中規模（2026/4予定）

# ─── 義務化施行日 ─────────────────────────────────────────────────────────

# 省エネ基準適合義務制度（着工ベース）
OBLIGATION_EFFECTIVE_DATE = date(2025, 4, 1)

# 非住宅大規模BEI引上げ施行日
BEI_LARGE_SCALE_EFFECTIVE_DATE = date(2024, 4, 1)

# 非住宅中規模BEI引上げ予定日（未施行）
BEI_MEDIUM_SCALE_PLANNED_DATE = date(2026, 4, 1)

# 気候風土適応住宅の外皮基準恒久除外施行日
CLIMATE_ADAPTED_EFFECTIVE_DATE = date(2024, 6, 28)

# ─── 主要都市の地域区分 ──────────────────────────────────────────────────

# 代表的な市区町村の地域区分（参考値）
CITY_CLIMATE_REGION: dict[str, int] = {
    "高松市":    6,  # 香川県
    "丸亀市":    6,  # 香川県
    "観音寺市":  6,  # 香川県
    "さぬき市":  6,  # 香川県
    "東かがわ市": 6,  # 香川県
    "三豊市":    6,  # 香川県
    "札幌市":    2,
    "仙台市":    3,
    "東京都":    6,
    "横浜市":    6,
    "名古屋市":  5,
    "大阪市":    6,
    "京都市":    5,
    "神戸市":    6,
    "広島市":    6,
    "福岡市":    6,
    "那覇市":    8,
}

DEFAULT_CLIMATE_REGION = 6  # 高松市（コトとワ。デザインの活動拠点）

# ─── ユーティリティ ──────────────────────────────────────────────────────


def get_ua_standard(region: int) -> float | None:
    """地域区分からU_A値基準を取得。"""
    return UA_STANDARD.get(region)


def get_eta_ac_standard(region: int) -> float | None:
    """地域区分からη_AC値基準を取得。"""
    return ETA_AC_STANDARD.get(region)


def get_ua_zeh(region: int) -> float | None:
    """地域区分からZEH水準U_A値を取得。"""
    return UA_ZEH.get(region)


def get_nonresidential_bei(floor_area_m2: float, use_category: str | None = None) -> float:
    """
    非住宅の適用BEI基準値を返す。
    - 大規模（2,000㎡以上）かつ use_category が指定された場合は用途別基準値
    - それ以外は 1.0
    注意: 中規模BEI引上げは未施行のため、現時点では1.0を返す。
    """
    if floor_area_m2 >= SCALE_LARGE_THRESHOLD and use_category:
        for key, val in BEI_NONRESIDENTIAL_LARGE.items():
            if use_category in key or key in use_category:
                return val
    return BEI_NONRESIDENTIAL_STANDARD


def get_nonresidential_scale(floor_area_m2: float) -> str:
    """非住宅の規模区分（大規模/中規模/小規模）を返す。"""
    if floor_area_m2 >= SCALE_LARGE_THRESHOLD:
        return "大規模（2,000㎡以上）"
    elif floor_area_m2 >= SCALE_MEDIUM_THRESHOLD:
        return "中規模（300〜2,000㎡未満）"
    else:
        return "小規模（300㎡未満）"


def region_label(region: int) -> str:
    """地域区分の表示用ラベルを返す。"""
    labels = {
        1: "1地域（北海道北部）",
        2: "2地域（北海道）",
        3: "3地域（東北・高冷地）",
        4: "4地域（関東・東海）",
        5: "5地域（近畿・東海南部）",
        6: "6地域（九州・四国・近畿南部）",
        7: "7地域（沖縄以外の温暖地）",
        8: "8地域（沖縄）",
    }
    return labels.get(region, f"{region}地域")
