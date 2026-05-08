"""
用途地域・用途変更判定モジュール

根拠法令:
  - 建築基準法 第48条（用途地域等における建築物の用途制限）
  - 建築基準法 別表第2（用途地域内の建築物の用途制限）
  - 建築基準法 第87条（用途変更に対するこの法律の準用）
"""
from . import BuildingData, JudgeResult, Verdict

# 用途地域別 禁止用途キーワード（法48条・別表第2 を簡易化）
# key: 用途地域名に含まれる文字列, value: 禁止用途キーワードリスト
_DISTRICT_PROHIBITIONS: list[tuple[str, list[str]]] = [
    ("工業専用地域", ["住宅", "共同住宅", "長屋", "病院", "学校", "店舗"]),
    ("工業地域",    ["住宅", "共同住宅", "病院", "学校", "幼稚園", "保育所"]),
    ("第一種低層住居専用地域", ["工場", "倉庫", "店舗", "事務所", "旅館", "ホテル", "病院", "ボーリング"]),
    ("第二種低層住居専用地域", ["工場", "倉庫", "旅館", "ホテル", "病院"]),
    ("第一種中高層住居専用地域", ["工場", "倉庫", "旅館", "ホテル", "パチンコ"]),
    ("第二種中高層住居専用地域", ["工場", "倉庫"]),
    ("第一種住居地域", ["工場"]),
]

# 別表第1（法87条 用途変更 確認申請が必要な特殊建築物）
_SPECIAL_BUILDINGS = [
    "劇場", "映画館", "演芸場", "観覧場", "公会堂", "集会場",
    "病院", "診療所", "旅館", "ホテル",
    "共同住宅", "寄宿舎", "下宿",
    "百貨店", "物品販売業を営む店舗", "マーケット",
    "倉庫", "自動車車庫", "工場",
]

USE_CHANGE_PERMIT_AREA = 200.0  # 法87条: 特殊建築物への用途変更で確認申請が必要な床面積の閾値（㎡）


def _find_prohibited(use_district: str, use: str) -> list[str]:
    """指定の用途地域で禁止されているキーワードを探す"""
    for district_keyword, prohibitions in _DISTRICT_PROHIBITIONS:
        if district_keyword in use_district:
            return [p for p in prohibitions if p in use]
    return []


def judge(data: BuildingData) -> JudgeResult:
    """用途地域・用途制限・用途変更の適合性判定"""

    use_district = data.use_district
    building_use = data.building_use
    planned_use = data.planned_use
    total_area = data.total_floor_area or 0.0

    if use_district is None:
        return JudgeResult(
            category="用途地域・用途制限",
            verdict=Verdict.UNKNOWN,
            law_reference="建基法48条・別表2",
            summary="用途地域が未入力のため判定不能",
            caution="用途地域は都市計画図（市区町村窓口・GIS）で確認できます。",
        )

    if building_use is None:
        return JudgeResult(
            category="用途地域・用途制限",
            verdict=Verdict.UNKNOWN,
            law_reference="建基法48条・別表2",
            summary="建物用途が未入力のため判定不能",
            caution="建物の現在の用途を入力してください（住宅・店舗・事務所・倉庫等）。",
        )

    # ── 現在の用途が用途地域に違反していないか────────────────────
    current_hits = _find_prohibited(use_district, building_use)
    if current_hits:
        return JudgeResult(
            category="用途地域・用途制限",
            verdict=Verdict.VIOLATION,
            law_reference="建基法48条・別表2",
            summary=f"{use_district}内の「{building_use}」→ 用途制限違反",
            details=[
                f"用途地域: {use_district}",
                f"建物用途: {building_use}",
                f"禁止用途に該当: {', '.join(current_hits)}",
                f"建基法48条・別表第2により、{use_district}では「{'/'.join(current_hits)}」の建築は禁止されています。",
                "既存の建物が禁止用途で使用されている場合は違反建築物（建基法9条是正命令の対象）となります。",
            ],
            caution=(
                "禁止用途の建物は売買・住宅ローン融資・火災保険適用に支障が出る場合があります。"
                "用途変更を計画する場合は建築主事への確認が必要です。"
            ),
            recommendation=(
                "適法な用途への変更または行政（建築主事）との協議を行ってください。"
                "特例許可（法48条ただし書き）の適用可否を行政に確認することも検討してください。"
            ),
        )

    # ── 用途変更チェック (planned_use が入力されている場合)──────────
    if planned_use and planned_use != building_use:
        planned_hits = _find_prohibited(use_district, planned_use)
        if planned_hits:
            return JudgeResult(
                category="用途地域・用途制限",
                verdict=Verdict.VIOLATION,
                law_reference="建基法48条・87条・別表2",
                summary=f"計画用途「{planned_use}」→ {use_district}内での用途変更は不可",
                details=[
                    f"用途地域: {use_district}",
                    f"現在の用途: {building_use}",
                    f"計画用途: {planned_use}",
                    f"禁止用途に該当: {', '.join(planned_hits)}",
                    f"建基法48条・別表第2により、{use_district}では「{'/'.join(planned_hits)}」への変更は禁止されています。",
                ],
                caution="計画中の用途変更は建基法違反となります。別の用途を検討してください。",
                recommendation=(
                    "用途変更の可否について行政窓口（建築主事）に事前相談してください。"
                    "特例許可（法48条ただし書き）の適用可否も確認してください。"
                ),
            )

        needs_permit = (
            total_area > USE_CHANGE_PERMIT_AREA and
            any(sb in planned_use for sb in _SPECIAL_BUILDINGS)
        )
        if needs_permit:
            return JudgeResult(
                category="用途地域・用途制限",
                verdict=Verdict.UNKNOWN,
                law_reference="建基法87条",
                summary=f"用途変更（→「{planned_use}」・{total_area:.0f}㎡）→ 確認申請が必要",
                details=[
                    f"用途地域: {use_district}",
                    f"現在の用途: {building_use}",
                    f"計画用途: {planned_use}",
                    f"延べ面積: {total_area}㎡（{USE_CHANGE_PERMIT_AREA:.0f}㎡超）",
                    "建基法87条により、特殊建築物（別表第1）への用途変更で床面積が200㎡を超える場合は確認申請が必要です。",
                    f"「{planned_use}」は法別表第1に定める特殊建築物に該当します。",
                ],
                caution="確認申請を行わずに用途変更することは建基法違反です。",
                recommendation=(
                    "用途変更の確認申請を建築主事に提出してください。"
                    "申請にあたり避難規定・防火規制等の現行基準への適合も確認が必要です。"
                ),
            )
        else:
            return JudgeResult(
                category="用途地域・用途制限",
                verdict=Verdict.CONFORMING,
                law_reference="建基法87条・48条・別表2",
                summary=f"用途変更（→「{planned_use}」）→ 確認申請不要・用途制限に適合",
                details=[
                    f"用途地域: {use_district}",
                    f"計画用途: {planned_use}",
                    f"延べ面積: {total_area}㎡（200㎡以下 または 非特殊建築物）",
                    "建基法87条の確認申請は不要です。用途地域の用途制限にも適合しています。",
                ],
                recommendation=(
                    "確認申請は不要ですが、用途変更後も消防法・建基法の維持保全義務があります。"
                    "内装制限・避難規定に変更が生じないか確認してください。"
                ),
            )

    # ── 現在の用途が適合（用途変更なし）───────────────────────────
    return JudgeResult(
        category="用途地域・用途制限",
        verdict=Verdict.CONFORMING,
        law_reference="建基法48条・別表2",
        summary=f"{use_district}内「{building_use}」→ 用途制限に適合",
        details=[
            f"用途地域: {use_district}",
            f"建物用途: {building_use}",
            f"建基法48条・別表第2に基づき、{use_district}内での「{building_use}」は許容されています。",
        ],
        recommendation=(
            "用途地域の用途制限は満たしています。"
            "用途変更を計画する場合は「計画用途」を入力して改めて判定してください。"
        ),
    )
