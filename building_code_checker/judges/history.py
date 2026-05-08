"""
建築基準法 改正履歴データベース

出典:
  - 国土交通省「既存建築物の現況調査ガイドライン（第3版）」令和7年11月
  - 建築基準法 既存不適格早見表（同ガイドライン別紙）
  - 建築基準法施行令 各条文改正履歴

確認済証交付日を起点に、それ以降に施行された改正条文を全件チェックし、
既存不適格・要確認の一覧表を生成する。

種別:
  法規  = 建築基準法上の既存不適格（法的義務）
  性能  = 性能基準・推奨指針（法的既存不適格ではないが診断上重要）

緩和区分（renovation_exemption）:
  増築可  = 増築・改築でも緩和適用あり（既存不適格を継続できる）
  増築不可 = 増築・改築では緩和なし（現行規定への適合が必要）
  修繕可  = 大規模修繕・模様替のみ緩和あり
  用途可  = 用途変更でも緩和適用あり
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Callable, Optional

from . import BuildingData, JudgeResult, Verdict, parse_date


@dataclass
class LawRevision:
    """建築基準法 改正1件分のデータ"""
    effective_date: date
    article: str              # 条文番号
    category: str             # カテゴリ
    kind: str                 # "法規" or "性能"
    name: str                 # 規定名
    description: str          # 改正内容
    nonconforming_note: str   # 既存不適格・要注意の理由
    recommendation: str       # 対応推奨
    renovation_exemption: str = "増築可"  # 緩和区分（上記docstring参照）
    affected_structures: Optional[list] = None  # None=全構造
    extra_check: Optional[Callable[[BuildingData], bool]] = None


# ── 構造判定ヘルパー ─────────────────────────────────────────────
_WOOD = {"木造", "W", "木", "木構造"}
_RC   = {"RC", "鉄筋コンクリート", "SRC", "鉄骨鉄筋コンクリート"}
_S    = {"鉄骨", "S", "S造"}


def _is_wood(d: BuildingData) -> bool:
    return d.structure_type in _WOOD if d.structure_type else True  # 不明は該当扱い

def _is_rc(d: BuildingData) -> bool:
    return d.structure_type in _RC if d.structure_type else False

def _is_not_wood(d: BuildingData) -> bool:
    return d.structure_type not in _WOOD if d.structure_type else False


# ════════════════════════════════════════════════════════════════════
# 建築基準法 改正履歴データベース
# 出典: 既存建築物の現況調査ガイドライン（第3版）令和7年11月 別紙・早見表
# ════════════════════════════════════════════════════════════════════
REVISIONS: list[LawRevision] = [

    # ────────────────────────────────────────────────────────────────
    # 接道・敷地
    # ────────────────────────────────────────────────────────────────
    LawRevision(
        effective_date=date(1950, 11, 23),
        article="建基法43条①",
        category="接道", kind="法規",
        name="接道義務（建築基準法制定）",
        description="都市計画区域内の建築物の敷地は幅員4m以上の道路に2m以上接しなければならない。",
        nonconforming_note="法制定（S25）以前に建てられた建物は接道義務を満たしていない場合がある。",
        recommendation="前面道路幅員・接道長さを現地確認し、42条2項道路（みなし道路）のセットバック有無を確認する。",
        renovation_exemption="増築不可",
    ),
    LawRevision(
        effective_date=date(1950, 11, 23),
        article="建基法19条④・施行令80条の3",
        category="敷地", kind="法規",
        name="がけ崩れ・擁壁の安全対策",
        description="高さ2m超のがけに近接して建築物を建てる場合の擁壁設置・離隔距離の確保。",
        nonconforming_note="がけ・擁壁の現況が現行基準を満たしていない場合がある。",
        recommendation="がけ・擁壁の状態を現地確認し、必要に応じて構造計算による安全確認を実施する。",
        renovation_exemption="増築可",
    ),

    # ────────────────────────────────────────────────────────────────
    # 構造耐力・基礎
    # ────────────────────────────────────────────────────────────────
    LawRevision(
        effective_date=date(1965, 12, 2),
        article="建基法31条①・施行令35条",
        category="衛生", kind="法規",
        name="処理区域内の水洗便所義務化",
        description="下水道処理区域内での水洗便所の義務化（S40改正）。非水洗式トイレの継続使用が禁止。",
        nonconforming_note="1965年以前に建てられた建物で下水道整備後も汲み取り式便所のままの場合は既存不適格。",
        recommendation="下水道処理区域内であれば水洗化改修が必要。市区町村の下水道整備区域の確認を行う。",
        renovation_exemption="増築可",
    ),
    LawRevision(
        effective_date=date(1971, 1, 1),
        article="建基法施行令38条・令3章3節（S46大改正）",
        category="構造", kind="法規",
        name="基礎の構造方法制定・木造仕様規定強化（昭46施行令改正）",
        description=(
            "令38条（基礎の構造方法）制定。柱の有効細長比規定、"
            "風圧力に対する必要壁量の追加、継手仕口のボルト締に座金の義務付け、"
            "外壁内部の防蟻措置義務化（令42・43・46・47・49改正）。"
        ),
        nonconforming_note=(
            "1971年以前の建物は基礎の構造規定（令38条）が適用されておらず、"
            "コンクリート無筋基礎・不十分な根入れ深さの可能性がある。"
            "木造では必要壁量・継手仕口の強化基準未適用。"
        ),
        recommendation=(
            "基礎の種類（布基礎・ベタ基礎）と配筋有無を床下調査で確認する。"
            "外壁内部の防蟻処理（蟻害・腐朽）を目視・触診で確認。"
        ),
        renovation_exemption="増築可",
    ),
    LawRevision(
        effective_date=date(1971, 1, 1),
        article="建基法35条の2・施行令128条の3の2〜128条の5（昭46制定）",
        category="防火", kind="法規",
        name="内装制限（火気使用室・特殊建築物）",
        description=(
            "火気使用室・特殊建築物の内装材に不燃・準不燃材料使用を義務付け（法35の2）。"
            "調理室・浴室等の壁・天井に難燃化規定導入。"
        ),
        nonconforming_note=(
            "1971年以前の建物は火気使用室（台所・浴室等）の内装が規制対象外。"
            "可燃性内装材（板張り・壁紙等）が使用されている可能性がある。"
        ),
        recommendation=(
            "台所・浴室の内装材（壁・天井）を確認し、不燃・準不燃材料への更新を検討する。"
            "リノベーション時に合わせて更新すると費用対効果が高い。"
        ),
        renovation_exemption="増築可",
    ),
    LawRevision(
        effective_date=date(1971, 1, 1),
        article="建基法28条③・施行令20条の2〜3（昭46制定）",
        category="衛生", kind="法規",
        name="火気使用室の換気設備義務化",
        description=(
            "調理室・浴室・ボイラー室等の火気使用室に換気設備の設置を義務付け（法28条③新設）。"
            "換気回数・有効換気量の技術的基準を告示で規定。"
        ),
        nonconforming_note=(
            "1971年以前の建物は台所・浴室等の換気設備が設置されていない場合がある。"
            "不完全燃焼・CO中毒・結露・カビのリスクが高い。"
        ),
        recommendation=(
            "換気扇の設置状況と有効換気量（調理室: 床面積×40回/h相当）を確認する。"
            "レンジフードへの更新・換気口増設を改修時に合わせて実施する。"
        ),
        renovation_exemption="増築可",
    ),
    LawRevision(
        effective_date=date(1981, 6, 1),
        article="建基法20条・施行令36〜38条・46条（昭56改正）",
        category="耐震", kind="法規",
        name="新耐震基準（昭和56年施行令改正）",
        description=(
            "大地震（震度6強〜7）でも倒壊・崩壊しないことを要求。"
            "壁量計算の強化・偏心率規定の導入。圧縮筋かいの寸法規定強化。"
        ),
        nonconforming_note=(
            "旧耐震基準（中地震で損傷しない）の建物は現行基準を満たさない。"
            "耐震性能は現行基準の概ね1/2以下の可能性がある。"
        ),
        recommendation=(
            "耐震診断（一般診断法）→ Is値・q値確認 → 耐震補強計画。"
            "耐震改修促進法の補助金活用で費用の1/2〜2/3を補助できる場合がある。"
        ),
        renovation_exemption="増築可",
    ),
    LawRevision(
        effective_date=date(1987, 11, 16),
        article="建基法56条・別表第3（昭62改正）",
        category="形態", kind="法規",
        name="道路斜線制限の精緻化（昭62改正）",
        description=(
            "道路斜線制限の計算方法が精緻化され、前面道路の反対側の境界線からの水平距離で"
            "斜線勾配が変わる制度（適用距離）が導入された。"
        ),
        nonconforming_note="1987年以前の建物は現行の道路斜線算定方法で評価すると超過する場合がある。",
        recommendation=(
            "増築・改築時に道路斜線を再確認する。"
            "なお増築の場合は緩和規定（法86条の7）が適用されないため現行基準への適合が必要。"
        ),
        renovation_exemption="増築不可",
    ),
    LawRevision(
        effective_date=date(2000, 6, 1),
        article="建基法施行令20条（H12建告1460→1436号改正）",
        category="一般構造", kind="法規",
        name="居室の採光補正係数の導入（H12告示改正）",
        description=(
            "居室の採光計算に採光補正係数（用途地域・隣地境界からの距離等による補正）が導入された。"
            "有効採光面積 = 窓面積 × 採光補正係数で計算するように変更。"
        ),
        nonconforming_note=(
            "H12年以前の建物は旧基準（単純な開口比率）で設計されており、"
            "現行の採光補正係数で再計算すると居室として不適格になる部屋がある場合がある。"
        ),
        recommendation=(
            "採光不足の居室は天窓・トップライトの追加・間仕切り変更等で採光を確保する。"
            "用途変更時（居室が増える場合）は採光計算の確認が必要。"
        ),
        renovation_exemption="増築可",
    ),
    LawRevision(
        effective_date=date(2000, 6, 1),
        article="建基法施行令23〜26条（H12建告1352号）",
        category="一般構造", kind="法規",
        name="階段の手すり設置義務化（H12改正）",
        description=(
            "令23〜26条改正により、階段・踊り場に手すりの設置が義務付けられた。"
            "けあげ・踏面の寸法基準も細分化。"
        ),
        nonconforming_note=(
            "2000年以前に確認申請された建物は手すりが未設置・不適格な場合がある。"
            "特に急勾配階段（けあげ高い・踏面浅い）は転落リスクが高い。"
        ),
        recommendation=(
            "階段の手すり設置状況を確認し、未設置の場合は改修時に設置する。"
            "手すりの設置は介護保険住宅改修の対象でもあるため、施主の状況に応じて活用を提案する。"
        ),
        renovation_exemption="増築可",
    ),
    LawRevision(
        effective_date=date(2000, 6, 1),
        article="平12建告第1460号（現: H12建告1349号）・施行令42〜47条",
        category="耐震", kind="法規",
        name="木造2000年基準（接合金物・耐力壁バランス・基礎仕様）",
        description=(
            "柱頭柱脚の接合金物仕様の明確化（N値計算）、"
            "耐力壁の偏心率規定（四分割法、偏心率0.3以下）、"
            "基礎の配筋仕様の具体化（H12建告1347：布基礎・ベタ基礎の鉄筋仕様）。"
        ),
        nonconforming_note=(
            "1981〜2000年の木造は接合金物・耐力壁バランス・基礎配筋が現行基準未満の可能性。"
            "阪神淡路大震災（1995年）でこの世代の被害が多数確認されている。"
        ),
        recommendation=(
            "N値計算・四分割法による耐力壁バランス確認。"
            "床下・小屋裏目視で接合金物（かすがい留め等）の有無を確認。"
            "耐震補強と断熱改修の一体計画が費用対効果◎。"
        ),
        renovation_exemption="増築可",
        extra_check=_is_wood,
    ),
    LawRevision(
        effective_date=date(2003, 7, 1),
        article="建基法28条の2②・施行令20条の4〜9（H15施行）",
        category="衛生", kind="法規",
        name="シックハウス規制（ホルムアルデヒド・機械換気義務化）",
        description=(
            "居室内のホルムアルデヒド・クロルピリホスの規制（法28条の2三）、"
            "全居室に第3種以上の機械換気設備（0.5回/h以上）の設置義務化。"
        ),
        nonconforming_note=(
            "2003年以前の建物は24時間機械換気が未設置の場合がほとんど。"
            "内装材（合板・接着剤等）のF☆☆☆☆規格も未対応品の可能性がある。"
        ),
        recommendation=(
            "性能向上リノベ時に熱交換型換気システム（第1種）を導入すると断熱改修との相性良。"
            "内装仕上げ材はF☆☆☆☆品（ホルムアルデヒド放散量最小）を使用する。"
        ),
        renovation_exemption="増築可",
    ),
    LawRevision(
        effective_date=date(2006, 10, 1),
        article="建基法28条の2②（H18改正・石綿規制強化）",
        category="衛生", kind="法規",
        name="石綿（アスベスト）吹付け使用の全面禁止",
        description=(
            "建築材料への石綿含有材料の使用が全面禁止（法28条の2二改正）。"
            "解体・改修時の石綿使用建材の届出・飛散防止が義務化。"
        ),
        nonconforming_note=(
            "1975年以前の建物はアスベスト吹付け材（天井・梁等）が使用されている可能性が高い。"
            "1975〜2006年も一部含有建材（スレート・床材等）が残存している場合がある。"
        ),
        recommendation=(
            "解体・大規模改修前に石綿含有建材の調査を必ず実施する（大気汚染防止法の義務）。"
            "吹付け石綿は除去または封じ込め処理が必要（工事は専門業者が実施）。"
        ),
        renovation_exemption="増築可",
    ),
    LawRevision(
        effective_date=date(2006, 12, 20),
        article="バリアフリー法（高齢者・障害者等の移動等円滑化の促進に関する法律）",
        category="バリアフリー", kind="性能",
        name="バリアフリー法施行（旧ハートビル法・交通バリアフリー法を統合）",
        description=(
            "特定建築物（2,000m²以上の病院・ホテル・百貨店・共同住宅等）の"
            "バリアフリー基準適合が義務化（段差解消・手すり設置・トイレ整備等）。"
        ),
        nonconforming_note=(
            "特定建築物（2,000m²以上）に該当する場合、段差・手すり・出入口幅が既存不適格の可能性。"
            "一般住宅（個人邸）は努力義務のみ。"
        ),
        recommendation=(
            "住宅医診断時に高齢者・障害者の利用状況を確認し、"
            "手すり設置・段差解消・廊下幅確保を性能向上リノベに組み込む。"
            "介護保険住宅改修（上限20万円）との連携が可能。"
        ),
        renovation_exemption="増築可",
    ),
    LawRevision(
        effective_date=date(2007, 6, 20),
        article="建基法6条の3・20条改正（構造計算適合性判定）",
        category="構造", kind="法規",
        name="構造計算適合性判定制度の導入",
        description=(
            "一定規模以上の建築物の構造計算について第三者機関による適合性判定を義務化。"
            "ルートの明確化と審査手続きの厳格化。"
        ),
        nonconforming_note=(
            "2007年以前の中規模建築物は構造計算の第三者確認が未実施の可能性がある。"
            "直接の既存不適格ではないが、大規模改修・増築時に現行基準での再検討が必要。"
        ),
        recommendation=(
            "大規模改修・増築時は現行の構造計算基準（許容応力度計算・限界耐力計算等）に基づく再検討。"
            "既存躯体の強度試験（コンクリートコア圧縮強度試験等）を合わせて実施することを推奨。"
        ),
        renovation_exemption="増築可",
    ),

    # ────────────────────────────────────────────────────────────────
    # 省エネ（建基法・省エネ法）
    # ────────────────────────────────────────────────────────────────
    LawRevision(
        effective_date=date(1980, 10, 1),
        article="省エネ法・昭55基準（旧建設省告示）",
        category="省エネ", kind="性能",
        name="第1次省エネ基準（昭和55年基準）",
        description=(
            "住宅断熱に関する日本初の省エネ基準。"
            "地域区分に応じた熱損失係数（Q値）と熱貫流率（U値）を規定。"
        ),
        nonconforming_note=(
            "1980年以前の建物は断熱材未施工または基準以下の可能性が高い。"
            "※省エネ基準は既存建物の法的既存不適格には直接該当しない（性能基準）。"
        ),
        recommendation=(
            "床下・壁・天井の断熱材有無と種類・厚さを確認する（床下目視・壁内サーモカメラ等）。"
            "断熱改修による暖房エネルギー削減・結露防止を優先提案する。"
        ),
        renovation_exemption="増築可",
    ),
    LawRevision(
        effective_date=date(1992, 10, 1),
        article="省エネ法・平4基準",
        category="省エネ", kind="性能",
        name="第2次省エネ基準（平成4年基準）",
        description="Q値・μ値（日射取得係数）の強化、防湿層規定の追加。結露対策の基準化。",
        nonconforming_note=(
            "1992年以前の基準で建てられた建物はQ値が大きく省エネ性能が低い。"
            "防湿層がなく内部結露による木材腐朽リスクが高い世代。"
        ),
        recommendation="開口部（サッシ・ガラス）の断熱改修が費用対効果最高。内窓（インナーサッシ）設置が手軽で効果大。",
        renovation_exemption="増築可",
    ),

    # ────────────────────────────────────────────────────────────────
    # 用途地域・形態規制
    # ────────────────────────────────────────────────────────────────
    LawRevision(
        effective_date=date(1992, 6, 25),
        article="建基法48条・別表第2（H4改正・H5施行）",
        category="用途", kind="法規",
        name="用途地域の細分化（8種類→12種類）",
        description=(
            "住居系用途地域が細分化（第1〜2種低層・第1〜2種中高層・第1〜2種住居・準住居）。"
            "地域によっては容積率・建ぺい率・用途制限が変更された。"
        ),
        nonconforming_note=(
            "細分化前に適法だった用途・形態が細分化後の用途地域制限に抵触する場合がある。"
            "特に店舗・事務所等を兼用している住宅は用途規制の確認が必要。"
        ),
        recommendation=(
            "現在の用途地域を市区町村の都市計画情報（GIS等）で確認する。"
            "建物用途と現行の用途制限を照合する。用途変更時は緩和なく現行規定が適用される。"
        ),
        renovation_exemption="増築可",
    ),
    LawRevision(
        effective_date=date(1999, 10, 1),
        article="省エネ法・平11基準（次世代省エネ基準）",
        category="省エネ", kind="性能",
        name="第3次省エネ基準（平成11年・次世代省エネ基準）",
        description=(
            "Q値・C値（相当隙間面積）の大幅強化。高断熱・高気密の基準化。"
            "地域区分ごとの目標Q値が現行の約1/2程度に引き下げられた。"
        ),
        nonconforming_note=(
            "1999年以前の建物は気密性能（C値）・断熱性能（Q値）が次世代基準を下回る可能性が高い。"
            "隙間風・結露・冷暖房費の高さとして体感されることが多い。"
        ),
        recommendation=(
            "外皮性能の現況診断（赤外線サーモカメラ・気密測定）を実施し改修優先順位を設定。"
            "HEAT20 G1グレード（UA値 0.48 W/m²K・6地域）を目標に断熱計画を立てる。"
        ),
        renovation_exemption="増築可",
    ),
    LawRevision(
        effective_date=date(2013, 10, 1),
        article="建基法・平25省エネ基準（UA値・ηAC値・BEI）",
        category="省エネ", kind="性能",
        name="第4次省エネ基準（平成25年基準）UA値・一次エネルギー消費量",
        description=(
            "外皮性能指標をQ値→UA値・ηAC値に刷新。"
            "一次エネルギー消費量基準（BEI）を新設。"
            "地域区分を6→8区分に変更（四国・九州等が細分化）。"
        ),
        nonconforming_note=(
            "2013年以前の建物は現行の省エネ基準指標（UA値）での評価が基準値（6地域: 0.87）を上回る可能性大。"
            "2025年4月より新築は省エネ基準適合が建築確認の要件（既存は対象外）。"
        ),
        recommendation=(
            "UA値・ηAC値の推定計算（簡易計算ツール等）を診断時に実施。"
            "性能向上リノベ補助金（子育てエコホーム支援事業・先進的窓リノベ）の活用を検討。"
            "BELS取得で省エネ性能の見える化 → 売買・賃貸時の資産価値向上に有効。"
        ),
        renovation_exemption="増築可",
    ),
    LawRevision(
        effective_date=date(2015, 6, 1),
        article="建基法35条・施行令120〜126条の7（H27改正）",
        category="防火", kind="法規",
        name="避難規定・防火設備の強化",
        description=(
            "共同住宅・寄宿舎等の特殊建築物における避難安全性能の強化。"
            "スプリンクラー設備設置義務の対象拡大。"
        ),
        nonconforming_note=(
            "共同住宅・寄宿舎・診療所等の特殊建築物では避難通路・設備が既存不適格の可能性。"
            "一般住宅（一戸建て）は直接の対象外だが改修時に確認が必要。"
        ),
        recommendation=(
            "特殊建築物（共同住宅等）に用途変更する場合は避難規定の遡及適用に注意。"
            "消防設備（自動火災報知機・誘導灯等）の現況確認と更新を推奨。"
        ),
        renovation_exemption="増築可",
    ),
    LawRevision(
        effective_date=date(2019, 6, 25),
        article="建基法87条・施行令137条の18（R元改正）",
        category="用途", kind="法規",
        name="既存建物の用途変更規制緩和（200m²未満は確認申請不要）",
        description=(
            "用途変更の確認申請が必要な規模を100m²超→200m²超に緩和。"
            "既存建物の活用・リノベーションを促進するための改正。"
        ),
        nonconforming_note=(
            "200m²未満の用途変更は確認申請不要になったが、"
            "建築基準法・消防法の技術的基準は遵守が必要（申請不要≠規制不適用）。"
        ),
        recommendation=(
            "空き家・古民家を宿泊施設・店舗・診療所等に活用する際は"
            "技術的基準（採光・換気・避難・防火）の確認を行ってから改修計画を立てる。"
        ),
        renovation_exemption="増築可",
    ),
    LawRevision(
        effective_date=date(2022, 1, 1),
        article="建基法施行令39条・昭46建告109号（R4改正）",
        category="構造", kind="法規",
        name="瓦屋根の緊結方法強化（令4年1月施行）",
        description=(
            "屋根ふき材・外装材の緊結方法に関する告示（昭46建告109号）改正。"
            "瓦屋根について棟部・一般部ともに全数緊結が義務付けられた（台風・地震対策）。"
        ),
        nonconforming_note=(
            "2022年以前の瓦屋根（特に棟部分）は緊結不足の場合が多い。"
            "令3年度の地震・台風でも瓦の飛散・脱落被害が多数報告されている。"
        ),
        recommendation=(
            "屋根の瓦の緊結状態（棟・一般部）を目視確認する。"
            "緊結不足の場合は漆喰塗り直し・金属製緊結金物への取替えを提案する。"
        ),
        renovation_exemption="増築可",
    ),
    LawRevision(
        effective_date=date(2024, 4, 1),
        article="建築物省エネ法 第12条・国交省告示（R6.4施行）",
        category="省エネ", kind="法規",
        name="非住宅大規模建築物（2,000㎡以上）BEI基準引上げ",
        description=(
            "延べ床面積2,000㎡以上の非住宅建築物（大規模）の一次エネルギー消費量基準（BEI）が引上げ。"
            "用途別: 工場等 BEI≦0.75 ／ 事務所等・学校等・ホテル等・百貨店等 BEI≦0.80 ／"
            "病院等・飲食店等・集会所等 BEI≦0.85。"
            "中規模（300〜2,000㎡未満）は2026年4月より同水準への引上げ予定（未施行）。"
        ),
        nonconforming_note=(
            "2024年4月以前に建設された大規模非住宅（2,000㎡以上）は用途別BEI基準を超過している可能性がある。"
            "増改築・用途変更時に省エネ適合義務の審査対象となる。"
        ),
        recommendation=(
            "大規模非住宅の増改築計画時はBEI計算（標準入力法・モデル建物法）で基準適合を確認する。"
            "2026年4月には中規模（300〜2,000㎡未満）も同水準への引上げ予定。"
        ),
        renovation_exemption="増築可",
        # 住宅・2,000㎡未満は対象外
        extra_check=lambda d: (
            d.total_floor_area is not None and d.total_floor_area >= 2000
            and d.building_use is not None
            and any(kw in (d.building_use or "") for kw in ["事務所", "学校", "ホテル", "病院", "工場", "倉庫", "飲食", "集会", "百貨店"])
        ),
    ),
    LawRevision(
        effective_date=date(2024, 6, 28),
        article="建築物省エネ法 附則・施行規則改正（R6.6.28施行）",
        category="省エネ", kind="性能",
        name="気候風土適応住宅の外皮基準適用除外の恒久化（伝統構法への配慮）",
        description=(
            "地域の気候風土に応じた建築物（気候風土適応住宅）について、"
            "外皮性能基準（U_A値・η_AC値）の適用除外が恒久化された。"
            "要件として「茅葺き屋根」「面戸板現し」「せがい造り」等の伝統的構法の使用が追加。"
            "一次エネルギー消費量基準（BEI≦1.0）の遵守は引き続き必要。"
        ),
        nonconforming_note=(
            "古民家・伝統構法住宅で気候風土適応住宅の要件を満たす場合、外皮基準の適用除外が利用可能。"
            "茅葺き・せがい造り等の要件に該当する建物は新規申請時に除外申請が可能。"
        ),
        recommendation=(
            "古民家再生・伝統構法の新築・改築時に気候風土適応住宅への認定申請を検討する。"
            "BEI基準は引き続き適用されるため、一次エネルギー消費量の計算は必要。"
        ),
        renovation_exemption="増築可",
    ),
    LawRevision(
        effective_date=date(2025, 4, 1),
        article="建基法6条改正・省エネ法改正（R7施行）",
        category="省エネ", kind="法規",
        name="新築住宅の省エネ基準適合義務化",
        description=(
            "新築住宅・非住宅建築物の省エネ基準適合が建築確認の要件となった。"
            "R7.4改正により、省エネ基準への適合状況は完了検査でも確認対象となった（法7条の2改正）。"
            "改正省エネ法による省エネ性能ラベル表示の努力義務も開始。"
        ),
        nonconforming_note=(
            "既存建物は義務化対象外。"
            "ただし新2号建築物（2階建て以上・200㎡超木造）の増改築・大規模修繕を行う場合は"
            "確認申請・完了検査において省エネ基準適合が審査対象となる。"
        ),
        recommendation=(
            "省エネ性能ラベル表示は努力義務だが、売買・賃貸の付加価値として有効。"
            "増改築時は確認申請・完了検査で省エネ基準適合（UA値・一次エネ）の審査が必要。"
            "大規模改修時はZEH水準（UA値 0.60・6地域）を目標に設計することを推奨。"
        ),
        renovation_exemption="増築可",
    ),
    LawRevision(
        effective_date=date(2025, 4, 1),
        article="建基法施行令38条・H12建告1347号改正（R7施行）",
        category="構造", kind="法規",
        name="全構造の無筋コンクリート基礎禁止（令7年4月施行）",
        description=(
            "H12建告1347号（基礎の構造方法）改正により、"
            "木造・鉄骨造を含む全構造において無筋コンクリート基礎が正式に禁止された。"
            "布基礎・ベタ基礎ともに鉄筋配筋が必須要件となった。"
        ),
        nonconforming_note=(
            "2025年4月以前に建てられた建物で無筋コンクリート基礎（素掘り基礎・石積み基礎含む）は既存不適格。"
            "特に1981年以前の木造・鉄骨造の無筋基礎は多数存在する。"
            "古民家（石場建て・土台直置き等）も対象となる場合がある。"
        ),
        recommendation=(
            "基礎の種類と配筋有無を床下目視・地中レーダー探査で確認する。"
            "無筋基礎の場合は増築・改築時に鉄筋入り布基礎・ベタ基礎への補強を計画する。"
            "古民家再生では石場建て等の伝統構法特例（法40条・H24国交省告示）の適用可否を確認する。"
        ),
        renovation_exemption="増築可",
    ),
    LawRevision(
        effective_date=date(2025, 4, 1),
        article="建基法施行令43条・46条・S56建告1100号・H12建告1349号改正（R7施行）",
        category="耐震", kind="法規",
        name="木造の柱の小径・必要壁量の強化（令7年4月施行）",
        description=(
            "令43条（柱の小径）・令46条（壁量計算）の改正により、"
            "木造建築物の柱の断面寸法と耐力壁の必要量が強化された。"
            "必要壁量の計算には方法A（S56建告1100号改正の早見表）と"
            "方法B（howtec.or.jp公式計算ツール）の2方法が使用できる。"
            "準耐力壁等（筋かい未満の壁）は必要壁量の1/2まで算入可（令46条5項新設）。"
            "階高3.2m超の筋かいは壁倍率を低減（αh = 3.5 × 柱間隔/階高）。"
        ),
        nonconforming_note=(
            "2025年4月以前の木造建築物は改正後の必要壁量を満たさない場合がある。"
            "特に比較的大きな開口部（連窓・掃き出し窓等）を多用した設計の建物は要注意。"
            "経過措置（R7.4〜R8.3.31着工）: 地上2以下・高さ13m以下・軒高9m以下・"
            "延べ300㎡以下の木造は改正前の壁量基準（旧S56建告1100号）を選択適用できる。"
        ),
        recommendation=(
            "改正壁量基準（令46条・S56建告1100号改正）で必要壁量を再計算し、"
            "不足する場合は耐力壁増設・面材耐力壁（最大4.3倍）への補強を計画する。"
            "準耐力壁（土塗り壁0.5倍・小舞壁等）を最大1/2まで活用することで補強コストを抑制できる。"
            "既存不適格として緩和規定の適用対象となるため増築等でも継続使用は可能。"
        ),
        renovation_exemption="増築可",
        extra_check=_is_wood,
    ),

    # ────────────────────────────────────────────────────────────────
    # 手続（令7年4月改正）
    # ────────────────────────────────────────────────────────────────
    LawRevision(
        effective_date=date(2025, 4, 1),
        article="建基法6条改正・4号特例廃止（R7.4施行）",
        category="手続", kind="法規",
        name="4号特例廃止・2階建て木造への確認申請拡大（令7年4月施行）",
        description=(
            "従来「4号特例」として確認申請・審査省略の対象だった2階建て木造・小規模建築物について、"
            "増築・改築・大規模修繕・大規模模様替を行う場合に確認申請・完了検査が必要になった。"
            "都市計画区域外の小規模木造も増改築時に新たに確認申請対象となった。"
            "新区分: 新2号（2階以上 or 200㎡超木造）・新3号（平屋 and 200㎡以下木造）。"
        ),
        nonconforming_note=(
            "R7.4以降、2階建て木造（新2号）の増改築・大規模修繕を行う際は確認申請・完了検査が必要。"
            "過去に4号特例で確認申請なし・完了検査なしで増改築した部分は、"
            "次回改修時に構造・省エネを含む全規定の審査対象となる。"
            "経過措置（R7.4〜R8.3.31着工）: 地上2以下・高さ13m以下・軒高9m以下・"
            "延べ300㎡以下の木造は改正前の審査基準を選択適用できる。"
        ),
        recommendation=(
            "増改築・大規模修繕の計画前に新2号/新3号の区分を確認し、確認申請スケジュールを設定する。"
            "4号特例廃止により、設計段階から構造計算・省エネ審査を前提とした計画が必要。"
            "確認申請なし・検査済証なしの既存増築部分がある場合は現況調査で適合状況を先行確認する。"
        ),
        renovation_exemption="増築可",
        extra_check=_is_wood,
    ),
    LawRevision(
        effective_date=date(2025, 4, 1),
        article="建基法7条の6改正（R7.4施行）",
        category="手続", kind="法規",
        name="2階建て木造一戸建てへの使用制限適用（令7年4月施行）",
        description=(
            "R7.4改正により、2階建て木造一戸建て住宅（新2号）も完了検査を受けるまで使用制限の対象となった。"
            "検査済証の交付前に使用を開始することが正式に禁止された（建基法7条の6改正）。"
            "完了検査では構造規定の適合確認に加え、省エネ基準への適合状況も審査される（法7条の2改正）。"
            "同一敷地内での建て替え時の仮使用認定制度（指定確認検査機関による）が活用可能。"
        ),
        nonconforming_note=(
            "R7.4以降に確認申請を取得した2階建て木造住宅（新2号）は、"
            "完了検査（省エネ基準の確認含む）を受けずに居住すると違反となる。"
            "既存建物（R7.4以前の検査済証交付済み）への遡及適用はない。"
        ),
        recommendation=(
            "新築・増改築計画では必ず完了検査を取得してから入居する。"
            "完了検査では省エネ基準適合（UA値・一次エネルギー消費量）の書類確認が行われるため、"
            "設計段階から省エネ計算を実施し確認申請時に提出しておく。"
            "同一敷地内で住み替えを伴う建て替えは「仮使用認定」の活用を検討する（"
            "工事部分と仮使用部分を防火上有効に区画することが条件）。"
        ),
        renovation_exemption="増築可",
        extra_check=_is_wood,
    ),
]


# ── 判定関数 ──────────────────────────────────────────────────────

def judge(data: BuildingData) -> JudgeResult:
    """確認済証交付日を起点とした建築基準法改正 既存不適格一覧表を生成する"""

    if data.confirmation_date is None:
        return JudgeResult(
            category="法改正 既存不適格一覧",
            verdict=Verdict.UNKNOWN,
            law_reference="建築基準法 各条文",
            summary="確認済証交付日が未入力のため判定不能",
            caution="確認済証・設計図書・台帳記載事項証明書で交付日を確認してください。",
        )

    try:
        conf_date = parse_date(data.confirmation_date)
    except ValueError:
        return JudgeResult(
            category="法改正 既存不適格一覧",
            verdict=Verdict.UNKNOWN,
            law_reference="建築基準法 各条文",
            summary=f"確認済証交付日の形式が不正: {data.confirmation_date}",
        )

    rows = []

    for rev in REVISIONS:
        # 構造条件チェック
        if rev.extra_check and not rev.extra_check(data):
            rows.append({
                "施行日":     str(rev.effective_date),
                "カテゴリ":   rev.category,
                "種別":       rev.kind,
                "条文":       rev.article,
                "規定名":     rev.name,
                "判定":       "➖ 対象外",
                "増築緩和":   rev.renovation_exemption,
                "理由":       f"構造種別（{data.structure_type or '不明'}）は適用外",
                "推奨対応":   "-",
            })
            continue

        if conf_date < rev.effective_date:
            verdict_str = "⚠️ 既存不適格" if rev.kind == "法規" else "⚠️ 要確認（性能）"
            rows.append({
                "施行日":     str(rev.effective_date),
                "カテゴリ":   rev.category,
                "種別":       rev.kind,
                "条文":       rev.article,
                "規定名":     rev.name,
                "判定":       verdict_str,
                "増築緩和":   rev.renovation_exemption,
                "理由":       rev.nonconforming_note,
                "推奨対応":   rev.recommendation,
            })
        else:
            rows.append({
                "施行日":     str(rev.effective_date),
                "カテゴリ":   rev.category,
                "種別":       rev.kind,
                "条文":       rev.article,
                "規定名":     rev.name,
                "判定":       "✅ 適法",
                "増築緩和":   rev.renovation_exemption,
                "理由":       f"確認日（{conf_date}）は施行日以降",
                "推奨対応":   "-",
            })

    ng_law   = sum(1 for r in rows if r["判定"] == "⚠️ 既存不適格")
    ng_perf  = sum(1 for r in rows if r["判定"] == "⚠️ 要確認（性能）")
    skip     = sum(1 for r in rows if r["判定"] == "➖ 対象外")
    ok       = len(rows) - ng_law - ng_perf - skip

    # 増築不可（緩和なし）の既存不適格を抽出
    ng_no_exemption = [
        r for r in rows
        if r["判定"] == "⚠️ 既存不適格" and r["増築緩和"] == "増築不可"
    ]

    if ng_law > 0:
        verdict = Verdict.NONCONFORMING
        summary = f"法規上の既存不適格 {ng_law} 件 ／ 性能要確認 {ng_perf} 件（確認日: {conf_date}）"
    elif ng_perf > 0:
        verdict = Verdict.UNKNOWN
        summary = f"法規適合・性能要確認 {ng_perf} 件（確認日: {conf_date}）"
    else:
        verdict = Verdict.CONFORMING
        summary = f"全条文に適合（確認日: {conf_date}）"

    details = [
        f"確認済証交付日: {conf_date}",
        f"チェック条文数: {len(rows)} 件",
        f"  うち 既存不適格（法規）:       {ng_law} 件",
        f"  うち 要確認（性能基準）:       {ng_perf} 件",
        f"  うち 適法:                   {ok} 件",
        f"  うち 対象外（構造等）:         {skip} 件",
    ]
    if ng_no_exemption:
        details.append(f"  ⚠️ 増築・改築で緩和なし（現行適合必要）: {len(ng_no_exemption)} 件")
        for r in ng_no_exemption:
            details.append(f"     - {r['規定名']}（{r['条文']}）")

    caution = None
    if ng_no_exemption:
        caution = (
            "「増築不可（緩和なし）」の条文は増築・改築を行う場合に現行規定への適合が必要です。"
            "大規模修繕・模様替であれば緩和規定（法86条の7）が適用されます。"
            "出典: 国土交通省「既存建築物の現況調査ガイドライン（第3版）」令和7年11月"
        )

    return JudgeResult(
        category="法改正 既存不適格一覧",
        verdict=verdict,
        law_reference="建築基準法 各条文（改正履歴 全件）",
        summary=summary,
        details=details,
        table_rows=rows,
        caution=caution,
        recommendation=(
            "既存不適格条文は現状維持が可能ですが、増改築・用途変更・大規模修繕時に"
            "遡及適用の対象となる場合があります。"
            "住宅医詳細調査（30万円〜）で優先度をつけた改修計画を立案することを推奨します。"
        ),
    )
