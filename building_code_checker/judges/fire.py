"""
防火規制判定モジュール

根拠法令:
  - 建築基準法 第61条（防火地域・準防火地域内の建築物）
  - 建築基準法 第62条（準防火地域内の建築物）
  - 建築基準法 第65条（防火地域・準防火地域内の建築物の屋根）
  - 建築基準法施行令 第112条（防火区画）
  - 令和元年6月25日施行（防火規制の性能規定化・木造耐火建築物適用拡大）
"""
from . import BuildingData, JudgeResult, Verdict, parse_date

_WOOD_KEYWORDS = {"木造", "W", "木構造", "木"}


def judge(data: BuildingData) -> JudgeResult:
    """防火地域・準防火地域内の建築物の防火規制判定"""

    fire_zone = data.fire_zone
    if fire_zone is None:
        return JudgeResult(
            category="防火規制",
            verdict=Verdict.UNKNOWN,
            law_reference="建基法61条・62条・令112条",
            summary="防火地域区分が未入力のため判定不能",
            caution=(
                "防火地域・準防火地域・法22条区域・指定なし を確認してください。"
                "都市計画図（市区町村窓口・GIS）または行政の建築指導課で確認できます。"
            ),
        )

    structure = data.structure_type or ""
    stories = data.stories or 1
    total_area = data.total_floor_area or 0.0
    fire_resistance = data.fire_resistance or ""

    is_wood = any(kw in structure for kw in _WOOD_KEYWORDS)

    # ── 防火地域────────────────────────────────────────────────────
    if "防火地域" in fire_zone and "準" not in fire_zone:
        # 3階以上 or 延べ面積100㎡超 → 耐火建築物等が必要（法61条）
        if stories >= 3 or total_area > 100:
            if is_wood and "耐火" not in fire_resistance:
                return JudgeResult(
                    category="防火規制",
                    verdict=Verdict.NONCONFORMING,
                    law_reference="建基法61条・令136条の2",
                    summary=f"防火地域内 木造（{stories}階/{total_area:.0f}㎡）→ 耐火建築物等が必要・既存不適格",
                    details=[
                        f"防火地域区分: {fire_zone}",
                        f"構造種別: {structure} / 階数: {stories} / 延べ面積: {total_area}㎡",
                        "建基法61条により、防火地域内で3階以上または延べ面積100㎡超の建築物は耐火建築物等にしなければなりません。",
                        "一般木造は原則として耐火建築物に該当しません（CLT・耐火集成木材等の認定取得を除く）。",
                        "令和元年改正（2019年6月25日施行）により木造耐火建築物の適用が拡大されました。",
                    ],
                    caution=(
                        "増改築・用途変更を行う場合、耐火建築物等への変更が求められることがあります。"
                        "耐火性能の認定（耐火木造等）を取得している場合は適合の可能性があります。"
                    ),
                    recommendation=(
                        "設計図書（確認申請書・仕様書）で耐火性能の認定・仕様を確認してください。"
                        "CLT・耐火集成木材等の耐火木造への改修も選択肢として検討できます。"
                    ),
                )
            else:
                return JudgeResult(
                    category="防火規制",
                    verdict=Verdict.CONFORMING,
                    law_reference="建基法61条",
                    summary=f"防火地域内 耐火性能適合（{stories}階/{total_area:.0f}㎡）",
                    details=[
                        f"防火地域区分: {fire_zone}",
                        f"構造種別: {structure} / 耐火性能: {fire_resistance or '入力なし'} / 階数: {stories}",
                        "耐火建築物等として規模・耐火性能の基準を満たしています。",
                    ],
                )
        # 2階以下 かつ 100㎡以下 → 準耐火建築物等で対応可能（法61条ただし書き）
        else:
            return JudgeResult(
                category="防火規制",
                verdict=Verdict.UNKNOWN,
                law_reference="建基法61条",
                summary=f"防火地域内 小規模建築物（{stories}階/{total_area:.0f}㎡）→ 外壁・軒裏の防火性能確認が必要",
                details=[
                    f"防火地域区分: {fire_zone}",
                    f"構造種別: {structure} / 階数: {stories} / 延べ面積: {total_area}㎡",
                    "延べ面積100㎡以下2階以下の建築物は耐火建築物等でなくても可（法61条ただし書き）。",
                    "ただし外壁および軒裏を防火構造（法2条1項八号）にする必要があります。",
                ],
                caution="外壁・軒裏の防火構造（防火構造告示に適合する仕様）を現況確認してください。",
                recommendation="設計図書（仕様書）または現況で外壁・軒裏の防火構造を確認してください。",
            )

    # ── 準防火地域────────────────────────────────────────────────
    elif "準防火地域" in fire_zone:
        # 4階以上 or 延べ面積500㎡超 → 耐火建築物等（法62条）
        if stories >= 4 or total_area > 500:
            if is_wood and "耐火" not in fire_resistance:
                return JudgeResult(
                    category="防火規制",
                    verdict=Verdict.NONCONFORMING,
                    law_reference="建基法62条・令136条の2の2",
                    summary=f"準防火地域内 木造大規模（{stories}階/{total_area:.0f}㎡）→ 耐火建築物等が必要・既存不適格",
                    details=[
                        f"防火地域区分: {fire_zone}",
                        f"構造種別: {structure} / 階数: {stories} / 延べ面積: {total_area}㎡",
                        "建基法62条により、準防火地域内で4階以上または延べ面積500㎡超の建築物は耐火建築物等にしなければなりません。",
                    ],
                    caution="増改築・用途変更を行う場合、耐火建築物等への変更が求められることがあります。",
                    recommendation="建物の耐火性能を確認し、必要に応じて防火改修計画を立ててください。",
                )
            else:
                return JudgeResult(
                    category="防火規制",
                    verdict=Verdict.CONFORMING,
                    law_reference="建基法62条",
                    summary=f"準防火地域内 耐火性能適合（{stories}階/{total_area:.0f}㎡）",
                    details=[
                        f"防火地域区分: {fire_zone}",
                        f"構造種別: {structure} / 耐火性能: {fire_resistance or '入力なし'}",
                        "耐火建築物等として準防火地域の基準を満たしています。",
                    ],
                )
        # 3階以下かつ500㎡以下 → 準耐火建築物または防火構造で対応
        elif stories == 3 and is_wood:
            return JudgeResult(
                category="防火規制",
                verdict=Verdict.UNKNOWN,
                law_reference="建基法62条・令136条の2の2",
                summary=f"準防火地域内 木造3階建て → 準耐火建築物（45分）要件確認が必要",
                details=[
                    f"防火地域区分: {fire_zone}",
                    f"構造種別: {structure} / 階数: {stories} / 延べ面積: {total_area}㎡",
                    "準防火地域内の木造3階建ては準耐火建築物（イ-1: 45分準耐火）以上が必要です。",
                    "平成12年建告第1358号（準耐火構造の構造方法）への適合を確認する必要があります。",
                ],
                caution="準耐火構造（外壁・柱・床・梁の45分耐火仕様）を設計図書で確認してください。",
                recommendation="確認申請書の「準耐火構造」欄または仕様書で適合を確認してください。",
            )
        else:
            return JudgeResult(
                category="防火規制",
                verdict=Verdict.CONFORMING,
                law_reference="建基法62条",
                summary=f"準防火地域内 規制基準内（{stories}階/{total_area:.0f}㎡）",
                details=[
                    f"防火地域区分: {fire_zone}",
                    f"構造種別: {structure} / 階数: {stories} / 延べ面積: {total_area}㎡",
                    "準防火地域の耐火要件（4階以上・500㎡超）に該当せず、防火構造での対応が可能です。",
                ],
                caution="外壁・軒裏の防火構造については現況確認を推奨します。",
            )

    # ── 法22条区域──────────────────────────────────────────────────
    elif "22条" in fire_zone or "法22条" in fire_zone:
        return JudgeResult(
            category="防火規制",
            verdict=Verdict.CONFORMING,
            law_reference="建基法22条",
            summary="法22条区域 → 屋根不燃化要件のみ（現況確認推奨）",
            details=[
                f"防火地域区分: {fire_zone}",
                "建基法22条区域では屋根を不燃材料（瓦・スレート・金属板等）で葺く必要があります。",
                "防火地域・準防火地域ほどの厳しい耐火・準耐火要件は課されません。",
            ],
            caution="屋根材が不燃材料（瓦・スレート・ガルバリウム等）であることを現況確認してください。",
        )

    # ── 指定なし──────────────────────────────────────────────────
    else:
        # 令112条 面積区画: 延べ面積1500㎡超の場合は区画が必要
        if total_area > 1500:
            return JudgeResult(
                category="防火規制",
                verdict=Verdict.UNKNOWN,
                law_reference="建基法施行令112条",
                summary=f"防火地域等指定なし・延べ面積1500㎡超 → 面積区画（令112条）の確認が必要",
                details=[
                    f"防火地域区分: {fire_zone or '指定なし'}",
                    f"延べ面積: {total_area}㎡",
                    "建基法施行令112条により、延べ面積が1,500㎡を超える建築物は1,500㎡ごとに面積区画が必要です。",
                    "区画壁・区画床の耐火・準耐火構造および防火設備（甲種防火戸等）の設置が求められます。",
                ],
                caution="防火区画の設置状況を設計図書・現況で確認してください。",
                recommendation="住宅医詳細調査の際に防火区画の開口部・防火設備を確認してください。",
            )
        return JudgeResult(
            category="防火規制",
            verdict=Verdict.CONFORMING,
            law_reference="建基法61条・62条",
            summary="防火地域等の指定なし → 特別な防火規制なし",
            details=[
                f"防火地域区分: {fire_zone or '指定なし'}",
                "防火地域・準防火地域・法22条区域の指定がないため、特別な耐火・準耐火要件はありません。",
            ],
            recommendation="防火地域区分の確認は都市計画図（市区町村窓口・GIS）で確認できます。",
        )
