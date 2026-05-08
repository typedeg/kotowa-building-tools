"""
New Construction Planning - Building Code Check Tool - Streamlit UI
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from datetime import datetime

from calculator import SiteInput, OwnerInput, calculate
# from planner import generate_plans   # 間取り生成：現在無効
# from draw import render_plan_ascii   # ASCII図面：現在無効
# from report import generate_markdown   # 間取りレポート：現在無効


def build_markdown_anon(site: SiteInput, req: OwnerInput, result, slr=None) -> str:
    """法規チェック結果の Markdown を生成する（間取りなし版）"""
    from datetime import date
    lines = []
    lines.append(f"# 新築計画 法規チェック結果")
    lines.append(f"")
    lines.append(f"- 作成日：{date.today().isoformat()}")
    lines.append(f"- 敷地面積：{site.site_area} ㎡　建蔽率：{site.coverage_ratio}%　容積率：{site.floor_area_ratio}%")
    lines.append(f"- 用途地域：{site.use_district}　防火：{site.fire_zone}　接道方位：{site.road_direction}")
    lines.append(f"- 家族構成：{req.family}　予算：{req.budget}")
    lines.append(f"")

    if result.warnings:
        lines.append("## ⚠️ 注意事項")
        for w in result.warnings:
            lines.append(f"- {w}")
        lines.append("")

    lines.append("## 📋 法規チェック結果")
    lines.append("")
    lines.append("| 項目 | 制限 | 計算値 | 判定 | 備考 | 根拠条文 |")
    lines.append("|------|------|--------|------|------|----------|")
    for c in result.checks:
        verdict = "✅ OK" if c.ok else "❌ NG"
        lines.append(f"| {c.item} | {c.limit} | {c.calc} | {verdict} | {c.note} | {c.law_ref} |")
    lines.append("")

    lines.append("## 📊 建物規模")
    lines.append("")
    lines.append(f"- 推奨建築面積：{result.recommended_building_area:.1f} ㎡")
    lines.append(f"- 必要延床面積：{result.required_floor_area:.1f} ㎡")
    lines.append(f"- 推奨階数：{result.recommended_floors} 階")
    lines.append(f"- 建物寸法：{result.building_width:.1f}m × {result.building_depth:.1f}m")
    lines.append(f"- 最大建築面積（法規）：{result.max_building_area:.1f} ㎡")
    lines.append(f"- 最大延床面積（法規）：{result.max_floor_area:.1f} ㎡")
    lines.append(f"- 実効容積率：{result.actual_far:.0f} %")
    lines.append("")

    if result.ua_standard:
        lines.append("## ♻️ 省エネ基準（R7年4月義務化）")
        lines.append("")
        lines.append(f"- 地域区分：{result.energy_region}地域（{result.energy_region_label}）")
        lines.append(f"- U_A値義務基準：{result.ua_standard} W/(m²·K)")
        if result.ua_zeh:
            lines.append(f"- U_A値 ZEH水準：{result.ua_zeh} W/(m²·K)")
        lines.append("")

    return "\n".join(lines)


def main():
    st.set_page_config(
        page_title="新築計画 法規チェックツール",
        page_icon="📐",
        layout="wide",
    )

    st.title("📐 新築計画 法規チェックツール")
    st.caption("敷地条件・施主要望から建築基準法の適合性を自動チェックします")

    with st.form("madori_form"):
        st.subheader("📐 敷地条件")
        col1, col2, col3 = st.columns(3)
        with col1:
            site_area = st.number_input("敷地面積 (㎡) ★", min_value=10.0, value=112.0, step=1.0)
            coverage_ratio = st.number_input("建蔽率 (%) ★", min_value=10.0, max_value=100.0, value=60.0, step=10.0)
            floor_area_ratio = st.number_input("容積率 (%) ★", min_value=10.0, max_value=1000.0, value=150.0, step=50.0)
        with col2:
            road_direction = st.selectbox("接道方位 ★", ["南", "北", "東", "西"])
            road_width = st.number_input("前面道路幅員 (m)", min_value=1.0, max_value=20.0, value=4.5, step=0.5)
            setback_front = st.number_input("前面セットバック (m)", min_value=0.0, max_value=5.0, value=0.0, step=0.5)
        with col3:
            use_district = st.selectbox("用途地域", [
                "第一種低層住居専用地域", "第二種低層住居専用地域",
                "第一種中高層住居専用地域", "第二種中高層住居専用地域",
                "第一種住居地域", "第二種住居地域", "準住居地域",
                "近隣商業地域", "商業地域", "準工業地域", "工業地域",
            ])
            fire_zone = st.selectbox("防火地域区分", ["なし", "準防火", "防火"])
            height_limit = st.number_input("高さ制限 (m)（0=なし）", min_value=0.0, max_value=30.0, value=0.0, step=0.5)

        col1, col2 = st.columns(2)
        with col1:
            setback_exterior_wall = st.number_input(
                "外壁後退距離制限 (m)（0=なし）【建基法54条・低層住専のみ】",
                min_value=0.0, max_value=3.0, value=0.0, step=0.5
            )
        with col2:
            climate_region = st.number_input(
                "省エネ地域区分（1〜8）",
                min_value=1, max_value=8, value=6, step=1
            )
            st.caption("高松=6、東京=6、仙台=3、札幌=2")

        st.subheader("👨‍👩‍👧‍👦 施主要望（必要延床面積の算出に使用）")
        col1, col2, col3 = st.columns(3)
        with col1:
            family = st.text_input("家族構成", value="夫婦+子2人")
            budget = st.text_input("予算", value="未定")
            ldk_tatami = st.number_input("LDK広さ (畳)", min_value=10.0, max_value=40.0, value=20.0, step=1.0)
        with col2:
            num_rooms = st.number_input("居室数（LDK除く）", min_value=1, max_value=8, value=3, step=1)
            master_tatami = st.number_input("主寝室 (畳)（0=自動8畳）", min_value=0.0, max_value=20.0, value=8.0, step=1.0)
            room_tatami = st.number_input("各居室 (畳)（0=自動6畳）", min_value=0.0, max_value=15.0, value=6.0, step=1.0)
        with col3:
            water_placement = st.selectbox("水回り配置", ["おまかせ", "1F北", "1F南"])
            parking = st.number_input("駐車台数", min_value=0, max_value=5, value=1, step=1)
            col3a, col3b = st.columns(2)
            with col3a:
                has_washitsu = st.checkbox("和室希望")
            with col3b:
                has_pantry = st.checkbox("パントリー希望")

        submitted = st.form_submit_button("⚡ 法規チェックを実行", use_container_width=True, type="primary")

    if not submitted:
        return

    site = SiteInput(
        site_area=site_area,
        coverage_ratio=coverage_ratio,
        floor_area_ratio=floor_area_ratio,
        road_direction=road_direction,
        road_width=road_width,
        fire_zone=fire_zone,
        site_shape="矩形",
        setback_front=setback_front,
        height_limit=height_limit,
        use_district=use_district,
        climate_region=int(climate_region),
        setback_exterior_wall=setback_exterior_wall,
    )

    req = OwnerInput(
        ldk_tatami=ldk_tatami,
        num_rooms=int(num_rooms),
        room_tatami=room_tatami,
        master_tatami=master_tatami,
        water_placement=water_placement,
        parking=int(parking),
        family=family,
        budget=budget,
        has_washitsu=has_washitsu,
        has_pantry=has_pantry,
    )

    with st.spinner("計算中..."):
        try:
            result = calculate(site, req)
        except Exception as e:
            st.error(f"計算エラー: {e}")
            return

    # ── 法規チェック結果 ──────────────────────────────────────────
    st.divider()
    st.subheader("📋 法規チェック結果")

    if result.warnings:
        for w in result.warnings:
            st.info(f"ℹ️ {w}")

    check_rows = []
    for c in result.checks:
        check_rows.append({
            "項目": c.item,
            "制限": c.limit,
            "計算値": c.calc,
            "判定": "✅ OK" if c.ok else "❌ NG",
            "備考": c.note,
            "根拠条文": c.law_ref,
        })

    if check_rows:
        import pandas as pd
        df = pd.DataFrame(check_rows)
        st.dataframe(
            df.style.apply(
                lambda col: ["background-color: #ffecec" if v == "❌ NG" else "" for v in col]
                if col.name == "判定" else [""] * len(col),
                axis=0,
            ),
            use_container_width=True,
            hide_index=True,
        )

    # ── 建物規模サマリー ───────────────────────────────────────────
    st.subheader("📊 建物規模")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("推奨建築面積", f"{result.recommended_building_area:.1f} ㎡")
    col2.metric("必要延床面積", f"{result.required_floor_area:.1f} ㎡")
    col3.metric("推奨階数", f"{result.recommended_floors} 階")
    col4.metric("建物寸法", f"{result.building_width:.1f}m × {result.building_depth:.1f}m")

    col1, col2, col3 = st.columns(3)
    col1.metric("最大建築面積（法規）", f"{result.max_building_area:.1f} ㎡")
    col2.metric("最大延床面積（法規）", f"{result.max_floor_area:.1f} ㎡")
    col3.metric("実効容積率", f"{result.actual_far:.0f} %")

    # ── 省エネ基準 ────────────────────────────────────────────────
    if result.ua_standard:
        with st.expander("♻️ 省エネ基準（R7年4月義務化）"):
            col1, col2, col3 = st.columns(3)
            col1.metric("地域区分", f"{result.energy_region}地域")
            col2.metric("U_A値義務基準", f"{result.ua_standard} W/(m²·K)")
            if result.ua_zeh:
                col3.metric("U_A値 ZEH水準", f"{result.ua_zeh} W/(m²·K)")
            st.caption(result.energy_region_label)

    # ── 間取りパターン（現在無効・コードは保持） ──────────────────
    # st.divider()
    # st.subheader("🏠 間取りパターン（3案）")
    # plans = generate_plans(result, req, site.road_direction)
    # if not plans:
    #     st.warning("間取りパターンを生成できませんでした")
    #     return
    # tabs = st.tabs([f"パターン {p.pattern_id}：{p.pattern_name}" for p in plans])
    # for tab, plan in zip(tabs, plans):
    #     with tab:
    #         col1, col2 = st.columns([3, 2])
    #         with col1:
    #             st.markdown(f"**{plan.description}**")
    #             st.metric("スコア", f"{plan.score} / 100")
    #             try:
    #                 ascii_art = render_plan_ascii(plan)
    #                 st.text(ascii_art)
    #             except Exception as e:
    #                 st.caption(f"ASCII図面生成エラー: {e}")
    #         with col2:
    #             st.markdown("**部屋構成**")
    #             room_rows = []
    #             for floor_num, sections in plan.floor_sections.items():
    #                 for section in sections:
    #                     for room in section.rooms:
    #                         room_rows.append({
    #                             "フロア": f"{floor_num}F",
    #                             "部屋名": room.name,
    #                             "面積": f"{room.area_m2:.1f} ㎡",
    #                         })
    #             if room_rows:
    #                 import pandas as pd
    #                 st.dataframe(pd.DataFrame(room_rows), use_container_width=True, hide_index=True)
    #             if plan.pros:
    #                 st.markdown("**メリット**")
    #                 for note in plan.pros:
    #                     st.markdown(f"- {note}")
    #             if plan.cons:
    #                 st.markdown("**デメリット**")
    #                 for note in plan.cons:
    #                     st.markdown(f"- {note}")

    # ── Markdown ダウンロード ──────────────────────────────────────
    st.divider()
    try:
        slr = None
        try:
            from setback_line import calc_setback_lines
            slr = calc_setback_lines(site, result)
        except Exception:
            pass

        md_content = build_markdown_anon(site, req, result, slr=slr)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_新築法規チェック.md"

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
