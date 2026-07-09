import streamlit as st
import geopandas as gpd
import pandas as pd
import numpy as np
import folium
import folium.plugins
from streamlit_folium import st_folium
from pathlib import Path
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
import io, base64
from PIL import Image
import matplotlib.colors as mcolors
import plotly.express as px

# ─────────────────────────────────────────────────────────────
# Configuración
# ─────────────────────────────────────────────────────────────

st.set_page_config(page_title="GeoVisualizador de Valdivia", layout="wide")
st.title("🌎 GeoVisualizador de Valdivia — Territorio, Uso de Suelo y Vialidad")
st.write(
    "Manzanas censales (Censo 2024), uso de suelo (CONAF), red vial (MOP) y "
    "elevación de la comuna de Valdivia. Selecciona las capas en el panel lateral."
)

DATA = Path("data")

# ─────────────────────────────────────────────────────────────
# PASO 1: Paletas cartográficas
# ─────────────────────────────────────────────────────────────

PALETA_USO_SUELO = [
    "#E8A33D", "#4C9A4C", "#8FBF6A", "#2E7D32", "#5CC8C8",
    "#B0B0B0", "#3F7FBF", "#C97A4A", "#D9C36A", "#7A5C3E",
]

ESTILOS_VIAL = {
    "nacional":     {"color": "#CC0000", "weight": 5},
    "regional":     {"color": "#E05000", "weight": 3.5},
    "provincial":   {"color": "#FF8800", "weight": 2.5},
    "comunal":      {"color": "#DAA520", "weight": 1.8},
    "camino":       {"color": "#8B6914", "weight": 1.5},
    "sendero":      {"color": "#A0522D", "weight": 1},
    "default":      {"color": "#888888", "weight": 1.5},
}

COLORMAP_POBLACION = [
    (0.00, "#ffffcc"),
    (0.25, "#fed976"),
    (0.50, "#fd8d3c"),
    (0.75, "#e31a1c"),
    (1.00, "#800026"),
]

COLORMAP_DEM = [
    (0.00, "#006400"),
    (0.15, "#228B22"),
    (0.30, "#9ACD32"),
    (0.45, "#DAA520"),
    (0.60, "#CD853F"),
    (0.75, "#8B4513"),
    (0.88, "#D2B48C"),
    (1.00, "#FFFAFA"),
]

# ─────────────────────────────────────────────────────────────
# PASO 2: Funciones de color / estilo
# ─────────────────────────────────────────────────────────────

def construir_mapa_colores(serie, paleta):
    valores = sorted(serie.dropna().unique().tolist())
    return {str(v): paleta[i % len(paleta)] for i, v in enumerate(valores)}


def crear_style_uso_suelo(color_map):
    def style_fn(feature):
        val = str(feature["properties"].get("USO", ""))
        color = color_map.get(val, "#AAAAAA")
        return {"fillColor": color, "color": "#444444", "weight": 0.4, "fillOpacity": 0.65}
    return style_fn


def crear_style_vial():
    def style_fn(feature):
        catego = str(feature["properties"].get("Catego", "")).lower()
        clase = str(feature["properties"].get("Clase_Ruta", "")).lower()
        texto = f"{catego} {clase}"
        for key, vals in ESTILOS_VIAL.items():
            if key in texto:
                return {"color": vals["color"], "weight": vals["weight"], "opacity": 0.9}
        d = ESTILOS_VIAL["default"]
        return {"color": d["color"], "weight": d["weight"], "opacity": 0.9}
    return style_fn


def crear_style_poblacion(pob_min, pob_max):
    posiciones = [p for p, _ in COLORMAP_POBLACION]
    colores = [c for _, c in COLORMAP_POBLACION]
    cmap = mcolors.LinearSegmentedColormap.from_list("pob", list(zip(posiciones, colores)))

    def style_fn(feature):
        val = feature["properties"].get("n_per", 0) or 0
        norm = 0 if pob_max == pob_min else (val - pob_min) / (pob_max - pob_min)
        r, g, b, _ = cmap(norm)
        color = mcolors.to_hex((r, g, b))
        return {"fillColor": color, "color": "#555555", "weight": 0.5, "fillOpacity": 0.72}
    return style_fn

# ─────────────────────────────────────────────────────────────
# PASO 3: Leyendas HTML
# ─────────────────────────────────────────────────────────────

def leyenda_categorica_html(titulo, color_map, icono="🔲", top="10px"):
    items = ""
    for etiqueta, color in sorted(color_map.items()):
        items += f"""
        <div style="display:flex;align-items:center;margin:3px 0;">
          <div style="background:{color};width:16px;height:16px;
                      border:1px solid #555;margin-right:7px;
                      border-radius:2px;flex-shrink:0;"></div>
          <span style="font-size:11px;color:#222;">{etiqueta}</span>
        </div>"""
    return f"""
    <div style="position:fixed;top:{top};right:10px;z-index:1000;
        background:rgba(255,255,255,0.93);padding:10px 14px;border-radius:8px;
        border:1px solid #bbb;box-shadow:2px 2px 6px rgba(0,0,0,0.25);
        max-height:280px;overflow-y:auto;min-width:170px;font-family:Arial,sans-serif;">
      <b style="font-size:12px;">{icono} {titulo}</b>
      <hr style="margin:5px 0;border-color:#ddd;">
      {items}
    </div>"""


def leyenda_graduada_html(titulo, colormap_stops, val_min, val_max, unidad="", icono="📊", top="10px"):
    stops = ", ".join([f"{color} {int(pct*100)}%" for pct, color in colormap_stops])
    gradient = f"linear-gradient(to top, {stops})"
    return f"""
    <div style="position:fixed;top:{top};right:10px;z-index:1000;
        background:rgba(255,255,255,0.93);padding:10px 14px;border-radius:8px;
        border:1px solid #bbb;box-shadow:2px 2px 6px rgba(0,0,0,0.25);
        min-width:130px;font-family:Arial,sans-serif;">
      <b style="font-size:12px;">{icono} {titulo}</b>
      <hr style="margin:5px 0;border-color:#ddd;">
      <div style="display:flex;align-items:stretch;gap:8px;">
        <div style="width:22px;height:150px;background:{gradient};
                    border:1px solid #888;border-radius:3px;flex-shrink:0;"></div>
        <div style="display:flex;flex-direction:column;justify-content:space-between;
                    font-size:11px;color:#333;">
          <span><b>{int(val_max)}{unidad}</b></span>
          <span>{int(val_min + (val_max - val_min) * 0.75)}{unidad}</span>
          <span>{int(val_min + (val_max - val_min) * 0.50)}{unidad}</span>
          <span>{int(val_min + (val_max - val_min) * 0.25)}{unidad}</span>
          <span><b>{int(val_min)}{unidad}</b></span>
        </div>
      </div>
    </div>"""

# ─────────────────────────────────────────────────────────────
# PASO 4: Raster → ImageOverlay (con reproyección real)
# ─────────────────────────────────────────────────────────────

def aplicar_colormap_dem(band, nodata):
    posiciones = [p for p, _ in COLORMAP_DEM]
    colores = [c for _, c in COLORMAP_DEM]
    cmap = mcolors.LinearSegmentedColormap.from_list("dem", list(zip(posiciones, colores)))

    mascara = (band == nodata) if nodata is not None else np.zeros_like(band, dtype=bool)
    valid = band[~mascara]
    dem_min = float(valid.min()) if len(valid) > 0 else 0
    dem_max = float(valid.max()) if len(valid) > 0 else 1

    norm = mcolors.Normalize(vmin=dem_min, vmax=dem_max)
    rgba = cmap(norm(band))
    rgba[mascara, 3] = 0
    rgba[~mascara, 3] = 0.82
    return (rgba * 255).astype(np.uint8), dem_min, dem_max


@st.cache_data
def raster_a_overlay(raster_path):
    with rasterio.open(raster_path) as src:
        if src.crs and src.crs.to_epsg() != 4326:
            transform, width, height = calculate_default_transform(
                src.crs, "EPSG:4326", src.width, src.height, *src.bounds
            )
            data = np.zeros((1, height, width), dtype=np.float32)
            reproject(
                source=rasterio.band(src, 1),
                destination=data[0],
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=transform,
                dst_crs="EPSG:4326",
                resampling=Resampling.bilinear,
            )
            bounds_wgs84 = rasterio.transform.array_bounds(height, width, transform)
        else:
            data = src.read(1, out_dtype="float32")[np.newaxis, :, :]
            bounds_wgs84 = src.bounds

        nodata = src.nodata
        img_array, dem_min, dem_max = aplicar_colormap_dem(data[0], nodata)

        img_pil = Image.fromarray(img_array)
        buf = io.BytesIO()
        img_pil.save(buf, format="PNG")
        buf.seek(0)
        img_b64 = base64.b64encode(buf.read()).decode("utf-8")

        bounds = [[bounds_wgs84[1], bounds_wgs84[0]], [bounds_wgs84[3], bounds_wgs84[2]]]
        return img_b64, bounds, dem_min, dem_max

# ─────────────────────────────────────────────────────────────
# Cargar datos
# ─────────────────────────────────────────────────────────────

@st.cache_data
def load_vectors():
    manzanas = gpd.read_file(DATA / "Manzanas-Entidades.shp").to_crs(4326)
    uso = gpd.read_file(DATA / "Uso_Valdivia_cortado_conaf.shp").to_crs(4326)
    vial = gpd.read_file(DATA / "redvial2019.shp").to_crs(4326)
    manzanas["n_per"] = pd.to_numeric(manzanas["n_per"], errors="coerce").fillna(0)
    uso["SUPERF_HA"] = pd.to_numeric(uso["SUPERF_HA"], errors="coerce").fillna(0)
    vial["shape_leng"] = pd.to_numeric(vial["shape_leng"], errors="coerce").fillna(0)
    return manzanas, uso, vial


manzanas, uso, vial = load_vectors()
color_map_uso = construir_mapa_colores(uso["USO"], PALETA_USO_SUELO)

# ─────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────

st.sidebar.title("GeoVisualizador Valdivia")

st.sidebar.subheader("🗺️ Capas vectoriales")
show_manzanas = st.sidebar.checkbox("Manzanas censales (población)", value=True)
show_uso = st.sidebar.checkbox("Uso de suelo (CONAF)", value=True)
show_vial = st.sidebar.checkbox("Red vial (MOP)", value=False)

st.sidebar.subheader("🛰️ Raster")
show_dem = st.sidebar.checkbox("DEM (elevación)", value=False)

st.sidebar.subheader("🔍 Filtro")
pob_min, pob_max = int(manzanas["n_per"].min()), int(manzanas["n_per"].max())
rango_pob = st.sidebar.slider("Población por manzana", pob_min, pob_max, (pob_min, pob_max))
manzanas_filtradas = manzanas[(manzanas["n_per"] >= rango_pob[0]) & (manzanas["n_per"] <= rango_pob[1])]

st.sidebar.subheader("📊 Capa para análisis")
capa_analisis = st.sidebar.selectbox("Selecciona capa", ["Manzanas censales", "Uso de suelo", "Red vial"])

st.sidebar.markdown("---")
st.sidebar.subheader("Estadísticas")
if capa_analisis == "Manzanas censales":
    st.sidebar.metric("Manzanas en filtro", len(manzanas_filtradas))
    st.sidebar.metric("Población total", int(manzanas_filtradas["n_per"].sum()))
    st.sidebar.metric("Promedio por manzana", round(manzanas_filtradas["n_per"].mean(), 1) if len(manzanas_filtradas) else 0)
elif capa_analisis == "Uso de suelo":
    st.sidebar.metric("Polígonos", len(uso))
    st.sidebar.metric("Área total (ha)", round(uso["SUPERF_HA"].sum(), 1))
else:
    st.sidebar.metric("Tramos viales", len(vial))
    st.sidebar.metric("Longitud total (m)", round(vial["shape_leng"].sum(), 1))

# ─────────────────────────────────────────────────────────────
# Mapa base
# ─────────────────────────────────────────────────────────────

centro = [manzanas.geometry.centroid.y.mean(), manzanas.geometry.centroid.x.mean()]
m = folium.Map(location=centro, zoom_start=12, tiles="OpenStreetMap")
folium.TileLayer("CartoDB positron", name="Mapa claro").add_to(m)
folium.TileLayer("CartoDB dark_matter", name="Mapa oscuro").add_to(m)

leyendas_html = []
offset_top = 10

# ─────────────────────────────────────────────────────────────
# Raster DEM
# ─────────────────────────────────────────────────────────────

if show_dem:
    try:
        with st.spinner("Cargando DEM..."):
            img_b64, bounds, dem_min, dem_max = raster_a_overlay(DATA / "DEM_manzanas_Valdivia.tif")
        folium.raster_layers.ImageOverlay(
            image=f"data:image/png;base64,{img_b64}",
            bounds=bounds, opacity=0.80, name="🛰 DEM (elevación)",
        ).add_to(m)
        leyendas_html.append(leyenda_graduada_html(
            "Elevación", COLORMAP_DEM, dem_min, dem_max, unidad=" m", icono="🏔️", top=f"{offset_top}px"
        ))
        offset_top += 220
    except Exception as e:
        st.warning(f"No fue posible cargar el DEM: {e}")

# ─────────────────────────────────────────────────────────────
# Uso de suelo (categórico)
# ─────────────────────────────────────────────────────────────

if show_uso:
    folium.GeoJson(
        uso, name="🌳 Uso de suelo (CONAF)",
        style_function=crear_style_uso_suelo(color_map_uso),
        tooltip=folium.GeoJsonTooltip(fields=["USO", "SUBUSO", "SUPERF_HA"],
                                       aliases=["Uso:", "Subuso:", "Superficie (ha):"]),
    ).add_to(m)
    leyendas_html.append(leyenda_categorica_html(
        "Uso de suelo", color_map_uso, icono="🌳", top=f"{offset_top}px"
    ))
    offset_top += min(60 + len(color_map_uso) * 23, 300) + 10

# ─────────────────────────────────────────────────────────────
# Red vial (jerarquía)
# ─────────────────────────────────────────────────────────────

if show_vial:
    folium.GeoJson(
        vial, name="🛣️ Red vial (MOP)",
        style_function=crear_style_vial(),
        tooltip=folium.GeoJsonTooltip(fields=["Nom_Ruta", "Clase_Ruta", "Catego"],
                                       aliases=["Ruta:", "Clase:", "Categoría:"]),
    ).add_to(m)

# ─────────────────────────────────────────────────────────────
# Manzanas censales (graduado por población)
# ─────────────────────────────────────────────────────────────

if show_manzanas and len(manzanas_filtradas):
    folium.GeoJson(
        manzanas_filtradas, name="🏘️ Manzanas censales (población)",
        style_function=crear_style_poblacion(
            manzanas_filtradas["n_per"].min(), manzanas_filtradas["n_per"].max()
        ),
        tooltip=folium.GeoJsonTooltip(
            fields=["COMUNA", "n_per", "n_hog", "prom_per_hog"],
            aliases=["Comuna:", "Población:", "N° hogares:", "Prom. per./hogar:"],
        ),
    ).add_to(m)
    leyendas_html.append(leyenda_graduada_html(
        "Población por manzana", COLORMAP_POBLACION,
        manzanas_filtradas["n_per"].min(), manzanas_filtradas["n_per"].max(),
        icono="🏘️", top=f"{offset_top}px"
    ))

# ─────────────────────────────────────────────────────────────
# Ensamblar mapa
# ─────────────────────────────────────────────────────────────

for html in leyendas_html:
    m.get_root().html.add_child(folium.Element(html))

folium.plugins.Fullscreen(position="topleft").add_to(m)
folium.plugins.MiniMap(toggle_display=True).add_to(m)
folium.LayerControl(collapsed=False).add_to(m)

st_folium(m, width=1200, height=680)

# ─────────────────────────────────────────────────────────────
# Gráfico estadístico
# ─────────────────────────────────────────────────────────────

st.subheader("Superficie por categoría de uso de suelo")
area_por_uso = (uso.groupby("USO")["SUPERF_HA"].sum().reset_index()
                 .sort_values("SUPERF_HA", ascending=False))
fig = px.bar(area_por_uso, x="USO", y="SUPERF_HA", color="USO",
             color_discrete_map=color_map_uso,
             labels={"SUPERF_HA": "Superficie (ha)", "USO": "Uso de suelo"})
st.plotly_chart(fig, use_container_width=True)

# ─────────────────────────────────────────────────────────────
# Tabla de atributos
# ─────────────────────────────────────────────────────────────

st.subheader(f"Tabla de atributos — {capa_analisis}")
if capa_analisis == "Manzanas censales":
    cols = ["COMUNA", "n_per", "n_hog", "n_mujeres", "n_hombres", "prom_per_hog"]
    st.dataframe(manzanas_filtradas[cols], use_container_width=True)
elif capa_analisis == "Uso de suelo":
    st.dataframe(uso[["USO", "SUBUSO", "COBERTURA", "SUPERF_HA"]], use_container_width=True)
else:
    st.dataframe(vial[["Nom_Ruta", "Clase_Ruta", "Catego", "shape_leng"]], use_container_width=True)
