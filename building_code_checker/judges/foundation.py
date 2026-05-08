"""
基礎形式・劣化現況判定モジュール

根拠法令:
  - 建築基準法施行令 第38条（基礎）
  - 昭和46年建設省告示第109号（建築物の基礎の構造方法及び構造計算の基準）
  - 令和7年4月1日施行改正（無筋コンクリート基礎の禁止）
"""
from datetime import date
from . import BuildingData, JudgeResult, Verdict, parse_date

_UNREINFORCED_PROHIBITION_DATE = date(2025, 4, 1)  # 令和7年4月1日施行

_UNREINFORCED_KEYWORDS = {"無筋", "素コンクリート", "PCC", "無鉄筋"}
_STONE_KEYWORDS = {"玉石", "切石", "束石", "石場"}


def judge(data: BuildingData) -> JudgeResult:
    """基礎形式・劣化現況の既存不適格判定"""

    if data.foundation_type is None:
        return JudgeResult(
            category="基礎形式",
            verdict=Verdict.UNKNOWN,
            law_reference="建基法施行令38条",
            summary="基礎形式が未入力のため判定不能",
            caution="床下点検口から基礎を目視し、鉄筋の有無・形式（布基礎/ベタ基礎/玉石等）を確認してください。",
        )

    ft = data.foundation_type.strip()

    conf_date = None
    if data.confirmation_date:
        try:
            conf_date = parse_date(data.confirmation_date)
        except ValueError:
            pass

    # ── 玉石・石場建て（伝統工法）───────────────────────────────────
    if any(kw in ft for kw in _STONE_KEYWORDS):
        return JudgeResult(
            category="基礎形式",
            verdict=Verdict.NONCONFORMING,
            law_reference="建基法施行令38条・昭46建告第109号",
            summary="玉石基礎（伝統工法）→ 既存不適格",
            details=[
                f"基礎形式: {ft}",
                "建基法施行令38条は、地盤の長期・短期許容支持力に応じた基礎を要求しています。",
                "玉石基礎・石場建ては現行の基礎構造告示（昭46建告第109号）に該当しません。",
                "伝統的構法による限界耐力計算・時刻歴応答解析で設計された建物は別途扱いがあります。",
            ],
            caution=(
                "大規模改修・増築時に遡及適用が生じ、基礎補強が必要になることがあります。"
                "指定文化財・伝統的建造物群保存地区内の建物は教育委員会・行政との調整が必要です。"
            ),
            recommendation=(
                "床下の基礎・土台の劣化状況（蟻害・腐朽・不同沈下）を目視確認してください。"
                "伝統工法として再設計する場合は限界耐力計算または時刻歴応答解析が必要です。"
                "住宅医詳細調査での基礎現況確認を推奨します。"
            ),
        )

    # ── 無筋コンクリート基礎────────────────────────────────────────
    is_unreinforced = any(kw in ft for kw in _UNREINFORCED_KEYWORDS) or (
        "コンクリート" in ft and "無筋" in ft
    )
    # 明示的に有筋・ベタ・布基礎（有筋）なら除外
    if any(kw in ft for kw in ("有筋", "ベタ", "べた", "布基礎（", "地中梁")):
        is_unreinforced = False

    if is_unreinforced:
        if conf_date and conf_date >= _UNREINFORCED_PROHIBITION_DATE:
            return JudgeResult(
                category="基礎形式",
                verdict=Verdict.VIOLATION,
                law_reference="建基法施行令38条・令和7年4月改正",
                summary="無筋コンクリート基礎 × 令和7年4月以降確認 → 違反",
                details=[
                    f"基礎形式: {ft}",
                    f"確認済証交付日: {conf_date}",
                    "令和7年4月1日施行の改正により、無筋コンクリート基礎は全構造種別で禁止されました。",
                    "同日以降に確認申請を行った建築物に無筋基礎を使用することは建基法違反です。",
                ],
                caution="速やかに有筋基礎（鉄筋コンクリート布基礎またはベタ基礎）への変更設計が必要です。",
                recommendation="鉄筋コンクリート布基礎またはベタ基礎への入れ替え設計を行ってください。",
            )
        else:
            return JudgeResult(
                category="基礎形式",
                verdict=Verdict.NONCONFORMING,
                law_reference="建基法施行令38条・令和7年4月改正",
                summary="無筋コンクリート基礎 → 令和7年4月改正で既存不適格",
                details=[
                    f"基礎形式: {ft}",
                    f"確認済証交付日: {conf_date or '不明'}",
                    "令和7年4月1日施行の改正により、無筋コンクリート基礎は現行基準不適合となりました。",
                    "建設当時は適法でしたが、法改正により既存不適格建築物となります。",
                    "無筋コンクリートは中性化・ひび割れが進行しやすく、劣化リスクが高い傾向があります。",
                ],
                caution=(
                    "増改築・大規模改修を行う場合は基礎の補強・入れ替えが必要になることがあります。"
                    "現状維持（増改築なし）の場合は改修義務はありません。"
                ),
                recommendation=(
                    "床下調査で無筋基礎の状況・中性化・クラックを確認してください。"
                    "増改築計画がある場合は基礎補強（アンダーピニング・ベタ基礎化）の費用を試算します。"
                    "住宅医詳細調査での基礎コンクリート中性化試験を推奨します。"
                ),
            )

    # ── 現行基準適合（有筋布基礎・ベタ基礎等）──────────────────────
    return JudgeResult(
        category="基礎形式",
        verdict=Verdict.CONFORMING,
        law_reference="建基法施行令38条・昭46建告第109号",
        summary=f"基礎形式は現行基準に適合（{ft}）",
        details=[
            f"基礎形式: {ft}",
            "建基法施行令38条および昭46建告第109号が定める基礎の構造方法に適合しています。",
        ],
        recommendation=(
            "基礎の構造方法は適合していますが、劣化状況（蟻害・腐朽・クラック）の目視確認を推奨します。"
            "コンクリートの中性化・鉄筋の錆は住宅医詳細調査で確認します。"
        ),
    )
