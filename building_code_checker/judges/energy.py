"""
省エネ基準適合義務 判定モジュール
建築物省エネ法（R7年4月施行・改正建築物省エネ法）

判定対象：
  新築・増改築時の省エネ基準適合義務（住宅・非住宅）
  気候風土適応住宅の外皮基準除外
  非住宅大規模BEI引上げ（2024年4月施行済み）

出典:
  国土交通省「省エネ基準適合義務制度の解説【第二版】」(001852347.pdf)
"""
from __future__ import annotations
from datetime import date
from typing import TYPE_CHECKING

from judges import JudgeResult, Verdict, VERDICT_ICONS
from judges.energy_standards import (
    get_ua_standard, get_eta_ac_standard, get_ua_zeh,
    get_nonresidential_bei, get_nonresidential_scale, region_label,
    DEFAULT_CLIMATE_REGION,
    OBLIGATION_EFFECTIVE_DATE,
    BEI_RESIDENTIAL_MANDATORY, BEI_RESIDENTIAL_GUIDED,
    UA_STANDARD, UA_ZEH, ETA_AC_STANDARD,
    BEI_LARGE_SCALE_EFFECTIVE_DATE,
    CLIMATE_ADAPTED_EFFECTIVE_DATE,
    BEI_MEDIUM_SCALE_PLANNED_DATE,
)

if TYPE_CHECKING:
    from judges import BuildingData


def judge(data: "BuildingData") -> JudgeResult:
    """
    省エネ基準適合義務を判定する。

    対象：
      - 2025年4月以降に着工する新築・増改築
      - 修繕・模様替え（リフォーム）は対象外

    戻り値：
      ✅ 適法      … 基準を満たす、または義務対象外
      ⚠️ 既存不適格 … 既存建築物の省エネ性能が基準未満（法改正前建設）
      ❌ 違反      … 義務対象の新築で基準未達
      ❓ 判定不能   … 必須データ不足
    """
    today = date.today()

    # ─── 地域区分の確定 ────────────────────────────────────────────
    region = data.climate_region if data.climate_region else DEFAULT_CLIMATE_REGION
    region_str = region_label(region)

    # ─── 気候風土適応住宅の除外判定 ──────────────────────────────────
    if data.is_climate_adapted:
        return JudgeResult(
            category="省エネ基準適合義務",
            verdict=Verdict.CONFORMING,
            law_reference="建築物省エネ法 第11条・附則 / 2024年6月28日改正",
            summary="気候風土適応住宅 ─ 外皮基準の適用除外（恒久化）",
            details=[
                "2024年6月28日施行の改正により外皮基準の適用除外が恒久化されました。",
                "要件：茅葺き屋根・面戸板現し・せがい造り等の地域固有の伝統的構法を用いるもの。",
                "一次エネルギー消費量基準（BEI）の遵守は引き続き必要です。",
            ],
            caution="BEI（一次エネルギー消費量指標）の基準適合は引き続き義務があります。",
            numeric={"地域区分": region, "外皮基準": "適用除外"},
        )

    # ─── 建物用途の判定（住宅/非住宅）──────────────────────────────
    building_use = data.building_use or ""
    is_residential = _is_residential(building_use)

    # ─── 新築/増改築フラグ ─────────────────────────────────────────
    is_new = data.is_new_construction  # True=新築, False=増改築, None=不明

    # ─── 既存建築物（確認日が古い場合）の省エネ既存不適格チェック ─────
    if data.confirmation_date and is_new is not True:
        try:
            from judges import parse_date
            conf_date = parse_date(data.confirmation_date)
            if conf_date < OBLIGATION_EFFECTIVE_DATE:
                return _existing_building_result(data, region, region_str, is_residential, conf_date)
        except ValueError:
            pass

    # ─── 義務対象外チェック（修繕・模様替え等）───────────────────────
    # 増改築の場合のみ renovation_area チェック（新築は常に義務対象）
    if is_new is False and not data.renovation_area:
        return JudgeResult(
            category="省エネ基準適合義務",
            verdict=Verdict.CONFORMING,
            law_reference="建築物省エネ法 第11条",
            summary="修繕・模様替えのため省エネ基準適合義務の対象外",
            details=[
                "修繕・模様替え（リフォーム）は省エネ基準適合義務の対象外です。",
                "増改築の場合は増改築部分のみが対象となります（建物全体ではありません）。",
            ],
            numeric={"地域区分": region},
        )

    # ─── 住宅の省エネ基準判定 ─────────────────────────────────────
    if is_residential:
        return _judge_residential(data, region, region_str, is_new)
    else:
        return _judge_nonresidential(data, region, region_str, is_new)


def _is_residential(building_use: str) -> bool:
    """建物用途が住宅系かどうかを判定。"""
    non_residential_keywords = ["事務所", "店舗", "工場", "倉庫", "病院", "学校",
                                  "ホテル", "飲食", "集会", "百貨店", "旅館"]
    return not any(kw in building_use for kw in non_residential_keywords)


def _judge_residential(data: "BuildingData", region: int, region_str: str,
                        is_new) -> JudgeResult:
    """住宅の省エネ基準判定。"""
    ua_std = get_ua_standard(region)
    eta_std = get_eta_ac_standard(region)
    ua_zeh = get_ua_zeh(region)

    details = [
        f"適用地域区分: {region_str}",
        f"U_A値基準: {ua_std} W/(m²·K)（ZEH水準: {ua_zeh} W/(m²·K)）" if ua_std else "U_A値基準: なし（8地域）",
        f"η_AC値基準: {eta_std}（冷房期平均日射熱取得率）" if eta_std else "η_AC値基準: なし（1〜4地域）",
        f"BEI義務基準: {BEI_RESIDENTIAL_MANDATORY}（ZEH誘導基準: {BEI_RESIDENTIAL_GUIDED}）",
    ]

    numeric = {
        "地域区分": region,
        "U_A値基準": ua_std,
        "η_AC値基準": eta_std,
        "BEI義務基準": BEI_RESIDENTIAL_MANDATORY,
    }

    # U_A値の実測値がある場合は比較
    ua_input = data.ua_value
    bei_input = data.bei

    verdict = Verdict.UNKNOWN
    summary_parts = []
    caution = None

    if ua_input is not None and ua_std is not None:
        numeric["U_A値（入力）"] = ua_input
        if ua_input <= ua_std:
            summary_parts.append(f"U_A値 {ua_input} ≦ 基準 {ua_std} ✅")
            if ua_input <= ua_zeh:
                summary_parts.append(f"ZEH水準 {ua_zeh} も達成 ✅")
        else:
            summary_parts.append(f"U_A値 {ua_input} > 基準 {ua_std} ❌")

    if bei_input is not None:
        numeric["BEI（入力）"] = bei_input
        if bei_input <= BEI_RESIDENTIAL_MANDATORY:
            summary_parts.append(f"BEI {bei_input} ≦ 義務基準 {BEI_RESIDENTIAL_MANDATORY} ✅")
        else:
            summary_parts.append(f"BEI {bei_input} > 義務基準 {BEI_RESIDENTIAL_MANDATORY} ❌")

    # 判定値なし → UNKNOWN、値あり → 比較結果で判定
    if not summary_parts:
        verdict = Verdict.UNKNOWN
        summary = f"住宅省エネ基準 ─ {region_str} の基準値を参照（実測値未入力）"
        caution = "U_A値・BEI値を入力すると詳細な適合判定ができます。"
    else:
        # 少なくとも1項目でNG判定があるか確認
        all_ok = all("❌" not in s for s in summary_parts)
        if all_ok:
            verdict = Verdict.CONFORMING
            summary = f"住宅省エネ基準 ─ 適合 ({'; '.join(summary_parts)})"
        else:
            verdict = Verdict.VIOLATION if is_new else Verdict.NONCONFORMING
            summary = f"住宅省エネ基準 ─ 不適合 ({'; '.join(summary_parts)})"
            caution = (
                "2025年4月以降の新築は省エネ基準適合が義務です。確認申請時に省エネ計算書の提出が必要です。"
                if is_new else
                "増改築部分は省エネ基準への適合が必要です。"
            )

    return JudgeResult(
        category="省エネ基準適合義務",
        verdict=verdict,
        law_reference="建築物省エネ法 第11条・第12条 / 建築基準法第6条連携",
        summary=summary,
        details=details,
        caution=caution,
        recommendation=(
            "省エネ適判不要の条件：①仕様基準評価 ②設計住宅性能評価（断熱等級4以上かつ一次エネ等級4以上）"
            " ③長期優良住宅認定。いずれかに該当する場合は省エネ適合性判定は不要です。"
        ),
        numeric=numeric,
    )


def _judge_nonresidential(data: "BuildingData", region: int, region_str: str,
                           is_new) -> JudgeResult:
    """非住宅の省エネ基準判定（BEIのみ対象）。"""
    floor_area = data.total_floor_area or 0.0
    scale = get_nonresidential_scale(floor_area)
    bei_std = get_nonresidential_bei(floor_area, data.building_use)
    bei_input = data.bei

    details = [
        f"用途: {data.building_use or '不明'}",
        f"延べ床面積: {floor_area} m²（{scale}）",
        f"適用BEI基準: {bei_std}",
        "非住宅は外皮性能基準（U_A値）の義務なし。一次エネルギー消費量基準（BEI）のみ対象。",
    ]

    if floor_area >= 2000:
        details.append("大規模（2,000㎡以上）：2024年4月より用途別BEIが引き上げられています。")
    elif floor_area >= 300:
        details.append(f"中規模（300〜2,000㎡未満）：2026年4月よりBEI引上げ予定（現在基準: {bei_std}）。")

    numeric = {
        "延べ床面積": floor_area,
        "規模区分": scale,
        "BEI義務基準": bei_std,
    }

    if bei_input is not None:
        numeric["BEI（入力）"] = bei_input
        if bei_input <= bei_std:
            verdict = Verdict.CONFORMING
            summary = f"非住宅省エネ基準 ─ 適合（BEI {bei_input} ≦ {bei_std}）"
        else:
            verdict = Verdict.VIOLATION if is_new else Verdict.NONCONFORMING
            summary = f"非住宅省エネ基準 ─ 不適合（BEI {bei_input} > {bei_std}）"
    else:
        verdict = Verdict.UNKNOWN
        summary = f"非住宅省エネ基準（{scale}）─ BEI基準 {bei_std}（BEI値未入力）"

    return JudgeResult(
        category="省エネ基準適合義務",
        verdict=verdict,
        law_reference="建築物省エネ法 第11条・第12条 / 建築基準法第6条連携",
        summary=summary,
        details=details,
        caution=(
            "2026年4月以降、中規模（300〜2,000㎡未満）のBEI基準も大規模と同水準へ引上げ予定です。"
            if 300 <= floor_area < 2000 else None
        ),
        numeric=numeric,
    )


def _existing_building_result(data: "BuildingData", region: int, region_str: str,
                               is_residential: bool, conf_date: date) -> JudgeResult:
    """
    既存建築物（確認済証交付日が省エネ義務化前）の既存不適格判定。
    義務化以前に建設されたものは既存不適格扱い（現状維持は可）。
    """
    ua_std = get_ua_standard(region) if is_residential else None

    details = [
        f"確認済証交付日: {conf_date}（省エネ義務化: {OBLIGATION_EFFECTIVE_DATE} 以降）",
        f"適用地域区分: {region_str}",
    ]

    if is_residential and ua_std:
        details.append(f"現行U_A値基準: {ua_std} W/(m²·K)（建設当時は基準なし）")
        details.append(f"現行BEI基準: {BEI_RESIDENTIAL_MANDATORY}（建設当時は基準なし）")
    elif not is_residential:
        floor_area = data.total_floor_area or 0.0
        scale = get_nonresidential_scale(floor_area)
        bei_std = get_nonresidential_bei(floor_area, data.building_use)
        details.append(f"規模区分: {scale}、現行BEI基準: {bei_std}")

    details.append("既存建築物の現状維持は可能です。増改築・用途変更時には増改築部分への適用が必要です。")

    # 第1〜4次省エネ基準の変遷を参考情報として添付
    _ENERGY_HISTORY = [
        (date(1980, 11, 1),  "第1次省エネ基準（昭和55年基準）制定"),
        (date(1992,  7, 1),  "第2次省エネ基準（平成4年基準）強化"),
        (date(1999,  3, 1),  "第3次省エネ基準（平成11年基準）強化"),
        (date(2013,  9, 1),  "第4次省エネ基準（H25年基準・現行義務基準と同等）"),
        (date(2025,  4, 1),  "省エネ基準適合義務化（全新築・増改築対象）"),
    ]

    applicable = [f"{d}〜: {label}" for d, label in _ENERGY_HISTORY if conf_date < d]
    if applicable:
        details.append("建設後に施行された省エネ基準強化:")
        details.extend([f"  {item}" for item in applicable])

    return JudgeResult(
        category="省エネ基準適合義務",
        verdict=Verdict.NONCONFORMING,
        law_reference="建築物省エネ法 第11条 / 附則（経過措置）",
        summary=f"省エネ基準 既存不適格（{conf_date.year}年建設・{region_str}）",
        details=details,
        caution="増改築時は増改築部分について省エネ基準への適合が必要です（建物全体への遡及適用はなし）。",
        recommendation=(
            "省エネ改修（断熱改修・窓断熱等）を行うことで省エネ性能を向上できます。"
            "補助金制度（先進的窓リノベ・子育てエコホーム支援事業等）の活用もご検討ください。"
        ),
        numeric={"地域区分": region, "確認年": conf_date.year},
    )
