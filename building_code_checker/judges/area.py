"""
建ぺい率・容積率判定モジュール

根拠法令:
  - 建築基準法 第53条（建ぺい率）
  - 建築基準法 第52条（容積率）
  - 建築基準法 第86条の7（既存不適格建築物の増改築）

用語:
  BCR = Building Coverage Ratio = 建ぺい率
  FAR = Floor Area Ratio        = 容積率
"""
from . import BuildingData, JudgeResult, Verdict

_TOLERANCE = 0.05  # 浮動小数点誤差の許容値（%）


def judge(data: BuildingData) -> JudgeResult:
    """建ぺい率・容積率の既存不適格判定"""

    missing = _check_required(data)
    if missing:
        return JudgeResult(
            category="建ぺい率・容積率",
            verdict=Verdict.UNKNOWN,
            law_reference="建基法52条・53条",
            summary=f"判定に必要なデータが不足: {', '.join(missing)}",
            caution="敷地面積・建築面積・延べ床面積・指定制限値を入力してください。",
        )

    current_bcr = (data.building_area / data.site_area) * 100
    current_far = (data.total_floor_area / data.site_area) * 100

    bcr_over = current_bcr > data.bcr_limit + _TOLERANCE
    far_over  = current_far > data.far_limit + _TOLERANCE

    numeric = {
        "current_bcr": round(current_bcr, 2),
        "current_far": round(current_far, 2),
        "bcr_limit":   data.bcr_limit,
        "far_limit":   data.far_limit,
        "bcr_margin":  round(data.bcr_limit - current_bcr, 2),
        "far_margin":  round(data.far_limit - current_far, 2),
    }

    # ── 適法 ────────────────────────────────────────────────────────
    if not bcr_over and not far_over:
        return JudgeResult(
            category="建ぺい率・容積率",
            verdict=Verdict.CONFORMING,
            law_reference="建基法52条・53条",
            summary=(
                f"建ぺい率 {current_bcr:.1f}%（上限 {data.bcr_limit}%）/ "
                f"容積率 {current_far:.1f}%（上限 {data.far_limit}%）→ 適法"
            ),
            details=[
                f"建ぺい率: {current_bcr:.2f}% ≦ {data.bcr_limit}%"
                f"（余裕 {numeric['bcr_margin']:.2f}%）",
                f"容積率:   {current_far:.2f}% ≦ {data.far_limit}%"
                f"（余裕 {numeric['far_margin']:.2f}%）",
                f"建築面積: {data.building_area} m² ／ 敷地面積: {data.site_area} m²",
                f"延べ床面積: {data.total_floor_area} m² ／ 敷地面積: {data.site_area} m²",
            ],
            numeric=numeric,
            recommendation=(
                f"現行制限に適合しています。"
                f"増築可能な建築面積の目安: {numeric['bcr_margin'] * data.site_area / 100:.1f} m²"
                f"（建ぺい率余裕分）"
            ),
        )

    # ── 既存不適格 ──────────────────────────────────────────────────
    issues = []
    if bcr_over:
        excess = current_bcr - data.bcr_limit
        issues.append(
            f"建ぺい率 {current_bcr:.2f}% が上限 {data.bcr_limit}% を"
            f" {excess:.2f}% 超過（建基法53条）"
        )
    if far_over:
        excess = current_far - data.far_limit
        issues.append(
            f"容積率 {current_far:.2f}% が上限 {data.far_limit}% を"
            f" {excess:.2f}% 超過（建基法52条）"
        )

    return JudgeResult(
        category="建ぺい率・容積率",
        verdict=Verdict.NONCONFORMING,
        law_reference="建基法52条・53条",
        summary=" ／ ".join([i.split("（")[0] for i in issues]) + " → 既存不適格",
        details=issues + [
            f"建築面積: {data.building_area} m² ／ 敷地面積: {data.site_area} m²",
            f"延べ床面積: {data.total_floor_area} m² ／ 敷地面積: {data.site_area} m²",
        ],
        caution=(
            "既存不適格建物は現状維持は可能ですが、"
            "超過分を増大させる増築・用途変更は認められません。"
        ),
        recommendation=(
            "増改築計画では現行制限の枠内で設計してください。"
            "超過面積が大きい場合は、減築や一部用途変更による適合化を検討します。"
        ),
        numeric=numeric,
    )


def _check_required(data: BuildingData) -> list:
    required = {
        "site_area":        data.site_area,
        "building_area":    data.building_area,
        "total_floor_area": data.total_floor_area,
        "bcr_limit":        data.bcr_limit,
        "far_limit":        data.far_limit,
    }
    return [k for k, v in required.items() if v is None]
