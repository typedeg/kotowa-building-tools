"""住所から用途地域・建蔽率・容積率・防火指定を自動取得するモジュール。

データソース（正規ルート・利用規約準拠）:
  1. 国土地理院 ジオコーディングAPI（住所 → 緯度経度・無料・キー不要）
     https://msearch.gsi.go.jp/address-search/AddressSearch
  2. 国交省 不動産情報ライブラリ XKT002（用途地域）・XKT014（防火・準防火地域）
     https://www.reinfolib.mlit.go.jp/ex-api/external/
     APIキーは tools/mlit-geospatial-mcp/.env の LIBRARY_API_KEY を流用

注意:
  - 取得値はGISデータによる参考値。確認申請前に必ず自治体（高松市は都市計画課
    087-839-2455）で確認すること。
  - 建築基準法上の道路種別はAPI提供がないため取得しない。
    高松市内は「たかまっぷ」を人が閲覧して確認する（レポートに引用リンクを記載）。
"""
from __future__ import annotations

import json
import math
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

GSI_GEOCODE_URL = 'https://msearch.gsi.go.jp/address-search/AddressSearch'
REINFOLIB_URL = 'https://www.reinfolib.mlit.go.jp/ex-api/external'
ZOOM = 15  # XKT系APIの推奨ズームレベル

# たかまっぷ（高松市WebGIS）引用リンク — レポート掲載用
TAKAMAP_YOUTO_URL = (
    'https://takamatsu.geocloud.jp/webgis/'
    '?z=19&ll=34.342778%2C134.046667&t=DM&mp=90&op=70&vlf=90-84-00000ffffffe'
)
TAKAMAP_ROAD_URL = (
    'https://takamatsu.geocloud.jp/webgis/'
    '?z=19&ll=34.319565%2C134.005478&t=roadmap&mp=100&op=70&vlf=-1'
)


@dataclass
class ZoningResult:
    """住所調査の結果"""
    address: str = ''
    matched_address: str = ''      # ジオコーディングでヒットした住所表記
    lat: float = 0.0
    lon: float = 0.0
    use_district: Optional[str] = None      # 用途地域名
    coverage_ratio: Optional[float] = None  # 建蔽率 (%)
    floor_area_ratio: Optional[float] = None  # 容積率 (%)
    fire_zone: Optional[str] = None         # なし/準防火/防火
    raw_properties: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)


def _load_api_key() -> Optional[str]:
    """LIBRARY_API_KEY を環境変数 → mlit-geospatial-mcp/.env の順で探す"""
    key = os.getenv('LIBRARY_API_KEY')
    if key:
        return key
    env_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        '..', 'mlit-geospatial-mcp', '.env'
    )
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('LIBRARY_API_KEY'):
                    return line.split('=', 1)[1].strip().strip('"\'')
    except OSError:
        pass
    return None


def _fetch_json(url: str, headers: Optional[dict] = None) -> object:
    h = {'User-Agent': 'kotowa-madori-generator/1.0'}
    h.update(headers or {})
    req = urllib.request.Request(url, headers=h)
    last_err = None
    for _ in range(2):  # 一時的な失敗に備えて1回リトライ
        try:
            with urllib.request.urlopen(req, timeout=15) as res:
                return json.loads(res.read().decode('utf-8'))
        except Exception as e:
            last_err = e
    raise last_err


def geocode(address: str) -> tuple[float, float, str]:
    """住所 → (lat, lon, ヒットした住所表記)。国土地理院API使用。"""
    url = f'{GSI_GEOCODE_URL}?q={urllib.parse.quote(address)}'
    data = _fetch_json(url)
    if not data:
        raise ValueError(f'住所が見つかりません: {address}')
    top = data[0]
    lon, lat = top['geometry']['coordinates']
    title = top.get('properties', {}).get('title', address)
    return float(lat), float(lon), title


def _latlon_to_tile(lat: float, lon: float, zoom: int = ZOOM) -> tuple[int, int]:
    """緯度経度 → タイル座標（Webメルカトル）"""
    n = 2 ** zoom
    lat_rad = math.radians(lat)
    x = int(n * ((lon + 180) / 360))
    y = int(n * (1 - (math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi)) / 2)
    return x, y


def _point_in_ring(lon: float, lat: float, ring: list) -> bool:
    """レイキャスティング法による点の多角形内判定（外部ライブラリ不要）"""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat):
            x_cross = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lon < x_cross:
                inside = not inside
        j = i
    return inside


def _point_in_feature(lon: float, lat: float, geometry: dict) -> bool:
    """Polygon / MultiPolygon に対する内外判定（穴も考慮）"""
    gtype = geometry.get('type')
    if gtype == 'Polygon':
        polygons = [geometry['coordinates']]
    elif gtype == 'MultiPolygon':
        polygons = geometry['coordinates']
    else:
        return False
    for poly in polygons:
        if not poly:
            continue
        if _point_in_ring(lon, lat, poly[0]):  # 外周リング
            in_hole = any(_point_in_ring(lon, lat, hole) for hole in poly[1:])
            if not in_hole:
                return True
    return False


def _query_reinfolib(api_code: str, lat: float, lon: float,
                     api_key: str) -> Optional[dict]:
    """XKT系APIのタイルを取得し、緯度経度を含むフィーチャの properties を返す"""
    x, y = _latlon_to_tile(lat, lon)
    url = (f'{REINFOLIB_URL}/{api_code}'
           f'?response_format=geojson&z={ZOOM}&x={x}&y={y}')
    data = _fetch_json(url, headers={'Ocp-Apim-Subscription-Key': api_key})
    for feat in data.get('features', []):
        if _point_in_feature(lon, lat, feat.get('geometry', {})):
            return feat.get('properties', {})
    return None


def _pick(props: dict, keywords: list[str]) -> Optional[str]:
    """propertiesから、キー名にキーワードを含む値を探す（API仕様の表記揺れ対策）"""
    for key, value in props.items():
        if value is None or value == '':
            continue
        if any(kw in key for kw in keywords):
            return value
    return None


def _parse_percent(value) -> Optional[float]:
    """'80%'・'８０％'・80 などの表記を float に変換する"""
    s = str(value).translate(str.maketrans('０１２３４５６７８９．', '0123456789.'))
    s = s.replace('%', '').replace('％', '').strip()
    try:
        return float(s)
    except ValueError:
        return None


def lookup(address: str) -> ZoningResult:
    """住所から用途地域・建蔽率・容積率・防火指定を取得する"""
    result = ZoningResult(address=address)

    lat, lon, matched = geocode(address)
    result.lat, result.lon, result.matched_address = lat, lon, matched

    api_key = _load_api_key()
    if not api_key:
        result.warnings.append(
            'LIBRARY_API_KEY が見つかりません（tools/mlit-geospatial-mcp/.env を確認）。'
            '用途地域の自動取得をスキップしました'
        )
        return result

    # 用途地域（XKT002）
    try:
        props = _query_reinfolib('XKT002', lat, lon, api_key)
        if props:
            result.raw_properties = props
            result.use_district = _pick(
                props, ['use_area_ja', 'youto_area_full_ja', '用途地域'])
            bcr = _pick(props, ['u_building_coverage_ratio', 'kenpei', '建蔽', '建ぺい'])
            far = _pick(props, ['u_floor_area_ratio', 'yoseki', '容積'])
            if bcr is not None:
                result.coverage_ratio = _parse_percent(bcr)
            if far is not None:
                result.floor_area_ratio = _parse_percent(far)
        else:
            result.warnings.append(
                '指定地点の用途地域データが見つかりません（都市計画区域外の可能性）')
    except Exception as e:
        result.warnings.append(f'用途地域API（XKT002）取得エラー: {e}')

    # 防火・準防火地域（XKT014）
    try:
        props = _query_reinfolib('XKT014', lat, lon, api_key)
        if props:
            name = _pick(props, ['fire_prevention_ja', 'fire_prevention', '防火']) or ''
            if '準防火' in str(name):
                result.fire_zone = '準防火'
            elif '防火' in str(name):
                result.fire_zone = '防火'
        else:
            result.fire_zone = 'なし'
    except Exception as e:
        result.warnings.append(f'防火地域API（XKT014）取得エラー: {e}')

    result.warnings.append(
        '自動取得値はGISデータによる参考値です。確認申請前に必ず自治体で確認してください'
        '（高松市: 都市計画課 087-839-2455）'
    )
    return result
