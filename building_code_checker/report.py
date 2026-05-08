"""
レポート生成モジュール（Markdown + PDF）

カラーパレット（コトとワ。デザイン統一ルール）:
  sumi  #1C1C1C  本文
  ai    #1B4F72  見出し・強調
  kin   #7D6608  アクセントライン
  washi #F4F1EB  ボックス背景
"""
from __future__ import annotations
from pathlib import Path
from datetime import date
from typing import TYPE_CHECKING

from judges import Verdict, VERDICT_ICONS

if TYPE_CHECKING:
    from judges import BuildingData, JudgeResult

_ICONS = VERDICT_ICONS  # 後方互換エイリアス

# PDFのCSS（コトとワ。デザイン カラーパレット適用）
_CSS = """
@font-face {
  font-family: 'JaFont';
  src: local('Hiragino Sans'),
       local('ヒラギノ角ゴシック'),
       local('Yu Gothic'),
       local('メイリオ');
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'JaFont', 'Hiragino Sans', 'Yu Gothic', 'Meiryo', sans-serif;
  font-size: 10pt;
  line-height: 1.75;
  color: #1C1C1C;
}
@page {
  size: A4 portrait;
  margin: 22mm 18mm 22mm 18mm;
  @bottom-center {
    content: counter(page) " / " counter(pages);
    font-size: 8pt;
    color: #7D6608;
  }
}
h1 {
  font-size: 16pt;
  color: #1B4F72;
  border-bottom: 3px solid #7D6608;
  padding-bottom: 6px;
  margin-bottom: 16px;
}
h2 {
  font-size: 12pt;
  color: #1B4F72;
  border-left: 5px solid #1B4F72;
  padding-left: 10px;
  margin: 20px 0 10px 0;
}
h3 {
  font-size: 10.5pt;
  color: #1C1C1C;
  margin: 14px 0 6px 0;
}
p { margin: 6px 0; }
ul { margin: 6px 0 6px 18px; }
li { margin: 2px 0; }
table {
  border-collapse: collapse;
  width: 100%;
  margin: 10px 0;
  font-size: 9.5pt;
}
th {
  background-color: #1B4F72;
  color: #FFFFFF;
  padding: 6px 10px;
  text-align: left;
}
td {
  border: 1px solid #CCC;
  padding: 5px 10px;
}
tr:nth-child(even) td { background-color: #F4F1EB; }
.badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 3px;
  font-weight: bold;
  font-size: 9pt;
}
.badge-conform  { background: #1E8449; color: #FFF; }
.badge-ng       { background: #D35400; color: #FFF; }
.badge-violation{ background: #C0392B; color: #FFF; }
.badge-unknown  { background: #7F8C8D; color: #FFF; }
.caution-box {
  background: #FFF3CD;
  border-left: 4px solid #D35400;
  padding: 8px 12px;
  margin: 10px 0;
  font-size: 9.5pt;
}
.recommend-box {
  background: #F4F1EB;
  border-left: 4px solid #7D6608;
  padding: 8px 12px;
  margin: 10px 0;
  font-size: 9.5pt;
}
.footer-note {
  font-size: 8pt;
  color: #888;
  margin-top: 20px;
  border-top: 1px solid #DDD;
  padding-top: 8px;
}
hr { border: none; border-top: 1px solid #DDD; margin: 16px 0; }
"""


# ─────────────────────────────────────────────────────────────────
# Markdown レポート生成
# ─────────────────────────────────────────────────────────────────

def write_markdown(
    data: "BuildingData",
    results: list["JudgeResult"],
    output_path: Path,
    field_checks: list = None,
) -> str:
    """Markdownレポートを生成してファイルに保存し、内容を返す"""
    content = _build_markdown(data, results, field_checks or [])
    output_path.write_text(content, encoding="utf-8")
    return content


def _build_markdown(
    data: "BuildingData",
    results: list["JudgeResult"],
    field_checks: list = None,
) -> str:
    today = date.today().strftime("%Y年%m月%d日")
    address = data.address or "未入力"
    owner = data.owner_name or "未入力"

    non_conforming = [r for r in results if r.verdict == Verdict.NONCONFORMING]
    unknown = [r for r in results if r.verdict == Verdict.UNKNOWN]

    overall_icon = "⚠️ 既存不適格あり" if non_conforming else (
        "❓ 判定不能項目あり" if unknown else "✅ 法規上の問題なし"
    )

    lines = [
        "# 建築法規チェックレポート（既存不適格判定）",
        "",
        f"| 項目 | 内容 |",
        f"|------|------|",
        f"| 作成日 | {today} |",
        f"| 作成者 | 長尾賢（一級建築士 第326774号・住宅医） |",
        f"| 対象物件 | {address} |",
        f"| 施主名 | {owner} |",
        "",
        "---",
        "",
        "## 総合判定",
        "",
        f"### {overall_icon}",
        "",
    ]

    if non_conforming:
        lines.append("**既存不適格項目：**")
        for r in non_conforming:
            lines.append(f"- {r.category}：{r.summary}")
        lines.append("")

    # 判定サマリー表
    lines += [
        "| 判定項目 | 結果 | 概要 |",
        "|---------|------|------|",
    ]
    for r in results:
        icon = _ICONS.get(r.verdict.value, "")
        short = r.summary[:45] + "…" if len(r.summary) > 45 else r.summary
        lines.append(f"| {r.category} | {icon} {r.verdict.value} | {short} |")
    lines += ["", "---", ""]

    # 物件概要
    lines += [
        "## 物件概要",
        "",
        "| 項目 | 内容 |",
        "|------|------|",
        f"| 所在地 | {address} |",
        f"| 施主名 | {owner} |",
        f"| 構造・規模 | {data.structure_type or '-'} {data.stories or '-'}階建 |",
        f"| 確認済証交付日 | {data.confirmation_date or '不明'} |",
        f"| 敷地面積 | {_fmt(data.site_area)} m² |",
        f"| 建築面積 | {_fmt(data.building_area)} m² |",
        f"| 延べ床面積 | {_fmt(data.total_floor_area)} m² |",
        f"| 用途地域 | {data.use_district or '-'} |",
        f"| 建ぺい率制限 | {_fmt(data.bcr_limit)} % |",
        f"| 容積率制限 | {_fmt(data.far_limit)} % |",
        f"| 前面道路幅員 | {_fmt(data.road_width)} m |",
        f"| 接道長さ | {_fmt(data.contact_length)} m |",
        f"| 増改築予定面積 | {_fmt(data.renovation_area)} m² |",
        "",
        "---",
        "",
    ]

    # 各判定詳細
    lines.append("## 詳細判定")
    lines.append("")

    for i, r in enumerate(results, 1):
        icon = _ICONS.get(r.verdict.value, "")
        lines += [
            f"### {i}. {r.category}　{icon} {r.verdict.value}",
            "",
            f"**根拠条文：** {r.law_reference}",
            "",
            f"{r.summary}",
            "",
        ]

        if r.details:
            for d in r.details:
                lines.append(f"- {d}")
            lines.append("")

        if r.table_rows:
            lines += _format_history_table(r.table_rows)
            lines.append("")

        if r.numeric:
            num_lines = _format_numeric(r.category, r.numeric)
            if num_lines:
                lines += num_lines
                lines.append("")

        if r.caution:
            lines += [
                "> **⚠️ 注意事項（施主向け）**",
                f"> {r.caution}",
                "",
            ]

        if r.recommendation:
            lines += [
                "> **💡 実務アドバイス（長尾賢）**",
                f"> {r.recommendation}",
                "",
            ]

        lines += ["---", ""]

    # 現況確認結果
    if field_checks:
        lines += _build_field_check_section(field_checks)

    # 根拠条文一覧
    lines += [
        "## 根拠条文一覧",
        "",
        "| 条文 | 内容 |",
        "|------|------|",
        "| 建築基準法 第20条 | 構造耐力（耐震基準） |",
        "| 建築基準法 第42条 | 道路の定義（42条2項道路・みなし道路） |",
        "| 建築基準法 第43条 | 敷地等と道路の関係（接道義務） |",
        "| 建築基準法 第52条 | 容積率 |",
        "| 建築基準法 第53条 | 建ぺい率 |",
        "| 建築基準法 第86条の7 | 既存不適格建築物の増改築制限 |",
        "| 建築基準法施行令 第137条の2 | 構造耐力関係の遡及適用範囲 |",
        "| 建築基準法施行令 第137条の14 | 増改築部分の割合計算 |",
        "| 昭55建告第1792号 | 旧耐震基準（昭和55年） |",
        "| 平12建告第1460号 | 木造2000年基準（平成12年） |",
        "| 耐震改修促進法 | 既存不適格建築物の耐震改修に関する法律 |",
        "",
        "---",
        "",
        "*本レポートは建築法規チェックツール（コトとワ。デザイン）により自動生成されました。*  ",
        "*最終的な法的判断は特定行政庁または指定確認検査機関へご確認ください。*",
    ]

    return "\n".join(lines)


def _aggregate_field_checks(items: list) -> dict:
    """現況確認リストを verified/compliant/still_ng/unverified に分類する"""
    verified   = [i for i in items if i.verified]
    compliant  = [i for i in verified if i.compliant]
    still_ng   = [i for i in verified if not i.compliant]
    unverified = [i for i in items if not i.verified]
    return {"verified": verified, "compliant": compliant, "still_ng": still_ng, "unverified": unverified}


def _build_compliance_table(title: str, items: list, with_note: bool = True) -> list:
    """現況確認テーブルブロックを生成（compliant / still_ng 共通）"""
    if with_note:
        header = ["| # | 区分 | 規定名 | 条文 | 確認メモ |", "|---|------|--------|------|---------|"]
        rows   = [f"| {i.item_id} | {i.category} | {i.name} | {i.article} | {i.note or '-'} |" for i in items]
    else:
        header = ["| # | 区分 | 規定名 | 条文 |", "|---|------|--------|------|"]
        rows   = [f"| {i.item_id} | {i.category} | {i.name} | {i.article} |" for i in items]
    return [title, "", *header, *rows, ""]


def _build_field_check_section(field_checks: list) -> list:
    """現況確認結果セクションを生成"""
    if not field_checks:
        return []

    agg = _aggregate_field_checks(field_checks)
    compliant  = agg["compliant"]
    still_ng   = agg["still_ng"]
    unverified = agg["unverified"]

    lines = [
        "## 現況確認結果",
        "",
        f"| 区分 | 件数 |",
        f"|------|------|",
        f"| 既存不適格 総数 | {len(field_checks)} 件 |",
        f"| 確認済（現況適法） | {len(compliant)} 件 |",
        f"| 確認済（現況でも不適格） | {len(still_ng)} 件 |",
        f"| 未確認 | {len(unverified)} 件 |",
        "",
    ]

    if compliant:
        lines += _build_compliance_table("### ✅ 現況確認により適法と確認された項目", compliant)
    if still_ng:
        lines += _build_compliance_table("### ⚠️ 確認済・現況でも不適格の項目", still_ng)
    if unverified:
        lines += _build_compliance_table("### ❓ 未確認の項目（現況確認を推奨）", unverified, with_note=False)

    lines += ["---", ""]
    return lines


def _format_history_table(rows: list) -> list:
    """法改正 既存不適格一覧テーブルをMarkdown形式で生成"""
    lines = [
        "#### 建築基準法 改正履歴 既存不適格チェック一覧",
        "",
        "※ 出典: 国土交通省「既存建築物の現況調査ガイドライン（第3版）」令和7年11月",
        "",
        "| # | 施行日 | 区分 | 種別 | 規定名 | 判定 | 増築緩和 |",
        "|---|--------|------|------|--------|------|---------|",
    ]
    for i, row in enumerate(rows, 1):
        lines.append(
            f"| {i} | {row['施行日']} | {row['カテゴリ']} | {row['種別']} "
            f"| {row['規定名']} | {row['判定']} | {row['増築緩和']} |"
        )
    lines.append("")

    # 既存不適格・要確認のみ詳細を展開
    ng_rows = [r for r in rows if "⚠️" in r["判定"]]
    if ng_rows:
        lines += ["#### 既存不適格・要確認 詳細", ""]
        for row in ng_rows:
            lines += [
                f"**{row['規定名']}**（{row['施行日']} 施行 / {row['条文']}）",
                "",
                f"- **判定：** {row['判定']}",
                f"- **理由：** {row['理由']}",
                f"- **推奨対応：** {row['推奨対応']}",
                "",
            ]
    return lines


def _fmt(val) -> str:
    if val is None:
        return "-"
    return str(val)


def _format_numeric(category: str, numeric: dict) -> list:
    """数値データを判定カテゴリに応じて表形式で整形"""
    if category == "建ぺい率・容積率":
        return [
            "| 指標 | 現況値 | 制限値 | 余裕 |",
            "|------|--------|--------|------|",
            f"| 建ぺい率 | {numeric.get('current_bcr', '-')}% "
            f"| {numeric.get('bcr_limit', '-')}% "
            f"| {numeric.get('bcr_margin', '-')}% |",
            f"| 容積率 | {numeric.get('current_far', '-')}% "
            f"| {numeric.get('far_limit', '-')}% "
            f"| {numeric.get('far_margin', '-')}% |",
        ]
    if category == "増改築可否" and "ratio_pct" in numeric:
        return [
            f"**増改築面積比率：** {numeric['ratio_pct']}%"
            f"（閾値 {numeric['threshold_pct']}%）",
        ]
    if category == "省エネ基準適合義務":
        rows = [
            "| 指標 | 基準値 | 実測値 |",
            "|------|--------|--------|",
        ]
        rows.append(
            f"| 地域区分 | — | {numeric.get('地域区分', '-')} |"
        )
        if "U_A値基準" in numeric:
            rows.append(
                f"| U_A値 [W/(m²·K)] | {numeric.get('U_A値基準', '-')} | "
                f"{numeric.get('U_A値（入力）', '未測定')} |"
            )
        if "BEI義務基準" in numeric:
            rows.append(
                f"| BEI | ≦{numeric.get('BEI義務基準', '-')} | "
                f"{numeric.get('BEI（入力）', '未測定')} |"
            )
        return rows
    return []


# ─────────────────────────────────────────────────────────────────
# PDF レポート生成
# ─────────────────────────────────────────────────────────────────

def write_pdf(
    data: "BuildingData",
    results: list["JudgeResult"],
    output_path: Path,
    field_checks: list = None,
    md_content: str = None,
) -> bool:
    """Markdown → HTML → PDF に変換して保存。md_content を渡すと _build_markdown の再実行を省略できる"""
    try:
        import markdown as md_lib
        from weasyprint import HTML, CSS

        if md_content is None:
            md_content = _build_markdown(data, results, field_checks or [])
        html_body = md_lib.markdown(
            md_content,
            extensions=["tables", "nl2br", "fenced_code"],
        )

        full_html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <title>建築法規チェックレポート</title>
</head>
<body>
{html_body}
</body>
</html>"""

        HTML(string=full_html).write_pdf(
            str(output_path),
            stylesheets=[CSS(string=_CSS)],
        )
        return True

    except ImportError as e:
        print(f"  PDF生成スキップ（ライブラリ不足: {e}）。`pip install weasyprint markdown` で導入できます。")
        return False
    except Exception as e:
        print(f"  PDF生成エラー: {e}")
        return False
