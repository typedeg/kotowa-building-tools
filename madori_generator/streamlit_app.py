"""
新築計画 法規チェックツール - Streamlit UI
外部実務者検証用（著者情報なし）
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

    ng_items = [c for c in result.checks if not c.ok and c.suggestion]
    if ng_items:
        lines.append("## ⚠️ NG項目の改善提案")
        lines.append("")
        for c in ng_items:
            lines.append(f"### {c.item}")
            lines.append("")
            for line in c.suggestion.split('\n'):
                lines.append(line)
            lines.append("")

    lines.append("## 📊 法規上限（敷地面積・建蔽率・容積率からの最大値）")
    lines.append("")
    lines.append(f"- 敷地面積：{site.site_area:.1f} ㎡")
    lines.append(f"- 最大建築面積：{result.max_building_area:.1f} ㎡"
                 f"（建蔽率 {result.effective_coverage_ratio:.0f}%・緩和込・建基法53条）")
    lines.append(f"- 最大延床面積：{result.max_floor_area:.1f} ㎡"
                 f"（実効容積率 {result.actual_far:.0f}%・建基法52条）")
    lines.append(f"- 道路幅員による容積率上限：{result.far_by_road:.0f} %"
                 f"（{site.road_width}m × {result.far_coeff}/10・建基法52条2項）")
    lines.append("")

    if result.ua_standard:
        lines.append("## ♻️ 省エネ基準（R7年4月義務化）")
        lines.append("")
        lines.append(f"- 地域区分：{result.energy_region}地域（{result.energy_region_label}）")
        lines.append(f"- U_A値義務基準：{result.ua_standard} W/(m²·K)")
        if result.ua_zeh:
            lines.append(f"- U_A値 ZEH水準：{result.ua_zeh} W/(m²·K)")
        lines.append("")

    lines += [
        "## 🔗 参照リンク（法規条件の確認用）",
        "",
        "本結果の用途地域・建蔽率・容積率等はGISデータ・入力値に基づく参考値です。",
        "確認申請前に必ず以下の公開情報および自治体窓口でご確認ください"
        "（高松市: 都市計画課 087-839-2455）。",
        "",
        "- たかまっぷ（高松市地図ポータル）用途地域等: "
        "https://takamatsu.geocloud.jp/webgis/?z=19&ll=34.342778%2C134.046667&t=DM&mp=90&op=70&vlf=90-84-00000ffffffe",
        "- たかまっぷ（高松市地図ポータル）道路種別等: "
        "https://takamatsu.geocloud.jp/webgis/?z=19&ll=34.319565%2C134.005478&t=roadmap&mp=100&op=70&vlf=-1",
        "- 国土交通省 不動産情報ライブラリ（用途地域・防火地域GISデータ出典）: "
        "https://www.reinfolib.mlit.go.jp/",
        "",
        "> 建築基準法上の道路種別は自動取得できないため、上記「道路種別等」の地図および",
        "> 高松市建築指導課での窓口確認が必要です。",
        "",
    ]

    return "\n".join(lines)


def _calc_slr(site: SiteInput, result):
    """setback_line.calc_setback_lines を正しい引数で呼び出すヘルパー"""
    from setback_line import calc_setback_lines
    return calc_setback_lines(
        use_district=site.use_district,
        road_direction=site.road_direction,
        road_width=site.road_width,
        site_area=site.site_area,
        building_width=result.building_width,
        building_depth=result.building_depth,
        setback_front=site.setback_front,
        height_limit=site.height_limit,
    )


def render_setback_charts(site: SiteInput, result) -> None:
    """道路斜線・北側斜線の断面図を描画"""
    import matplotlib
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches

    matplotlib.rcParams['font.family'] = 'DejaVu Sans'

    try:
        slr = _calc_slr(site, result)
    except Exception as e:
        st.caption(f"Setback calc error: {e}")
        return

    est_bldg_h = result.recommended_floors * 3.0
    est_site_depth = site.site_area / max(result.building_width, 1.0)
    n_cols = 2 if slr.north_applicable else 1
    cols = st.columns(n_cols)

    # ── 道路斜線断面図 ──────────────────────────────────────────
    fig1, ax1 = plt.subplots(figsize=(7, 5))

    ax1.axvspan(0, site.road_width, alpha=0.15, color='gray')
    ax1.text(site.road_width / 2, 0.3, 'Road', ha='center', va='bottom', fontsize=9, color='gray')
    ax1.axvline(x=site.road_width, color='black', linestyle='--', linewidth=1.2)
    ax1.text(site.road_width + 0.15, 0.3, 'Boundary', fontsize=8, color='black')

    xs = [p.dist_m for p in slr.road_points]
    ys = [p.height_m for p in slr.road_points]
    ax1.plot(xs, ys, color='#c0392b', linewidth=2.0, label=f'Road setback 1:{slr.road_slope:.2f}')

    bx = site.road_width + site.setback_front
    rect1 = patches.Rectangle(
        (bx, 0), result.building_depth, est_bldg_h,
        linewidth=1.5, edgecolor='#2980b9', facecolor='#aed6f1', alpha=0.6,
        label=f'Building {result.recommended_floors}F (~{est_bldg_h:.0f}m)'
    )
    ax1.add_patch(rect1)

    if slr.abs_height_limit > 0:
        ax1.axhline(y=slr.abs_height_limit, color='#e67e22', linestyle='-.', linewidth=1.5,
                    label=f'Max H {slr.abs_height_limit:.0f}m')

    D_front = bx
    ax1.annotate(
        f'Front {slr.effective_max_height_front:.1f}m',
        xy=(D_front, slr.effective_max_height_front),
        xytext=(D_front + 1.5, slr.effective_max_height_front + 0.8),
        fontsize=8, color='#c0392b',
        arrowprops=dict(arrowstyle='->', color='#c0392b', lw=1.0),
    )
    D_rear = bx + result.building_depth
    if slr.effective_max_height_rear < 9999:
        ax1.annotate(
            f'Rear {slr.effective_max_height_rear:.1f}m',
            xy=(D_rear, slr.effective_max_height_rear),
            xytext=(D_rear + 1.0, slr.effective_max_height_rear + 0.8),
            fontsize=8, color='#c0392b',
            arrowprops=dict(arrowstyle='->', color='#c0392b', lw=1.0),
        )

    ax1.set_xlabel('Horizontal dist. from road opp. boundary D (m)')
    ax1.set_ylabel('Height H (m)')
    ax1.legend(loc='upper left', fontsize=8)
    ax1.set_xlim(left=0, right=max(xs[-1] if xs else 25, D_rear + 3))
    ax1.set_ylim(bottom=0)
    ax1.grid(True, alpha=0.25, linestyle=':')
    plt.tight_layout()
    with cols[0]:
        st.pyplot(fig1)
    plt.close(fig1)

    # ── 北側斜線断面図（適用地域のみ） ────────────────────────────
    if slr.north_applicable:
        fig2, ax2 = plt.subplots(figsize=(7, 5))

        xs2 = [p.dist_m for p in slr.north_points]
        ys2 = [p.height_m for p in slr.north_points]
        ax2.plot(xs2, ys2, color='#27ae60', linewidth=2.0,
                 label=f'North setback base={slr.north_base_h:.0f}m slope=1:1.25')

        ax2.axvline(x=0, color='black', linestyle='--', linewidth=1.2)
        ax2.text(0.15, 0.3, 'N.Boundary', fontsize=8, color='black')

        x_rear_from_north = max(0.0, est_site_depth - site.setback_front - result.building_depth)
        rect2 = patches.Rectangle(
            (x_rear_from_north, 0), result.building_depth, est_bldg_h,
            linewidth=1.5, edgecolor='#2980b9', facecolor='#aed6f1', alpha=0.6,
            label=f'Building {result.recommended_floors}F (~{est_bldg_h:.0f}m)'
        )
        ax2.add_patch(rect2)

        if slr.abs_height_limit > 0:
            ax2.axhline(y=slr.abs_height_limit, color='#e67e22', linestyle='-.', linewidth=1.5,
                        label=f'Max H {slr.abs_height_limit:.0f}m')

        ax2.set_xlabel('Horizontal dist. from north boundary x (m) [southward]')
        ax2.set_ylabel('Height H (m)')
        ax2.legend(loc='upper left', fontsize=8)
        ax2.set_xlim(left=0)
        ax2.set_ylim(bottom=0)
        ax2.grid(True, alpha=0.25, linestyle=':')
        plt.tight_layout()
        with cols[1]:
            st.pyplot(fig2)
        plt.close(fig2)

    # 根拠条文・算定式の詳細
    if slr.notes:
        with st.expander('📖 斜線制限の根拠条文・算定式', expanded=False):
            for note in slr.notes:
                st.text(note)
    for w in slr.warnings:
        st.caption(f'⚠️ {w}')


def main():
    st.set_page_config(
        page_title="新築計画 法規チェックツール",
        page_icon="📐",
        layout="wide",
    )

    st.title("📐 新築計画 法規チェックツール")
    st.caption("敷地条件・施主要望から建築基準法の適合性を自動チェックします")

    # フォーム初期値（住所自動取得・用途地域選択で上書きされる）
    _defaults = {
        "coverage_ratio": 60.0,
        "floor_area_ratio": 150.0,
        "use_district": "第一種低層住居専用地域",
        "fire_zone": "なし",
        "height_limit": 10.0,   # デフォルト用途地域＝一低のため建基法55条の10m
        "climate_region": 6,
    }
    for _k, _v in _defaults.items():
        st.session_state.setdefault(_k, _v)

    _DISTRICTS = [
        "第一種低層住居専用地域", "第二種低層住居専用地域",
        "第一種中高層住居専用地域", "第二種中高層住居専用地域",
        "第一種住居地域", "第二種住居地域", "田園住居地域", "準住居地域",
        "近隣商業地域", "商業地域", "準工業地域", "工業地域", "工業専用地域",
    ]
    # 建基法55条1項：絶対高さ制限（10m又は12m・都市計画で指定）の対象地域
    _LOW_RISE = ("第一種低層住居専用地域", "第二種低層住居専用地域", "田園住居地域")
    _TAKAMAP_YOUTO = ("https://takamatsu.geocloud.jp/webgis/"
                      "?z=19&ll=34.342778%2C134.046667&t=DM&mp=90&op=70&vlf=90-84-00000ffffffe")
    _TAKAMAP_ROAD = ("https://takamatsu.geocloud.jp/webgis/"
                     "?z=19&ll=34.319565%2C134.005478&t=roadmap&mp=100&op=70&vlf=-1")

    def _default_height(district: str) -> float:
        return 10.0 if district in _LOW_RISE else 0.0

    def _on_district_change():
        st.session_state["height_limit"] = _default_height(st.session_state["use_district"])

    # ── 住所から法規条件を自動取得（任意） ─────────────────────────
    with st.expander("📍 住所から用途地域・建蔽率・容積率・防火指定を自動取得（任意）"):
        st.caption(
            "国土地理院ジオコーディング＋国交省 不動産情報ライブラリAPI（XKT002/XKT014）を使用。"
            "取得値はGISデータによる参考値です。確認申請前に必ず自治体で確認してください。"
        )
        addr_col1, addr_col2 = st.columns([3, 1])
        address = addr_col1.text_input(
            "敷地住所", placeholder="例: 香川県高松市番町一丁目8-15", key="lookup_address")
        if addr_col2.button("自動取得", use_container_width=True):
            try:
                if "LIBRARY_API_KEY" in st.secrets:
                    os.environ["LIBRARY_API_KEY"] = st.secrets["LIBRARY_API_KEY"]
            except Exception:
                pass
            try:
                from zoning_lookup import lookup
                with st.spinner("取得中..."):
                    z = lookup(address)
                st.success(f"位置特定: {z.matched_address}")
                if z.use_district in _DISTRICTS:
                    st.session_state["use_district"] = z.use_district
                    st.session_state["height_limit"] = _default_height(z.use_district)
                elif z.use_district:
                    st.warning(f"用途地域「{z.use_district}」は選択肢にないため手動選択してください")
                if z.coverage_ratio is not None:
                    st.session_state["coverage_ratio"] = float(z.coverage_ratio)
                if z.floor_area_ratio is not None:
                    st.session_state["floor_area_ratio"] = float(z.floor_area_ratio)
                if z.fire_zone is not None:
                    st.session_state["fire_zone"] = z.fire_zone

                # 省エネ地域区分の自動反映（市区町村名→地域区分テーブル）
                _region_msg = ""
                try:
                    _bcc = os.path.join(
                        os.path.dirname(os.path.abspath(__file__)),
                        "..", "building_code_checker")
                    if _bcc not in sys.path:
                        sys.path.insert(0, _bcc)
                    from judges.energy_standards import CITY_CLIMATE_REGION
                    import re as _re
                    _m = _re.search(r'(?:都|道|府|県)(.{1,8}?[市町村])', z.matched_address)
                    _city = _m.group(1) if _m else None
                    if _city and _city in CITY_CLIMATE_REGION:
                        st.session_state["climate_region"] = CITY_CLIMATE_REGION[_city]
                        _region_msg = f"省エネ地域区分: {CITY_CLIMATE_REGION[_city]}地域（{_city}）"
                    else:
                        st.warning(
                            f"省エネ地域区分テーブルに「{_city or '市区町村名'}」が未登録のため"
                            "自動設定をスキップしました。国交省告示の地域区分一覧で確認してください"
                        )
                except Exception as _e:
                    st.warning(f"省エネ地域区分の自動取得をスキップ: {_e}")

                st.info(
                    f"用途地域: {z.use_district or '取得不可'} / "
                    f"建蔽率: {z.coverage_ratio or '—'}% / "
                    f"容積率: {z.floor_area_ratio or '—'}% / "
                    f"防火指定: {z.fire_zone or '—'}"
                    + (f" / {_region_msg}" if _region_msg else "")
                    + " → 下のフォームに反映しました"
                )
                for w in z.warnings:
                    st.warning(w)
            except Exception as e:
                st.error(f"自動取得に失敗しました（手入力で続行してください）: {e}")

    # ── 用途地域（選択即時に法定高さ・通知を反映するためフォーム外） ──
    st.subheader("🗺 用途地域")
    use_district = st.selectbox(
        "用途地域", _DISTRICTS, key="use_district", on_change=_on_district_change)
    if use_district in _LOW_RISE:
        st.info(
            "建基法55条1項：この用途地域の建築物の高さは **10m又は12m**"
            "（どちらかは都市計画で指定）以下です。基本値 **10m** を高さ制限欄に設定しました。"
            "10m/12mの別・高度地区の有無は必ず自治体（高松市: 都市計画課 087-839-2455）で確認してください。"
        )
    else:
        st.info(
            "この用途地域に建基法55条の絶対高さ制限はありません（斜線制限・日影規制・"
            "高度地区等が適用）。高度地区等の指定は必ず自治体で確認してください。"
        )
    st.caption(
        f"🔗 高松市内の用途地域の確認: [たかまっぷ（用途地域等）]({_TAKAMAP_YOUTO})"
    )

    with st.form("madori_form"):
        st.subheader("📐 敷地条件")
        col1, col2, col3 = st.columns(3)
        with col1:
            site_area = st.number_input("敷地面積 (㎡) ★", min_value=10.0, value=112.0, step=1.0)
            coverage_ratio = st.number_input("建蔽率 (%) ★", min_value=10.0, max_value=100.0, step=10.0, key="coverage_ratio")
            floor_area_ratio = st.number_input("容積率 (%) ★", min_value=10.0, max_value=1000.0, step=50.0, key="floor_area_ratio")
        with col2:
            road_direction = st.selectbox("接道方位 ★", ["南", "北", "東", "西"])
            road_width = st.number_input("前面道路幅員 (m)", min_value=1.0, max_value=20.0, value=4.5, step=0.5)
            st.caption(f"🔗 [たかまっぷ（道路種別等）]({_TAKAMAP_ROAD})｜建基法上の道路種別は地図と建築指導課で要確認")
            setback_front = st.number_input("前面セットバック (m)", min_value=0.0, max_value=5.0, value=0.0, step=0.5)
        with col3:
            fire_zone = st.selectbox(
                "防火地域区分", ["なし", "法22条地域", "準防火", "防火"], key="fire_zone")
            height_limit = st.number_input(
                "高さ制限 (m)（0=なし）", min_value=0.0, max_value=30.0, step=0.5,
                key="height_limit",
                help="用途地域の選択で法定の基本値が自動設定されます（建基法55条）。"
                     "都市計画で12m指定の場合や高度地区がある場合は修正してください。")
            setback_exterior_wall = st.number_input(
                "外壁後退距離制限 (m)（0=なし）【建基法54条・低層住専のみ】",
                min_value=0.0, max_value=3.0, value=0.0, step=0.5
            )

        st.markdown("**建蔽率の緩和（建基法53条3項）** — 該当する場合にチェック")
        col1, col2, col3 = st.columns(3)
        with col1:
            corner_lot = st.checkbox(
                "角地緩和 +10%（53条3項2号）",
                help="特定行政庁が指定する角地等。指定の有無は自治体で要確認")
        with col2:
            fireproof_building = st.checkbox(
                "耐火建築物等とする +10%（53条3項1号）",
                help="防火地域内の耐火建築物等／準防火地域内の耐火・準耐火建築物等が対象。"
                     "建蔽率80%地域×防火地域×耐火は適用除外＝100%（53条6項1号）")
        with col3:
            climate_region = st.number_input(
                "省エネ地域区分（1〜8）",
                min_value=1, max_value=8, step=1, key="climate_region",
                help="住所自動取得で自動設定されます（高松=6、東京=6、仙台=3、札幌=2）")

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
        corner_lot=corner_lot,
        fireproof_building=fireproof_building,
    )

    # 施主要望入力は廃止（法規チェック特化）。内部計算用にデフォルト値を使用
    req = OwnerInput()

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
        # 施主要望入力の廃止に伴い、建蔽率・容積率は「最大面積の提示」に置き換える
        if c.item == '建蔽率':
            check_rows.append({
                "項目": "建蔽率 → 最大建築面積",
                "制限": c.limit,
                "計算値": f"{site.site_area:.1f}㎡ × {result.effective_coverage_ratio:.0f}% = "
                          f"最大 {result.max_building_area:.1f}㎡",
                "判定": "📐 上限",
                "備考": c.note,
                "根拠条文": "建基法53条",
            })
            continue
        if c.item == '容積率':
            check_rows.append({
                "項目": "容積率 → 最大延床面積",
                "制限": f"{result.actual_far:.0f}%（指定{site.floor_area_ratio:.0f}% / "
                        f"道路幅員{result.far_by_road:.0f}% の小さい方）",
                "計算値": f"{site.site_area:.1f}㎡ × {result.actual_far:.0f}% = "
                          f"最大 {result.max_floor_area:.1f}㎡",
                "判定": "📐 上限",
                "備考": f"道路幅員容積率 = {site.road_width}m × {result.far_coeff}/10 = "
                        f"{result.far_by_road:.0f}%",
                "根拠条文": "建基法52条1項・2項",
            })
            continue
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

    # ── NG項目の改善提案 ──────────────────────────────────────────────
    # 建蔽率・容積率は最大面積提示に置換済みのため改善提案の対象外
    ng_items = [c for c in result.checks
                if not c.ok and c.suggestion and c.item not in ('建蔽率', '容積率')]
    if ng_items:
        with st.expander(f"⚠️ NG項目の改善提案（{len(ng_items)}件）", expanded=True):
            for c in ng_items:
                st.markdown(f"**{c.item}**")
                for line in c.suggestion.split('\n'):
                    st.markdown(line)
                st.divider()

    # ── 法規上限サマリー ───────────────────────────────────────────
    st.subheader("📊 法規上限（敷地面積・建蔽率・容積率からの最大値）")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("敷地面積", f"{site.site_area:.1f} ㎡")
    col2.metric("最大建築面積", f"{result.max_building_area:.1f} ㎡",
                delta=f"建蔽率 {result.effective_coverage_ratio:.0f}%（緩和込）",
                delta_color="off")
    col3.metric("最大延床面積", f"{result.max_floor_area:.1f} ㎡",
                delta=f"実効容積率 {result.actual_far:.0f}%", delta_color="off")
    col4.metric("道路幅員による容積率上限",
                f"{result.far_by_road:.0f} %",
                delta=f"{site.road_width}m × {result.far_coeff}/10（建基法52条2項）",
                delta_color="off")
    if result.far_by_road < site.floor_area_ratio:
        st.warning(
            f"前面道路幅員により容積率は指定 {site.floor_area_ratio:.0f}% ではなく "
            f"**{result.actual_far:.0f}%** が適用されます（建基法52条2項）"
        )

    # ── 省エネ基準 ────────────────────────────────────────────────
    if result.ua_standard:
        with st.expander("♻️ 省エネ基準（R7年4月義務化）"):
            col1, col2, col3 = st.columns(3)
            col1.metric("地域区分", f"{result.energy_region}地域")
            col2.metric("U_A値義務基準", f"{result.ua_standard} W/(m²·K)")
            if result.ua_zeh:
                col3.metric("U_A値 ZEH水準", f"{result.ua_zeh} W/(m²·K)")
            st.caption(result.energy_region_label)

    # ── 斜線制限断面図 ────────────────────────────────────────────
    st.divider()
    st.subheader("📐 斜線制限断面図")
    st.caption("道路斜線（建基法56条1項1号）・北側斜線（同3号）の制限ラインと推定建物外形の関係を示します")
    render_setback_charts(site, result)

    # ── 参照リンク（法規条件の確認用） ─────────────────────────────
    st.divider()
    with st.expander("🔗 参照リンク（法規条件の確認用）", expanded=False):
        st.markdown(
            "本結果の用途地域・建蔽率・容積率等はGISデータ・入力値に基づく**参考値**です。"
            "確認申請前に必ず以下の公開情報および自治体窓口でご確認ください"
            "（高松市: 都市計画課 087-839-2455）。\n\n"
            "- [たかまっぷ（高松市地図ポータル）用途地域等]"
            "(https://takamatsu.geocloud.jp/webgis/?z=19&ll=34.342778%2C134.046667&t=DM&mp=90&op=70&vlf=90-84-00000ffffffe)\n"
            "- [たかまっぷ（高松市地図ポータル）道路種別等]"
            "(https://takamatsu.geocloud.jp/webgis/?z=19&ll=34.319565%2C134.005478&t=roadmap&mp=100&op=70&vlf=-1)\n"
            "- [国土交通省 不動産情報ライブラリ（用途地域・防火地域GISデータ出典）]"
            "(https://www.reinfolib.mlit.go.jp/)\n\n"
            "> 建築基準法上の道路種別は自動取得できないため、上記「道路種別等」の地図および"
            "高松市建築指導課での窓口確認が必要です。"
        )

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
            slr = _calc_slr(site, result)
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
