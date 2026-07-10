# GeoVisualizador de Valdivia

Aplicación web geoespacial construida con Python y Streamlit para el Trabajo Final
de Aplicaciones SIG (ASIG2026, Escuela de Geografía UACh).

**App en vivo:** https://mapweb-app-bjsvjfdxofwehczrguh8me.streamlit.app/

## Pregunta territorial

¿Cómo se relaciona la urbanización y la pérdida de cobertura vegetal con la
distribución de población en Valdivia, y qué rol juega esto en la temperatura
superficial (isla de calor) y la topografía?

## Capas y fuentes de datos

**Capas vectoriales**

| Capa | Fuente | Año / período | Tipo de geometría |
|---|---|---|---|
| Manzanas censales (población, hogares) | INE, Censo de Población y Vivienda | 2024 | Polígono |
| Uso de suelo | CONAF | 2024 | Polígono |
| Red vial | MOP | 2019 | Línea |

**Capas raster**

| Capa | Fuente | Año / período | Resolución |
|---|---|---|---|
| DEM (elevación) | OpenTopography (SRTM) | Misión 2000 | 30 m |
| NDVI (línea base y reciente) | Sentinel-2 SR, quality mosaic + Cloud Score+ | jul2019-jul2021 y jul2025-jul2026 | 10 m |
| Diferencia NDVI | Cálculo propio sobre los dos composites anteriores | 2020-2026 | 10 m |
| Temperatura superficial (LST) | Landsat 8/9 Collection 2, banda térmica | ene2025-jul2026 | 30 m |
| Serie histórica NDVI/LST | Sentinel-2 y Landsat 8/9, promedio anual de toda el área | 2019-2026 | 30 m |

Los rasters de NDVI, diferencia NDVI, LST y las estadísticas zonales por manzana
(`manzanas_ndvi_diff_stats.csv`, `manzanas_lst_stats.csv`) se generaron en Google
Earth Engine y se subieron pre-procesados a `data/`, no se calculan en tiempo real
en la app.

## Funcionalidades

**Requisitos mínimos:**
- Sidebar con checkboxes para activar/desactivar cada capa
- Estilos categóricos (uso de suelo), graduados (población, rasters continuos) y
  por jerarquía (red vial)
- Tooltips con múltiples atributos por capa
- Leyendas dentro del mapa
- 3 mapas base (OpenStreetMap, CartoDB claro, CartoDB oscuro)
- Control de capas (LayerControl)

**Funcionalidades avanzadas:**
- Panel de estadísticas por capa en el sidebar
- Filtro interactivo por población (visible solo cuando corresponde a la capa activa)
- 4 gráficos estadísticos (Plotly): superficie por uso de suelo, 3 análisis de
  correlación, serie histórica anual
- Tabla de atributos interactiva por capa
- Correlación entre atributos: población vs. distancia a áreas verdes, LST vs.
  distancia a áreas verdes, diferencia NDVI vs. población
- Descarga de datos filtrados (CSV y GeoJSON)
- Minimapa de referencia
- Modo pantalla completa
- Control de opacidad independiente por capa raster

## Estructura del repositorio

```
super-mapweb/
├── app.py                              # aplicación Streamlit
├── requirements.txt
├── data/
│   ├── Manzanas-Entidades.geojson
│   ├── Uso_Valdivia_cortado_conaf.shp  (+ .dbf .shx .prj .cpg .qmd)
│   ├── redvial2019.shp                 (+ .dbf .shx .prj .cpg .qmd)
│   ├── DEM_manzanas_Valdivia.tif
│   ├── NDVI_2020.tif
│   ├── NDVI_2026.tif
│   ├── NDVI_diff_2020_2026.tif
│   ├── LST_Valdivia_Landsat.tif
│   ├── manzanas_ndvi_diff_stats.csv
│   ├── manzanas_lst_stats.csv
│   ├── serie_ndvi_anual.csv
│   └── serie_lst_anual.csv
└── README.md
```

## Ejecutar localmente

```bash
git clone https://github.com/Luk343/mapweb-streamlit.git
cd super-mapweb
pip install -r requirements.txt
streamlit run app.py
```

## Notas técnicas

- CRS métrico para cálculos de distancia: EPSG:32718 (UTM 18S).
- La distancia de cada manzana al área verde más cercana se calcula con
  `gpd.sjoin_nearest` (índice espacial), no con `unary_union`, que resultó
  demasiado costoso en memoria para Streamlit Community Cloud con miles de
  polígonos.
- Los rasters continuos (NDVI, diferencia NDVI, LST) usan recorte por
  percentiles 2-98 para fijar la escala de color, en vez de mínimo/máximo
  crudo, porque los tif exportados desde GEE no traen nodata explícito y
  píxeles de borde o nube distorsionaban la paleta.
- Las capas provienen de años distintos porque corresponden a los productos
  oficiales más recientes disponibles en cada fuente. La red vial (2019) y el
  DEM (SRTM, 2000) se usan como referencia estructural de base, no como insumo
  temporal del análisis de cambio, que se apoya en NDVI y LST (2020-2026).

## Uso de inteligencia artificial

Se utilizó Claude (Anthropic) como apoyo iterativo durante el desarrollo: generación
de código base, resolución de errores de despliegue (crashes por operaciones
espaciales costosas, orden de subida de datos vs. código), y diseño de las
funciones de reproyección y estilo raster. Las decisiones de temática, interpretación
de resultados y arquitectura final de la app fueron del autor.

## Autor

Trabajo individual para el curso Aplicaciones SIG, Escuela de Geografía, UACh.
