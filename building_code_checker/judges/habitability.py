"""
採光・換気・排煙・シックハウス対策判定モジュール

根拠法令:
  - 建築基準法 第28条（居室の採光・換気）
  - 建築基準法 第28条の2（シックハウス対策）
  - 建築基準法施行令 第19条（採光のための開口部の面積の算定方法）
  - 建築基準法施行令 第20条の2（換気設備）
  - 建築基準法施行令 第116条の2（排煙上の無窓居室）
  - 平成15年7月1日施行（シックハウス対策・24時間換気義務化）
"""
from __future__ import annotations
from datetime import date
from typing import Optional
from . import BuildingData, JudgeResult, Verdict, parse_date

_SICKHOUSE_LAW_DATE = date(2003, 7, 1)  # 平成15年7月1日施行（シックハウス対策）

_DAYLIGHT_RATIO = 1 / 7   # 法28条: 居室の有効採光面積は床面積の1/7以上
_EXHAUST_AREA_THRESHOLD = 200.0  # 令116条の2: 200㎡超または3階以上で排煙確認
_EXHAUST_VOLUME_RATIO = 1 / 50  # 令116条の2: 排煙窓面積は床面積の1/50以上


def judge(data: BuildingData) -> JudgeResult:
    """採光・換気（シックハウス含む）・排煙の居住性能判定"""

    conf_date = None
    if data.confirmation_date:
        try:
            conf_date = parse_date(data.confirmation_date)
        except ValueError:
            pass

    stories = data.stories or 1
    total_area = data.total_floor_area or 0.0
    has_24h = data.has_24h_ventilation
    max_room_area = data.max_room_area
    effective_daylight = data.effective_daylight_area

    results: list[JudgeResult] = []

    # ── シックハウス対策（法28条の2・令20条の2）──────────────────────
    sick = _judge_sickhouse(conf_date, has_24h)
    results.append(sick)

    # ── 採光（法28条・令19条）────────────────────────────────────────
    if max_room_area is not None and effective_daylight is not None:
        daylight = _judge_daylight(max_room_area, effective_daylight)
        results.append(daylight)

    # ── 排煙（令116条の2）───────────────────────────────────────────
    exhaust = _judge_exhaust(stories, total_area)
    results.append(exhaust)

    # 最も重篤な verdict を採用して統合結果を返す
    priority = [Verdict.VIOLATION, Verdict.NONCONFORMING, Verdict.UNKNOWN, Verdict.CONFORMING]
    worst = max(results, key=lambda r: priority.index(r.verdict))

    all_details: list[str] = []
    all_caution_parts: list[str] = []
    all_rec_parts: list[str] = []
    for r in results:
        if r.details:
            all_details.extend(r.details)
        if r.caution:
            all_caution_parts.append(r.caution)
        if r.recommendation:
            all_rec_parts.append(r.recommendation)

    # サマリを複数判定の見出しにまとめる
    summaries = [r.summary for r in results]
    combined_summary = " ／ ".join(summaries)

    return JudgeResult(
        category="採光・換気・排煙",
        verdict=worst.verdict,
        law_reference="建基法28条・28条の2・令19条・20条の2・116条の2",
        summary=combined_summary,
        details=all_details or None,
        caution=" ".join(all_caution_parts) if all_caution_parts else None,
        recommendation=" ".join(all_rec_parts) if all_rec_parts else None,
    )


def _judge_sickhouse(conf_date: Optional[date], has_24h: Optional[bool]) -> JudgeResult:
    """シックハウス対策（法28条の2・令20条の2）"""

    if conf_date is None:
        return JudgeResult(
            category="採光・換気・排煙",
            verdict=Verdict.UNKNOWN,
            law_reference="建基法28条の2・令20条の2",
            summary="シックハウス対策：確認済証日が未入力のため判定不能",
            caution="確認済証交付日を入力してください。平成15年7月1日以降の建物は24時間換気が義務です。",
        )

    if conf_date < _SICKHOUSE_LAW_DATE:
        if has_24h is False:
            return JudgeResult(
                category="採光・換気・排煙",
                verdict=Verdict.NONCONFORMING,
                law_reference="建基法28条の2・令20条の2",
                summary="シックハウス対策：平成15年7月施行前建築・24時間換気なし → 既存不適格",
                details=[
                    f"確認済証交付日: {conf_date}（平成15年7月1日より前）",
                    "建基法28条の2・令20条の2 のシックハウス対策規定（平成15年7月1日施行）は建設当時未施行のため既存不適格です。",
                    "24時間換気設備（0.5回/h以上）が未設置のまま使用継続されています。",
                    "建材からのホルムアルデヒド・VOC濃度が基準値を超えるリスクがあります。",
                ],
                caution=(
                    "増改築・用途変更を行う場合、現行のシックハウス対策基準への適合が必要です。"
                    "特に子ども・高齢者・アレルギー体質の居住者がいる場合は改修を優先してください。"
                ),
                recommendation=(
                    "機械換気設備（第1種または第3種換気・0.5回/h以上）の設置を検討してください。"
                    "リノベーション時に内装材を低VOC建材へ更新することも有効です。"
                ),
            )
        elif has_24h is True:
            return JudgeResult(
                category="採光・換気・排煙",
                verdict=Verdict.CONFORMING,
                law_reference="建基法28条の2・令20条の2",
                summary="シックハウス対策：平成15年7月前建築・24時間換気あり → 実質対応済み",
                details=[
                    f"確認済証交付日: {conf_date}（平成15年7月1日より前）",
                    "施行前建築ですが、24時間換気設備が設置済みのため実質的に現行基準を満たしています。",
                ],
                recommendation="換気設備の定期清掃・フィルター交換（年1〜2回）を継続してください。",
            )
        else:
            return JudgeResult(
                category="採光・換気・排煙",
                verdict=Verdict.UNKNOWN,
                law_reference="建基法28条の2・令20条の2",
                summary="シックハウス対策：平成15年7月前建築・24時間換気の有無を確認してください",
                details=[
                    f"確認済証交付日: {conf_date}（平成15年7月1日より前）",
                    "シックハウス対策規定（令20条の2）施行前の建築物です。24時間換気設備の有無を確認してください。",
                ],
                caution="24時間換気設備（機械換気・0.5回/h）の有無を現況確認してください。",
                recommendation="換気設備がない場合は設置を検討してください。リノベーション時の対応が最も効果的です。",
            )
    else:
        if has_24h is False:
            return JudgeResult(
                category="採光・換気・排煙",
                verdict=Verdict.VIOLATION,
                law_reference="建基法28条の2・令20条の2",
                summary="シックハウス対策：平成15年7月以降建築・24時間換気なし → 違反",
                details=[
                    f"確認済証交付日: {conf_date}（平成15年7月1日以降）",
                    "建基法28条の2・令20条の2 のシックハウス対策規定が適用される建築物です。",
                    "24時間換気設備（0.5回/h以上）が設置されていないことは建基法違反です。",
                ],
                caution="速やかに24時間換気設備（第1種または第3種換気・0.5回/h以上）を設置してください。",
                recommendation=(
                    "建築主事または建築確認機関に相談し、確認申請時の換気計算書を確認してください。"
                    "設置費用の目安：第3種換気（低コスト）15〜30万円程度。"
                ),
            )
        elif has_24h is True:
            return JudgeResult(
                category="採光・換気・排煙",
                verdict=Verdict.CONFORMING,
                law_reference="建基法28条の2・令20条の2",
                summary="シックハウス対策：24時間換気設備あり → 適合",
                details=[
                    f"確認済証交付日: {conf_date}",
                    "建基法28条の2・令20条の2 のシックハウス対策規定に適合しています。",
                    "24時間換気設備（0.5回/h以上）が設置されています。",
                ],
                recommendation="換気設備の定期点検・フィルター清掃を実施してください（年1〜2回推奨）。",
            )
        else:
            return JudgeResult(
                category="採光・換気・排煙",
                verdict=Verdict.UNKNOWN,
                law_reference="建基法28条の2・令20条の2",
                summary="シックハウス対策：24時間換気の有無が未入力",
                caution="平成15年7月以降の建物は24時間換気設備（0.5回/h）が法的義務です。有無を確認してください。",
            )


def _judge_daylight(max_room_area: float, effective_daylight: float) -> JudgeResult:
    """採光（法28条・令19条）"""

    required = max_room_area * _DAYLIGHT_RATIO
    ratio = effective_daylight / max_room_area if max_room_area > 0 else 0.0

    if ratio < _DAYLIGHT_RATIO:
        return JudgeResult(
            category="採光・換気・排煙",
            verdict=Verdict.NONCONFORMING,
            law_reference="建基法28条・令19条",
            summary=f"採光：有効採光面積不足（{ratio:.3f} < 1/7）→ 既存不適格",
            details=[
                f"最大居室面積: {max_room_area}㎡",
                f"有効採光面積: {effective_daylight}㎡（必要: {required:.2f}㎡以上）",
                f"採光比率: {ratio:.4f}（基準: 1/7 ≈ 0.1429）",
                "建基法28条・令19条により、居室の有効採光面積は床面積の1/7以上が必要です。",
                "令19条の採光補正係数（用途地域・窓面積・隣地境界からの距離で算定）を用いて算定します。",
            ],
            caution=(
                "無窓居室（採光不足）は居室として使用できない場合があります。"
                "増改築・用途変更時には現行基準への適合確認が必要です。"
            ),
            recommendation=(
                "天窓・トップライトの追加、窓面積の拡大、隣地境界からの離隔確保で改善できます。"
                "採光補正係数の再算定を建築士に依頼してください。"
            ),
        )
    else:
        return JudgeResult(
            category="採光・換気・排煙",
            verdict=Verdict.CONFORMING,
            law_reference="建基法28条・令19条",
            summary=f"採光：有効採光面積適合（{ratio:.3f} ≥ 1/7）",
            details=[
                f"最大居室面積: {max_room_area}㎡",
                f"有効採光面積: {effective_daylight}㎡（必要: {required:.2f}㎡以上）",
                f"採光比率: {ratio:.4f}（基準: 1/7 ≈ 0.1429）",
                "建基法28条・令19条の採光要件を満たしています。",
            ],
        )


def _judge_exhaust(stories: int, total_area: float) -> JudgeResult:
    """排煙（令116条の2）"""

    # 令116条の2 除外規定: 住宅の居室・2階以下・延べ面積200㎡以下は排煙規定の適用除外
    is_excluded = (stories <= 2 and total_area <= _EXHAUST_AREA_THRESHOLD)

    if is_excluded:
        return JudgeResult(
            category="採光・換気・排煙",
            verdict=Verdict.CONFORMING,
            law_reference="建基法施行令116条の2",
            summary=f"排煙：除外規定適用（{stories}階/{total_area:.0f}㎡）→ 排煙設備不要",
            details=[
                f"階数: {stories} / 延べ面積: {total_area}㎡",
                "令116条の2 ただし書きにより、2階以下かつ延べ面積200㎡以下の住宅居室は排煙規定の適用除外です。",
            ],
            recommendation="排煙設備は不要ですが、火災時の避難経路（窓・出入口）の確保を確認してください。",
        )
    else:
        return JudgeResult(
            category="採光・換気・排煙",
            verdict=Verdict.UNKNOWN,
            law_reference="建基法施行令116条の2",
            summary=f"排煙：排煙窓の有効開口面積（床面積の1/50以上）の確認が必要（{stories}階/{total_area:.0f}㎡）",
            details=[
                f"階数: {stories} / 延べ面積: {total_area}㎡",
                "令116条の2 により、延べ面積200㎡超または3階以上の建築物は排煙上の無窓居室に該当しないか確認が必要です。",
                "各居室の床面積の1/50以上の有効開口面積を持つ排煙窓（天井から80cm以内の位置）が必要です。",
                "無窓居室に該当する場合は機械排煙設備（令126条の2）または排煙区画の設置が必要です。",
            ],
            caution="排煙上の無窓居室に該当する可能性があります。設計図書で排煙窓の有効開口面積を確認してください。",
            recommendation=(
                "各居室の天井から80cm以内に位置する開口部の合計面積が床面積の1/50以上あるか確認してください。"
                "不足する場合は機械排煙設備または排煙口の追加が必要です。"
            ),
        )
