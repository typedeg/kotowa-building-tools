"""
耐震基準判定モジュール

根拠法令:
  - 建築基準法 第20条（構造耐力）
  - 昭和55年建設省告示第1792号（旧耐震：1981年5月以前）
  - 昭和56年改正施行（新耐震基準：1981年6月1日〜）
  - 平成12年建設省告示第1460号（木造2000年基準：2000年6月1日〜）
"""
from datetime import date
from . import BuildingData, JudgeResult, Verdict, parse_date

# 基準日の定数（条文対応のため根拠を明記）
_NEW_SEISMIC_DATE = date(1981, 6, 1)   # 昭56年建基法施行令改正（新耐震基準施行）
_WOOD_2000_DATE   = date(2000, 6, 1)   # 平12建告第1460号施行（接合金物・壁量強化）

_WOOD_TYPES = {"木造", "W", "木", "木構造"}


def judge(data: BuildingData) -> JudgeResult:
    """耐震基準の既存不適格判定"""

    if data.confirmation_date is None:
        return JudgeResult(
            category="耐震基準",
            verdict=Verdict.UNKNOWN,
            law_reference="建基法20条",
            summary="確認済証交付日が未入力のため判定不能",
            caution="確認済証・建設当時の設計図書で交付日を確認してください。",
        )

    try:
        conf_date = parse_date(data.confirmation_date)
    except ValueError:
        return JudgeResult(
            category="耐震基準",
            verdict=Verdict.UNKNOWN,
            law_reference="建基法20条",
            summary=f"確認済証交付日の形式が不正: {data.confirmation_date}",
            caution="例: 1978-03-15 / 昭和53年3月15日 / S53.3.15",
        )

    structure = data.structure_type or ""

    # ── 旧耐震基準 ──────────────────────────────────────────────────
    if conf_date < _NEW_SEISMIC_DATE:
        return JudgeResult(
            category="耐震基準",
            verdict=Verdict.NONCONFORMING,
            law_reference="建基法20条1項・昭55建告第1792号",
            summary=f"旧耐震基準適用（確認日: {conf_date}）→ 既存不適格",
            details=[
                f"確認済証交付日: {conf_date}",
                f"新耐震基準施行日（{_NEW_SEISMIC_DATE}）より前のため旧耐震基準が適用されています。",
                "設計基準：中地震（震度5強程度）で損傷しないこと。",
                "現行基準：大地震（震度6強〜7）でも倒壊・崩壊しないことが要求されます。",
                "耐震性能は現行基準の概ね1/2程度以下の可能性があります。",
            ],
            caution=(
                "旧耐震基準の建物は地震保険の割増対象となる場合があります。"
                "大規模改修・増築の際は建物全体を現行基準に適合させる必要が生じることがあります。"
            ),
            recommendation=(
                "住宅医詳細調査の実施を提案してください。"
                "耐震診断（一般診断法・精密診断法）でIs値・q値を確認し、"
                "耐震補強計画と性能向上リノベーション（断熱・省エネ）を一体で設計すると"
                "耐震改修促進法に基づく補助金活用の可能性が高まります。"
            ),
            numeric={"confirmation_year": conf_date.year},
        )

    # ── 新耐震基準・2000年基準未満（木造のみ） ────────────────────────
    if structure in _WOOD_TYPES and conf_date < _WOOD_2000_DATE:
        return JudgeResult(
            category="耐震基準",
            verdict=Verdict.NONCONFORMING,
            law_reference="建基法20条1項・平12建告第1460号",
            summary=f"新耐震基準・木造2000年基準未満（確認日: {conf_date}）→ 既存不適格",
            details=[
                f"確認済証交付日: {conf_date}",
                f"新耐震基準（{_NEW_SEISMIC_DATE}）以降ですが、木造2000年基準（{_WOOD_2000_DATE}）より前です。",
                "平成12年建設省告示第1460号（柱頭柱脚接合金物・耐力壁バランス・基礎仕様）が未適用の可能性があります。",
                "特に接合部金物の欠如・耐力壁の偏在・無筋コンクリート基礎が多い世代です。",
            ],
            caution=(
                "阪神淡路大震災（1995年）でこの世代の木造住宅の被害が多く確認されています。"
                "N値計算・四分割法による安全確認が必要です。"
            ),
            recommendation=(
                "劣化状況調査（床下・小屋裏の目視確認）と耐震診断（一般診断法）を組み合わせてください。"
                "改修設計では平12告示の接合金物基準を遡及適用し、"
                "耐力壁の偏心率（Fex・Fey ≦ 0.3）を目標に補強計画を立てます。"
            ),
            numeric={"confirmation_year": conf_date.year},
        )

    # ── 現行基準（2000年基準以降）────────────────────────────────────
    return JudgeResult(
        category="耐震基準",
        verdict=Verdict.CONFORMING,
        law_reference="建基法20条1項・平12建告第1460号",
        summary=f"現行耐震基準に適合（確認日: {conf_date}）",
        details=[
            f"確認済証交付日: {conf_date}（木造2000年基準 {_WOOD_2000_DATE} 以降）",
            "平成12年建設省告示第1460号に基づく接合金物・壁量計算が適用されています。",
        ],
        recommendation=(
            "耐震性能は現行基準を満たしています。"
            "劣化状況に応じて性能向上リノベーション（断熱・気密・省エネ）を優先提案できます。"
        ),
        numeric={"confirmation_year": conf_date.year},
    )
