"""
接道義務判定モジュール

根拠法令:
  - 建築基準法 第42条（道路の定義）
  - 建築基準法 第43条（敷地等と道路との関係・接道義務）
  - 建築基準法 第42条2項（みなし道路・セットバック義務）
  - 建築基準法施行令 第144条の4（接道要件の例外）

実務メモ:
  - 2項道路のセットバック基準線 = 道路中心線から 2m
  - 片側が崖・川・線路の場合は反対側から 4m（建基法42条2項ただし書き）
  - セットバック予定地は建築面積・敷地面積の算入不可
"""
from . import BuildingData, JudgeResult, Verdict

_MIN_ROAD_WIDTH  = 4.0   # 建基法42条 道路幅員基準（m）
_MIN_CONTACT     = 2.0   # 建基法43条 接道長さ基準（m）
_SETBACK_TARGET  = 2.0   # 2項道路セットバック目標（道路中心から m）


def judge(data: BuildingData) -> JudgeResult:
    """接道義務の既存不適格判定"""

    if data.road_width is None or data.contact_length is None:
        return JudgeResult(
            category="接道義務",
            verdict=Verdict.UNKNOWN,
            law_reference="建基法42条・43条",
            summary="前面道路幅員または接道長さが未入力のため判定不能",
            caution="道路台帳・現況測量で前面道路の種別と幅員を確認してください。",
        )

    details = []
    issues = []
    cautions = []
    recommendations = []
    numeric = {
        "road_width":      data.road_width,
        "contact_length":  data.contact_length,
        "setback_required": 0.0,
    }

    # ── 接道長さ判定（建基法43条） ────────────────────────────────────
    if data.contact_length < _MIN_CONTACT:
        issues.append("接道長さ不足")
        details.append(
            f"接道長さ {data.contact_length:.2f}m ＜ 基準 {_MIN_CONTACT}m（建基法43条1項）"
        )
        cautions.append(
            "接道義務を満たさない場合、原則として建て替え・増改築の確認申請が受理されません。"
        )
        recommendations.append(
            "隣地の一部取得・借地による接道確保、または建基法43条2項許可申請（特定行政庁）を検討してください。"
        )
    else:
        details.append(
            f"接道長さ {data.contact_length:.2f}m ≧ 基準 {_MIN_CONTACT}m（建基法43条1項 OK）"
        )

    # ── 道路幅員判定（建基法42条） ────────────────────────────────────
    if data.road_width < _MIN_ROAD_WIDTH:
        issues.append("道路幅員不足")
        setback = _calc_setback(data.road_width)
        numeric["setback_required"] = setback

        details += [
            f"前面道路幅員 {data.road_width:.2f}m ＜ 基準 {_MIN_ROAD_WIDTH}m",
            f"→ 建基法42条2項道路（みなし道路）の可能性があります。",
            f"→ セットバック必要距離: 道路中心線から {_SETBACK_TARGET}m",
            f"   （現況道路境界からの後退目安: 約 {setback:.2f}m）",
            f"   ※片側が崖・川・線路等の場合は特定行政庁の指定による（建基法42条2項ただし書き）",
        ]
        cautions.append(
            f"セットバック予定地（約 {setback:.2f}m 幅）は建築不可・建ぺい率算入不可のため、"
            "有効敷地面積が減少します。建ぺい率・容積率の再計算が必要です。"
        )
        recommendations.append(
            f"セットバック後の有効敷地面積（= 現況敷地面積 − セットバック面積）で"
            "建ぺい率・容積率を再計算してください。"
            f"セットバック距離の目安: {setback:.2f}m。"
            "事前に市区町村の道路台帳で42条1項・2項・位置指定道路の別を確認してください。"
        )
    else:
        details.append(
            f"前面道路幅員 {data.road_width:.2f}m ≧ 基準 {_MIN_ROAD_WIDTH}m（建基法42条 OK）"
        )

    # ── 判定まとめ ────────────────────────────────────────────────
    if not issues:
        return JudgeResult(
            category="接道義務",
            verdict=Verdict.CONFORMING,
            law_reference="建基法42条・43条",
            summary=(
                f"接道義務を満たしています"
                f"（道路幅 {data.road_width}m ／ 接道長さ {data.contact_length}m）"
            ),
            details=details,
            numeric=numeric,
        )

    return JudgeResult(
        category="接道義務",
        verdict=Verdict.NONCONFORMING,
        law_reference="建基法42条・43条",
        summary=f"接道義務に課題あり（{' ／ '.join(issues)}）→ 既存不適格",
        details=details,
        caution=" ／ ".join(cautions),
        recommendation=" ／ ".join(recommendations),
        numeric=numeric,
    )


def _calc_setback(road_width: float) -> float:
    """
    2項道路のセットバック必要距離を計算する。
    道路中心線から 2m の位置までセットバックが必要。
    """
    current_half = road_width / 2
    if current_half >= _SETBACK_TARGET:
        return 0.0
    return round(_SETBACK_TARGET - current_half, 3)
