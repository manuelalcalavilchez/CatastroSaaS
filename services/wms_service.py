"""
Servicio WMS - Descarga de mapas, procesamiento de KML y cálculo de afecciones
Integración de lógica del script 15.py para análisis geoespacial completo
"""
import xml.etree.ElementTree as ET
import requests
import numpy as np
from io import BytesIO
from PIL import Image
from shapely.geometry import Polygon, MultiPolygon, Point
from datetime import date
import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch
from matplotlib.path import Path
import json
import tempfile
import os


# ============================================
# PARSEO DE KML
# ============================================
def parse_kml_polygons(kml_content):
    """
    Parsea contenido KML (bytes o string) y extrae polígonos con huecos.
    Retorna lista de anillos: cada elemento es una lista de anillos (exterior + interiores).
    """
    if isinstance(kml_content, bytes):
        kml_content = kml_content.decode('utf-8')
    
    try:
        root = ET.fromstring(kml_content)
    except Exception as e:
        raise ValueError(f"Error al parsear KML: {e}")
    
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    polygons = []
    
    for placemark in root.findall(".//kml:Placemark", ns):
        for polygon in placemark.findall(".//kml:Polygon", ns):
            rings = []
            # Exterior + interiores
            for ring_tag in ["outerBoundaryIs", "innerBoundaryIs"]:
                for ring in polygon.findall(f".//kml:{ring_tag}/kml:LinearRing/kml:coordinates", ns):
                    coords = []
                    for c in ring.text.strip().split():
                        lon, lat, *_ = map(float, c.split(","))
                        coords.append((lon, lat))
                    if coords:
                        rings.append(coords)
            if rings:
                polygons.append(rings)
    
    return polygons


def polygons_to_shapely(polygons):
    """Convierte lista de anillos KML a geometría Shapely MultiPolygon."""
    geoms = []
    for rings in polygons:
        if not rings:
            continue
        exterior = rings[0]
        interiors = rings[1:] if len(rings) > 1 else []
        poly = Polygon(exterior, interiors)
        geoms.append(poly)
    return MultiPolygon(geoms) if geoms else None


# ============================================
# BBOX Y ZOOM
# ============================================
def get_bbox_from_polygons(polygons):
    """
    Calcula BBOX de los polígonos con amplificación de zoom.
    Retorna (lat_min, lon_min, lat_max, lon_max).
    """
    all_coords = [pt for poly in polygons for ring in poly for pt in ring]
    if not all_coords:
        raise ValueError("No coordinates found in polygons")
    
    lons = [c[0] for c in all_coords]
    lats = [c[1] for c in all_coords]
    lat_min, lat_max = min(lats), max(lats)
    lon_min, lon_max = min(lons), max(lons)

    zoom_factor = 3
    lat_center = (lat_min + lat_max) / 2
    lon_center = (lon_min + lon_max) / 2
    lat_half = (lat_max - lat_min) / 2
    lon_half = (lon_max - lon_min) / 2

    lat_min_zoom = lat_center - lat_half * zoom_factor
    lat_max_zoom = lat_center + lat_half * zoom_factor
    lon_min_zoom = lon_center - lon_half * zoom_factor
    lon_max_zoom = lon_center + lon_half * zoom_factor

    return (lat_min_zoom, lon_min_zoom, lat_max_zoom, lon_max_zoom)


# ============================================
# DESCARGA WMS
# ============================================
def download_wms_image(base_url, layer, style, bbox, format_type="image/png", width=800, height=600):
    """
    Descarga imagen WMS.
    bbox: (lat_min, lon_min, lat_max, lon_max)
    """
    lat_min, lon_min, lat_max, lon_max = bbox
    url = (
        f"{base_url}SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0&"
        f"LAYERS={layer}&STYLES={style}&CRS=EPSG:4326&"
        f"BBOX={lat_min},{lon_min},{lat_max},{lon_max}&WIDTH={width}&HEIGHT={height}&FORMAT={format_type}"
    )
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            return Image.open(BytesIO(r.content))
        else:
            raise Exception(f"HTTP {r.status_code}")
    except Exception as e:
        raise Exception(f"Error descargando WMS: {e}")


def download_wms_legend(base_url, layer, format_type="image/png"):
    """Descarga leyenda oficial WMS."""
    url = (
        f"{base_url}SERVICE=WMS&REQUEST=GetLegendGraphic&VERSION=1.3.0&"
        f"FORMAT={format_type}&LAYER={layer}"
    )
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            return Image.open(BytesIO(r.content))
    except Exception:
        pass
    return None


# ============================================
# DIBUJO DE POLÍGONOS
# ============================================
def draw_kml_polygons(ax, polygons):
    """Dibuja polígonos KML (con soporte para huecos) en un eje matplotlib."""
    for rings in polygons:
        vertices = []
        codes = []
        for ring in rings:
            codes += [Path.MOVETO] + [Path.LINETO] * (len(ring) - 1) + [Path.CLOSEPOLY]
            vertices += ring + [(0, 0)]
        path = Path(vertices, codes)
        patch = PathPatch(path, edgecolor='red', facecolor='none', linewidth=2)
        ax.add_patch(patch)


# ============================================
# COMPOSICIÓN DE IMAGEN CON LEYENDA
# ============================================
def compose_image_with_legend(layer_key, bbox, polygons):
    """
    Compone ortofoto + capa temática + polígono con leyenda.
    Retorna imagen PNG como bytes.
    """
    capas_config = {
        "MontesPublicos": {
            "base_url": "https://wms.mapama.gob.es/sig/Biodiversidad/IEPF_CMUP?",
            "layer": "AM.ForestManagementArea",
            "style": "",
            "titulo": "Parcela sobre Montes Públicos"
        },
        "RedNatura2000": {
            "base_url": "https://wms.mapama.gob.es/sig/Biodiversidad/RedNatura/wms.aspx?",
            "layer": "PS.ProtectedSite",
            "style": "",
            "titulo": "Parcela sobre Red Natura 2000"
        },
        "ViasPecuarias": {
            "base_url": "https://wms.mapama.gob.es/sig/Biodiversidad/ViasPecuarias/wms.aspx?",
            "layer": "Red General de Vías Pecuarias",
            "style": "default",
            "titulo": "Parcela sobre Vías Pecuarias"
        }
    }

    if layer_key not in capas_config:
        raise ValueError(f"Capa desconocida: {layer_key}")

    config = capas_config[layer_key]
    fondo_url = "https://www.ign.es/wms-inspire/pnoa-ma?"
    fondo_layer = "OI.OrthoimageCoverage"

    # Descargar fondo (ortofoto)
    fondo_img = download_wms_image(fondo_url, fondo_layer, "", bbox, format_type="image/jpeg")
    # Descargar capa temática
    capa_img = download_wms_image(config["base_url"], config["layer"], config["style"], bbox, format_type="image/png")

    # Crear figura
    fig, ax = plt.subplots(figsize=(10, 8), dpi=100)
    ax.imshow(fondo_img, extent=[bbox[1], bbox[3], bbox[0], bbox[2]], zorder=1)
    ax.imshow(capa_img, extent=[bbox[1], bbox[3], bbox[0], bbox[2]], alpha=0.6, zorder=2)
    draw_kml_polygons(ax, polygons)

    fecha = date.today().strftime("%d-%m-%Y")
    ax.set_title(f"{config['titulo']} ({fecha})", fontsize=13, fontweight='bold')
    ax.axis("off")

    # Intentar descargar leyenda oficial
    legend_img = download_wms_legend(config["base_url"], config["layer"])
    if legend_img:
        legend_ax = fig.add_axes([0.75, 0.05, 0.2, 0.2])
        legend_ax.imshow(legend_img)
        legend_ax.axis("off")

    plt.tight_layout()
    
    # Guardar a bytes
    buf = BytesIO()
    plt.savefig(buf, dpi=150, format='png', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    
    return buf.read()


# ============================================
# CÁLCULO DE AFECCIÓN POR PÍXELES
# ============================================
def calcular_porcentaje_pixeles(parcela_polygons, capa_img, bbox, umbral=250):
    """
    Calcula el porcentaje de píxeles afectados dentro de la parcela.
    umbral: umbral de valor de píxel (para capas de afección, píxeles más oscuros = más afectados).
    """
    parcela_geom = polygons_to_shapely(parcela_polygons)
    if not parcela_geom:
        return 0.0

    width, height = capa_img.size
    xs = np.linspace(bbox[1], bbox[3], width)
    ys = np.linspace(bbox[0], bbox[2], height)

    mask = np.zeros((height, width), dtype=bool)
    for i, y in enumerate(ys):
        for j, x in enumerate(xs):
            if parcela_geom.contains(Point(x, y)):
                mask[i, j] = True

    arr = np.array(capa_img.convert("L"))
    arr_masked = arr[mask]

    if arr_masked.size == 0:
        return 0.0

    afectados = np.sum(arr_masked < umbral)
    total = arr_masked.size
    porcentaje = (afectados / total) * 100 if total > 0 else 0.0
    
    return porcentaje


# ============================================
# PROCESAMIENTO COMPLETO (POR REFERENCIA KML)
# ============================================
def procesar_consulta_catastral(kml_content, referencia_catastral):
    """
    Procesa una consulta catastral: parsea KML, descarga mapas WMS, calcula afecciones.
    Retorna diccionario con resultados e imágenes.
    """
    try:
        # Parsear KML
        polygons = parse_kml_polygons(kml_content)
        if not polygons:
            raise ValueError("No se encontraron polígonos en el KML")

        bbox = get_bbox_from_polygons(polygons)

        # Capas a procesar
        capas = ["MontesPublicos", "RedNatura2000", "ViasPecuarias"]
        umbrales = [250, 200, 150]
        
        resultados = {
            "referencia": referencia_catastral,
            "capas": {},
            "imagenes": {}  # capa -> bytes PNG
        }

        for capa in capas:
            try:
                # Descargar imágenes y calcular porcentajes
                imagen_bytes = compose_image_with_legend(capa, bbox, polygons)
                resultados["imagenes"][capa] = imagen_bytes

                # Descargar capa para calcular afecciones
                config_urls = {
                    "MontesPublicos": ("https://wms.mapama.gob.es/sig/Biodiversidad/IEPF_CMUP?", "AM.ForestManagementArea", ""),
                    "RedNatura2000": ("https://wms.mapama.gob.es/sig/Biodiversidad/RedNatura/wms.aspx?", "PS.ProtectedSite", ""),
                    "ViasPecuarias": ("https://wms.mapama.gob.es/sig/Biodiversidad/ViasPecuarias/wms.aspx?", "Red General de Vías Pecuarias", "default")
                }
                base_url, layer, style = config_urls[capa]
                capa_img = download_wms_image(base_url, layer, style, bbox, format_type="image/png")

                resultados["capas"][capa] = {}
                for umbral in umbrales:
                    porcentaje = calcular_porcentaje_pixeles(polygons, capa_img, bbox, umbral=umbral)
                    resultados["capas"][capa][f"umbral_{umbral}"] = round(porcentaje, 2)

            except Exception as e:
                resultados["capas"][capa] = {"error": str(e)}

        return resultados

    except Exception as e:
        return {
            "referencia": referencia_catastral,
            "error": str(e),
            "capas": {},
            "imagenes": {}
        }
