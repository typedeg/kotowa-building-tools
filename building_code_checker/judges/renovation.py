"""
増改築・大規模修繕 可否判定モジュール

根拠法令:
  - 建築基準法 第86条の7（既存不適格建築物の増改築）
  - 建築基準法施行令 第137条の2（構造耐力関係の遡及適用範囲）
  - 建築基準法施行令 第137条の14（増改築部分の割合の計算方法）
  - 建築基準法 第6条（確認申請対象の判定・R7.4改正で2階建て木造も対象に拡大）

判定フロー:
  既存不適格なし → 制限なし
  増改築面積 ÷ 既存延べ床面積 > 1/2 → 建物全体を現行基準に適合させる必要あり
  増改築面積 ÷ 既存延べ床面積 ≦ 1/2 → 増改築部分のみ現行基準適合でよい

大規模修繕・模様替の確認申請要否（R7.4改正後）:
  主要構造部（壁・柱・床・梁・屋根・階段）のうち1種類以上について
  当該種類の過半を修繕・模様替する場合 → 確認申請・完了検査が必要
  ※R7.4施行前は2階建て木造は審査省略（4号特例）。改正後は確認申請が必要。

実務メモ:
  「既存部分」の範囲・面積の定義は確認審査機関によって解釈が異なるため、
  設計着手前に特定行政庁または指定確認検査機関への事前相談を推奨する。
"""
from . import BuildingData, JudgeResult, Verdict
from .energy_standards import (
    get_ua_standard, get_ua_zeh, get_eta_ac_standard,
    region_label, DEFAULT_CLIMATE_REGION, BEI_RESIDENTIAL_MANDATORY,
)

_THRESHOLD = 0.5  # 建基法86条の7 判定閾値（1/2）

# 主要構造部一覧（建基法2条5号）と過半判定の基準
_MAJOR_PARTS = {
    "壁":   "総面積に占める割合",
    "柱":   "総本数に占める割合",
    "床":   "総水平投影面積に占める割合",
    "梁":   "総本数に占める割合",
    "屋根": "総水平投影面積に占める割合",
    "階段": "各階ごとの総数に占める割合",
}


def judge_repair_guidance() -> JudgeResult:
    """大規模修繕・大規模模様替の確認申請要否ガイダンスを返す（入力不要）"""
    parts_list = "\n".join(
        f"  ・{part}：{criteria}" for part, criteria in _MAJOR_PARTS.items()
    )
    return JudgeResult(
        category="大規模修繕・模様替の確認申請要否",
        verdict=Verdict.UNKNOWN,
        law_reference="建基法6条（R7.4改正）",
        summary="大規模修繕・模様替は主要構造部の過半に及ぶ場合に確認申請が必要（R7.4〜2階建て木造も対象）",
        details=[
            "■ 大規模の修繕・大規模の模様替とは（建基法2条14・15号）",
            "  主要構造部の1種類以上について「過半」の修繕または模様替をすること。",
            "",
            "■ 主要構造部（建基法2条5号）と過半判定の基準",
            parts_list,
            "",
            "■ 確認申請が不要な代表例（主要構造部の過半に及ばない場合）",
            "  ・屋根ふき材（スレート・金属板）のみの葺き替え",
            "  ・カバー工法（既設屋根ふき材の上に新設）",
            "  ・外壁の外装材のみの張り替え（構造用合板・胴縁は触らない）",
            "  ・水回りのみのリフォーム（キッチン・浴室・トイレ）",
            "  ・手すり・スロープの設置",
            "",
            "■ R7.4改正による変更点",
            "  2025年4月1日以降、2階建て木造・都市計画区域外の小規模木造も",
            "  大規模修繕・模様替の確認申請対象となった（4号特例廃止）。",
            "  確認申請が必要な場合は完了検査の取得が必須。",
        ],
        caution=(
            "主要構造部の「過半」か否かの判断は部位ごとに行う。"
            "屋根は水平投影面積の過半、柱・梁は本数の過半、壁は面積の過半で判定。"
            "判断が難しい場合は特定行政庁または指定確認検査機関への事前相談を推奨する。"
        ),
        recommendation=(
            "リノベ計画の初期段階で「大規模修繕に該当するか」を確認し、"
            "該当する場合は確認申請スケジュールを工程に組み込む。"
            "確認申請が必要な場合、省エネ適合判定・構造計算も審査対象になる場合がある。"
        ),
    )


def judge_building_classification(data: BuildingData) -> JudgeResult:
    """R7.4改正による建築物分類（新2号/新3号）判定

    令和7年（2025年）4月1日施行の建基法6条改正（4号特例廃止）により、
    木造建築物は「新2号」「新3号」に区分され、確認申請・審査の要件が変わった。
    """
    stories = data.stories
    total_area = data.total_floor_area
    structure = (data.structure_type or "").strip()

    # 木造かどうかを判定（未入力時は木造として扱う）
    is_wood = (
        not structure
        or structure in {"木造", "W", "木", "木構造", "在来工法", "軸組構法"}
    )

    if not is_wood:
        return JudgeResult(
            category="建築物分類（新2号/新3号）",
            verdict=Verdict.CONFORMING,
            law_reference="建基法6条改正（R7.4施行）",
            summary=f"構造種別「{structure}」は4号特例廃止（新2号/新3号区分）の対象外",
            details=[
                "4号特例廃止（R7.4）は木造建築物に対する改正です。",
                f"入力された構造種別「{structure}」には旧来の確認申請手続きが適用されます。",
            ],
        )

    if stories is None and total_area is None:
        return JudgeResult(
            category="建築物分類（新2号/新3号）",
            verdict=Verdict.UNKNOWN,
            law_reference="建基法6条改正（R7.4施行）",
            summary="階数・延べ床面積が未入力のため新2号/新3号の判定不能",
            caution="階数または延べ床面積を入力すると建築物分類を判定できます。",
        )

    # 新2号：2階建て以上 OR 延べ200㎡超（木造）
    is_shin2go = (stories is not None and stories >= 2) or (
        total_area is not None and total_area > 200
    )

    if is_shin2go:
        area_str = f"{total_area} m²" if total_area is not None else "不明"
        stories_str = f"{stories}階建て" if stories is not None else "不明"
        return JudgeResult(
            category="建築物分類（新2号/新3号）",
            verdict=Verdict.CONFORMING,
            law_reference="建基法6条1項2号改正（R7.4施行）",
            summary=f"新2号建築物（{stories_str}・{area_str}）— 確認申請・完了検査が必須",
            details=[
                f"■ 判定根拠",
                f"  階数: {stories_str}　延べ床面積: {area_str}",
                f"  2階建て以上 または 延べ200㎡超の木造 → 新2号建築物",
                "",
                "■ 確認申請・審査の変更点（R7.4以降）",
                "  ・確認申請・完了検査が義務（旧4号特例による省略不可）",
                "  ・構造規定（令43条：柱の小径、令46条：壁量計算）の審査対象",
                "  ・省エネ基準適合性も確認申請・完了検査で審査される",
                "  ・完了検査（検査済証）なしでの使用開始は法7条の6により禁止",
                "",
                "■ 壁量計算（令46条改正）—— 2つの計算方法",
                "  方法A（早見表）: S56建告1100号改正による見直し値（最大約1.5倍強化）",
                "  方法B（表計算ツール）: howtec.or.jp/publics/index/411/ の計算ツールを使用",
                "  ※準耐力壁等（筋かい未満の壁）は必要壁量の1/2まで算入可（令46条5項改正）",
                "  ※階高3.2m超の筋かいは壁倍率を低減（αh = 3.5 × 柱間隔/階高）",
                "",
                "■ 経過措置（R7.4〜R8.3.31着工）",
                "  令和7年4月1日〜令和8年3月31日に工事着手する場合、",
                "  地上2階以下・高さ13m以下・軒高9m以下・延べ300㎡以下の木造は",
                "  改正前の壁量基準（旧S56建告1100号）を適用することができる（経過措置）。",
            ],
            caution=(
                "増改築・大規模修繕では確認申請が必要です。"
                "省エネ基準適合（UA値・一次エネ）の審査も必須となります。"
            ),
            recommendation=(
                "設計段階から構造計算・省エネ計算を一体で計画してください。"
                "壁量計算はhowtec.or.jp公式ツール（方法B）または早見表（方法A）で実施し、"
                "準耐力壁の算入（1/2上限）も活用して壁量を確保します。"
            ),
        )

    # 新3号：平屋 AND 延べ200㎡以下（木造）
    area_str = f"{total_area} m²" if total_area is not None else "不明"
    stories_str = f"{stories}階建て" if stories is not None else "不明"
    return JudgeResult(
        category="建築物分類（新2号/新3号）",
        verdict=Verdict.CONFORMING,
        law_reference="建基法6条1項3号改正（R7.4施行）",
        summary=f"新3号建築物（{stories_str}・{area_str}）— 建築士設計の場合は構造規定の審査省略あり",
        details=[
            f"■ 判定根拠",
            f"  階数: {stories_str}　延べ床面積: {area_str}",
            f"  平屋かつ延べ200㎡以下の木造 → 新3号建築物",
            "",
            "■ 確認申請・審査の変更点（R7.4以降）",
            "  ・確認申請・完了検査は引き続き義務",
            "  ・建築士（一級・二級・木造建築士）が設計する場合は構造規定の審査が省略される",
            "    ただし 建築士が設計・工事監理を行うことが条件（無資格設計は省略不可）",
            "  ・省エネ基準適合性は確認申請・完了検査で審査される",
            "  ・完了検査（検査済証）なしでの使用開始は禁止（旧4号と同様）",
            "",
            "■ 木造建築士の業務範囲（建築士法改正・R7.4施行）",
            "  高さ16m以内の木造建築物の設計・工事監理が可能（改正前は13m以内）",
        ],
        caution=(
            "建築士資格のない施工者が設計する場合は審査省略が適用されません。"
            "省エネ基準適合（UA値・一次エネ）の確認申請・完了検査での審査は必須です。"
        ),
        recommendation=(
            "平屋・小規模であっても完了検査の取得を必ず計画に入れてください。"
            "省エネ基準は地域区分6（高松市）でUA値≦0.87（等級4）が最低要件です。"
        ),
    )


def judge(data: BuildingData) -> JudgeResult:
    """増改築可否判定（建基法86条の7）"""

    if data.renovation_area is None:
        return JudgeResult(
            category="増改築可否",
            verdict=Verdict.UNKNOWN,
            law_reference="建基法86条の7",
            summary="増改築予定面積が未入力のため判定不能",
            caution=(
                "増改築計画がない場合はこの判定は不要です。"
                "大規模修繕・大規模模様替を計画している場合は"
                "主要構造部の過半に及ぶか否かで確認申請の要否が変わります（R7.4以降は2階建て木造も対象）。"
            ),
        )

    # 既存床面積の取得（existing_floor_area 優先、なければ total_floor_area で代用）
    if data.existing_floor_area is not None:
        existing = data.existing_floor_area
        area_note = ""
    elif data.total_floor_area is not None:
        existing = data.total_floor_area
        area_note = "（total_floor_area で代用）"
    else:
        return JudgeResult(
            category="増改築可否",
            verdict=Verdict.UNKNOWN,
            law_reference="建基法86条の7",
            summary="既存延べ床面積が不明のため判定不能",
        )

    ratio = data.renovation_area / existing
    ratio_pct = ratio * 100

    # 省エネ基準の参照値（地域区分が未入力の場合はデフォルト6地域）
    region = data.climate_region if (hasattr(data, "climate_region") and data.climate_region) else DEFAULT_CLIMATE_REGION
    ua_std = get_ua_standard(region)
    ua_zeh = get_ua_zeh(region)
    region_str = region_label(region)
    energy_note = (
        f"省エネ基準（{region_str}）: U_A≦{ua_std} W/(m²·K)、BEI≦{BEI_RESIDENTIAL_MANDATORY}"
        if ua_std else
        f"省エネ基準（{region_str}）: BEI≦{BEI_RESIDENTIAL_MANDATORY}（外皮基準なし）"
    )

    numeric = {
        "renovation_area":     data.renovation_area,
        "existing_floor_area": existing,
        "ratio":               round(ratio, 4),
        "ratio_pct":           round(ratio_pct, 2),
        "threshold_pct":       _THRESHOLD * 100,
    }

    # ── 1/2 超 → 建物全体の現行基準適合が必要 ──────────────────────
    if ratio > _THRESHOLD:
        return JudgeResult(
            category="増改築可否",
            verdict=Verdict.NONCONFORMING,
            law_reference="建基法86条の7・令137条の14",
            summary=(
                f"増改築面積割合 {ratio_pct:.1f}%（1/2超）"
                f" → 建物全体を現行基準に適合させる必要あり"
            ),
            details=[
                f"増改築予定面積: {data.renovation_area} m²",
                f"既存延べ床面積: {existing} m²{area_note}",
                f"面積割合: {ratio_pct:.2f}%（閾値 {_THRESHOLD*100:.0f}% 超過）",
                "建基法86条の7第1項の規定により、増改築部分だけでなく",
                "建物全体を現行の建築基準法に適合させる必要があります。",
                "対象となる技術基準: 構造耐力（令137条の2）・防火（令137条の10）・",
                "採光・換気・避難（令137条の11）等",
                f"【省エネ】建物全体への適用: {energy_note}",
            ],
            caution=(
                "増改築面積が1/2を超えると建て替えと同等の法的要求が生じます。"
                "計画段階で特定行政庁・確認審査機関への事前相談を強く推奨します。"
            ),
            recommendation=(
                "増改築面積を既存床面積の1/2以内（="
                f" {existing * _THRESHOLD:.1f} m²以下）に抑えることで手続きを簡略化できます。"
                "それが難しい場合は、住宅医詳細調査を先行させ耐震補強計画と一体で設計することで"
                "全体適合のコストを最適化します。"
            ),
            numeric=numeric,
        )

    # ── 1/2 以下 → 増改築部分のみ適合でよい ───────────────────────
    return JudgeResult(
        category="増改築可否",
        verdict=Verdict.CONFORMING,
        law_reference="建基法86条の7・令137条の14",
        summary=(
            f"増改築面積割合 {ratio_pct:.1f}%（1/2以下）"
            f" → 増改築部分のみ現行基準適合でよい"
        ),
        details=[
            f"増改築予定面積: {data.renovation_area} m²",
            f"既存延べ床面積: {existing} m²{area_note}",
            f"面積割合: {ratio_pct:.2f}%（閾値 {_THRESHOLD*100:.0f}% 以下）",
            "建基法86条の7の規定により、増改築部分のみ現行技術基準への適合が求められます。",
            "既存部分については、現在の既存不適格状態を維持することができます。",
            f"【省エネ】増改築部分への適用: {energy_note}",
            f"なお、1/2以内の増築可能残余面積: {existing * _THRESHOLD - data.renovation_area:.1f} m²",
        ],
        caution=(
            "増改築後に既存不適格の状態が拡大する計画は認められません。"
            "また、用途変更を伴う場合は別途確認が必要です。"
        ),
        recommendation=(
            "増改築部分の断熱・気密性能（省エネ基準）と"
            "既存部分との接続部の耐震設計に注力してください。"
            "既存部分の劣化補修と組み合わせることで住宅全体の性能を底上げできます。"
        ),
        numeric=numeric,
    )
