"""
Building Code Checker - Streamlit UI
Existing building compliance check tool
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from datetime import datetime

from judges import BuildingData, Verdict, VERDICT_ICONS
from judges import seismic, area, access, renovation, history, energy, foundation, fire, use, habitability
import report


def run_all(data: BuildingData) -> list:
    judges_list = [
        seismic.judge,
        area.judge,
        access.judge,
        renovation.judge,
        renovation.judge_building_classification,
        energy.judge,
        foundation.judge,
        fire.judge,
        use.judge,
        habitability.judge,
        history.judge,
    ]
    results = []
    for fn in judges_list:
        try:
            results.append(fn(data))
        except Exception as e:
            pass
    return results


def verdict_badge(v: Verdict) -> str:
    icons = {
        Verdict.CONFORMING:    "✅ 適法",
        Verdict.NONCONFORMING: "⚠️ 既存不適格",
        Verdict.VIOLATION:     "❌ 違反",
        Verdict.UNKNOWN:       "❓ 判定不能",
    }
    return icons.get(v, str(v))


def build_markdown(data: BuildingData, results: list) -> str:
    """著者情報を除いた Markdown レポートを生成する"""
    import io
    from pathlib import Path
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w", encoding="utf-8") as f:
        tmp_path = Path(f.name)

    md = report.write_markdown(data, results, tmp_path, field_checks=[])
    tmp_path.unlink(missing_ok=True)

    # 著者情報を除去
    md = md.replace("長尾賢（一級建築士 第326774号・住宅医）", "（建築士）")
    md = md.replace("長尾賢", "（建築士）")
    md = md.replace("コトとワ。デザイン", "（事務所名）")
    return md


def main():
    st.set_page_config(
        page_title="建築法規チェックツール",
        page_icon="🏠",
        layout="wide",
    )

    st.title("🏠 建築法規チェックツール（既存不適格判定）")
    st.caption("建築基準法に基づく既存住宅の適合性を自動判定します")

    with st.form("building_form"):
        st.subheader("📋 基本情報")
        col1, col2 = st.columns(2)
        with col1:
            address = st.text_input("所在地 ★", placeholder="例：香川県高松市○○町123番地")
            owner_name = st.text_input("施主名（任意）", placeholder="例：山田 太郎")
        with col2:
            confirmation_date = st.text_input(
                "確認済証交付日 ★",
                placeholder="例：1978-03-15 / 昭和53年3月15日 / S53.3.15"
            )
            structure_type = st.selectbox(
                "構造種別",
                ["", "木造", "鉄骨造", "鉄筋コンクリート造", "鉄骨鉄筋コンクリート造", "その他"],
            )

        st.subheader("📐 面積・規模")
        col1, col2, col3 = st.columns(3)
        with col1:
            stories = st.number_input("階数", min_value=1, max_value=10, value=2, step=1)
            site_area = st.number_input("敷地面積 (㎡) ★", min_value=0.0, value=150.0, step=1.0)
        with col2:
            building_area = st.number_input("建築面積 (㎡) ★", min_value=0.0, value=75.0, step=1.0)
            total_floor_area = st.number_input("延べ床面積 (㎡) ★", min_value=0.0, value=120.0, step=1.0)
        with col3:
            renovation_area = st.number_input("増改築予定面積 (㎡)（なければ0）", min_value=0.0, value=0.0, step=1.0)
            existing_floor_area = st.number_input("既存延べ床面積 (㎡)（増改築時のみ）", min_value=0.0, value=0.0, step=1.0)

        st.subheader("🗺️ 用途地域・制限値")
        col1, col2, col3 = st.columns(3)
        with col1:
            use_district = st.selectbox("用途地域", [
                "", "第一種低層住居専用地域", "第二種低層住居専用地域",
                "第一種中高層住居専用地域", "第二種中高層住居専用地域",
                "第一種住居地域", "第二種住居地域", "準住居地域",
                "近隣商業地域", "商業地域", "準工業地域", "工業地域", "工業専用地域",
                "田園住居地域", "用途地域なし（白地）",
            ])
        with col2:
            bcr_limit = st.number_input("建ぺい率上限 (%) ★", min_value=0.0, max_value=100.0, value=60.0, step=10.0)
        with col3:
            far_limit = st.number_input("容積率上限 (%) ★", min_value=0.0, max_value=1000.0, value=200.0, step=50.0)

        st.subheader("🛣️ 接道")
        col1, col2 = st.columns(2)
        with col1:
            road_width = st.number_input("前面道路幅員 (m) ★", min_value=0.0, value=4.0, step=0.1)
            road_type = st.selectbox("道路種別", [
                "", "42条1項1号道路（公道）", "42条1項2号道路（開発道路）",
                "42条1項3号道路（既存建築基準道路）", "42条1項4号道路（計画道路）",
                "42条1項5号道路（位置指定道路）", "42条2項道路（みなし道路）",
                "43条2項1号（認定）", "43条2項2号（許可）",
            ])
        with col2:
            contact_length = st.number_input("接道長さ (m)", min_value=0.0, value=6.0, step=0.5)

        st.subheader("🔧 増改築・基礎・防火")
        col1, col2, col3 = st.columns(3)
        with col1:
            foundation_type = st.selectbox("基礎形式", [
                "", "ベタ基礎（有筋）", "布基礎（有筋）",
                "無筋コンクリート布基礎", "玉石基礎", "その他",
            ])
        with col2:
            fire_zone = st.selectbox("防火地域区分", [
                "", "指定なし", "法22条区域", "準防火地域", "防火地域",
            ])
        with col3:
            fire_resistance = st.selectbox("耐火性能", [
                "", "耐火建築物", "準耐火建築物（イ準耐）", "準耐火建築物（ロ準耐）", "その他",
            ])

        st.subheader("♻️ 省エネ基準")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            climate_region = st.number_input("地域区分（1〜8）", min_value=1, max_value=8, value=6, step=1)
            st.caption("高松=6、東京=6、仙台=3、札幌=2")
        with col2:
            ua_value = st.number_input("U_A値 W/(m²·K)（0=未入力）", min_value=0.0, value=0.0, step=0.01)
        with col3:
            bei = st.number_input("BEI（0=未入力）", min_value=0.0, value=0.0, step=0.01)
        with col4:
            is_new = st.radio("新築 / 増改築", ["増改築", "新築"])
            is_climate = st.radio("気候風土適応住宅", ["非該当", "該当"])

        st.subheader("💡 居住性能（採光・換気）")
        col1, col2, col3 = st.columns(3)
        with col1:
            has_24h = st.radio("24時間換気設備", ["未確認", "あり", "なし"])
        with col2:
            max_room_area = st.number_input("最大居室面積 (㎡)（0=省略）", min_value=0.0, value=0.0, step=1.0)
        with col3:
            effective_daylight = st.number_input("有効採光面積 (㎡)（0=省略）", min_value=0.0, value=0.0, step=0.1)

        st.subheader("🔄 用途変更")
        planned_use = st.text_input("用途変更計画用途（なければ空欄）", placeholder="例：店舗、事務所")

        submitted = st.form_submit_button("⚡ 判定実行", use_container_width=True, type="primary")

    if not submitted:
        return

    if not address:
        st.error("所在地は必須です")
        return
    if not confirmation_date:
        st.error("確認済証交付日は必須です")
        return

    data = BuildingData(
        address=address or None,
        owner_name=owner_name or None,
        confirmation_date=confirmation_date or None,
        structure_type=structure_type or None,
        stories=int(stories),
        site_area=site_area if site_area > 0 else None,
        building_area=building_area if building_area > 0 else None,
        total_floor_area=total_floor_area if total_floor_area > 0 else None,
        existing_floor_area=existing_floor_area if existing_floor_area > 0 else None,
        renovation_area=renovation_area if renovation_area > 0 else None,
        use_district=use_district or None,
        bcr_limit=bcr_limit if bcr_limit > 0 else None,
        far_limit=far_limit if far_limit > 0 else None,
        road_width=road_width if road_width > 0 else None,
        road_type=road_type or None,
        contact_length=contact_length if contact_length > 0 else None,
        climate_region=int(climate_region),
        ua_value=ua_value if ua_value > 0 else None,
        bei=bei if bei > 0 else None,
        is_new_construction=(is_new == "新築"),
        is_climate_adapted=(is_climate == "該当"),
        foundation_type=foundation_type or None,
        fire_zone=fire_zone or None,
        fire_resistance=fire_resistance or None,
        planned_use=planned_use or None,
        has_24h_ventilation=True if has_24h == "あり" else (False if has_24h == "なし" else None),
        max_room_area=max_room_area if max_room_area > 0 else None,
        effective_daylight_area=effective_daylight if effective_daylight > 0 else None,
    )

    with st.spinner("判定中..."):
        results = run_all(data)

    # ── 総合判定サマリー ──────────────────────────────────────────
    st.divider()
    st.subheader("📊 判定結果")

    ng_list = [r for r in results if r.verdict == Verdict.NONCONFORMING]
    viol_list = [r for r in results if r.verdict == Verdict.VIOLATION]

    if viol_list:
        st.error(f"❌ 違反あり：{len(viol_list)} 件")
    elif ng_list:
        st.warning(f"⚠️ 既存不適格：{len(ng_list)} 件")
    else:
        st.success("✅ 既存不適格なし（判定不能項目を除く）")

    # サマリーテーブル
    summary_rows = []
    for r in results:
        summary_rows.append({
            "判定項目": r.category,
            "結果": verdict_badge(r.verdict),
            "概要": r.summary[:60] + "…" if len(r.summary) > 60 else r.summary,
        })

    import pandas as pd
    df = pd.DataFrame(summary_rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # ── 詳細（expander） ───────────────────────────────────────────
    st.subheader("🔍 詳細判定")
    for r in results:
        icon = VERDICT_ICONS.get(r.verdict, "")
        with st.expander(f"{icon} {r.category}　—　{r.verdict.value}", expanded=(r.verdict != Verdict.CONFORMING)):
            st.markdown(f"**根拠条文：** {r.law_reference}")
            st.markdown(f"**判定概要：** {r.summary}")

            if r.details:
                st.markdown("**詳細：**")
                for d in r.details:
                    st.markdown(f"- {d}")

            if r.caution:
                st.warning(f"⚠️ {r.caution}")

            if r.recommendation:
                st.info(f"💡 {r.recommendation}")

            if r.table_rows:
                try:
                    df_rows = pd.DataFrame(r.table_rows)
                    st.dataframe(df_rows, use_container_width=True, hide_index=True)
                except Exception:
                    pass

    # ── Markdown ダウンロード ──────────────────────────────────────
    st.divider()
    try:
        md_content = build_markdown(data, results)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        addr_safe = (address or "物件").replace("/", "-").replace(" ", "_")[:15]
        filename = f"{timestamp}_{addr_safe}_既存不適格判定.md"

        st.download_button(
            label="📥 Markdownレポートをダウンロード",
            data=md_content.encode("utf-8"),
            file_name=filename,
            mime="text/markdown",
            use_container_width=True,
        )
    except Exception as e:
        st.error(f"レポート生成エラー: {e}")


if __name__ == "__main__":
    main()
