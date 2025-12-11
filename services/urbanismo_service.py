"""
Servicio de Urbanismo - Descarga WFS, análisis de planeamiento y cálculo de intersecciones
Integración de lógica del script 16.py para análisis urbano completo
"""
import geopandas as gpd
import requests
from io import BytesIO
import json
from datetime import date
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np


# ============================================
# DESCARGA WFS (Web Feature Service)
# ============================================
def descargar_capa_wfs(base_url, typename, srs_name="EPSG:4326"):
    """
    Descarga una capa WFS como GeoDataFrame.
    Convierte a EPSG:25830 (UTM 30N) para cálculos de área.
    """
    params = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "GetFeature",
        "typename": typename,
        "outputFormat": "json",
        "srsName": srs_name
    }
    try:
        r = requests.get(base_url, params=params, timeout=60)
        if r.status_code == 200:
            gdf = gpd.read_file(BytesIO(r.content))
            gdf.columns = [c.lower() for c in gdf.columns]
            # Reproyectar para cálculos de área
            gdf = gdf.to_crs(epsg=25830)
            return gdf
        else:
            raise Exception(f"HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        raise Exception(f"Error descargando WFS: {e}")


# ============================================
# CONVERSIÓN A GEODATAFRAME
# ============================================
def geojson_a_gdf(geojson_content):
    """Convierte contenido GeoJSON a GeoDataFrame."""
    try:
        if isinstance(geojson_content, str):
            geojson_obj = json.loads(geojson_content)
        else:
            geojson_obj = geojson_content
        
        gdf = gpd.GeoDataFrame.from_features(geojson_obj.get('features', []), crs="EPSG:4326")
        gdf = gdf.to_crs(epsg=25830)  # UTM 30N para cálculos de área
        return gdf
    except Exception as e:
        raise ValueError(f"Error al convertir GeoJSON: {e}")


def gdf_a_geojson(gdf):
    """Convierte GeoDataFrame a GeoJSON."""
    return gdf.to_crs("EPSG:4326").__geo_interface__


# ============================================
# CÁLCULO DE INTERSECCIONES Y PORCENTAJES
# ============================================
def calcular_porcentajes_planeamiento(gdf_parcela, gdf_planeamiento):
    """
    Calcula los porcentajes de la parcela cubiertos por cada clase de suelo.
    Retorna resumen de áreas y porcentajes.
    """
    try:
        # Asegurar proyección UTM
        gdf_parcela = gdf_parcela.to_crs(epsg=25830)
        gdf_planeamiento = gdf_planeamiento.to_crs(epsg=25830)
        
        # Overlay: intersección
        interseccion = gpd.overlay(gdf_planeamiento, gdf_parcela, how="intersection")
        
        if interseccion.empty:
            return {}, {}
        
        interseccion["area_m2"] = interseccion.geometry.area
        
        # Crear etiquetas de tipo suelo (puede incluir subtipos)
        if "clasificacion" in interseccion.columns:
            interseccion["tipo_suelo"] = interseccion["clasificacion"].astype(str)
            
            # Si existe "ambito", diferenciar subtipos (ej: No Urbanizable - Común)
            if "ambito" in interseccion.columns:
                mask_no_urb = interseccion["clasificacion"].str.contains(
                    "No Urbanizable", case=False, na=False
                )
                interseccion.loc[mask_no_urb, "tipo_suelo"] = (
                    interseccion["clasificacion"] + " - " + 
                    interseccion["ambito"].fillna("").astype(str)
                )
        else:
            # Si no existe clasificacion, usar la primera columna de geometría
            interseccion["tipo_suelo"] = "Suelo"
        
        # Agrupar por tipo de suelo
        resumen = interseccion.groupby("tipo_suelo", as_index=False)["area_m2"].sum()
        total_area = resumen["area_m2"].sum()
        
        resumen["porcentaje"] = (resumen["area_m2"] / total_area * 100).round(2)
        
        return resumen.to_dict(orient="list"), total_area
        
    except Exception as e:
        raise Exception(f"Error al calcular porcentajes: {e}")


# ============================================
# DESCARGA ORTOFOTO WMS (IGN PNOA)
# ============================================
def descargar_ortofoto_wms(bbox_epsg3857, wms_url="https://www.ign.es/wms-inspire/pnoa-ma"):
    """
    Descarga ortofoto desde IGN PNOA.
    bbox: (minx, miny, maxx, maxy) en EPSG:3857
    Retorna imagen como bytes PNG.
    """
    try:
        from owslib.wms import WebMapService
        
        wms = WebMapService(wms_url, version="1.3.0")
        minx, miny, maxx, maxy = bbox_epsg3857
        
        img = wms.getmap(
            layers=["OI.OrthoimageCoverage"],
            srs="EPSG:3857",
            bbox=(minx, miny, maxx, maxy),
            size=(1000, 1000),
            format="image/jpeg",
            transparent=True
        )
        return img.read()
    except Exception as e:
        raise Exception(f"Error descargando ortofoto: {e}")


# ============================================
# DESCARGA URBANISMO WMS (CARM Murcia)
# ============================================
def descargar_urbanismo_wms(
    bbox_epsg3857,
    wms_url="https://mapas-gis-inter.carm.es/geoserver/SIT_USU_PLA_URB_CARM/wms?"
):
    """
    Descarga capa de planeamiento urbanístico de CARM (Región de Murcia).
    bbox: (minx, miny, maxx, maxy) en EPSG:3857
    Retorna imagen como bytes PNG.
    """
    try:
        from owslib.wms import WebMapService
        
        wms = WebMapService(wms_url, version="1.3.0")
        minx, miny, maxx, maxy = bbox_epsg3857
        
        img = wms.getmap(
            layers=["SIT_USU_PLA_URB_CARM:clases_plu_ze_37mun"],
            srs="EPSG:3857",
            bbox=(minx, miny, maxx, maxy),
            size=(1000, 1000),
            format="image/png",
            transparent=True
        )
        return img.read()
    except Exception as e:
        raise Exception(f"Error descargando urbanismo: {e}")


def descargar_leyenda_urbanismo(
    wms_url="https://mapas-gis-inter.carm.es/geoserver/SIT_USU_PLA_URB_CARM/wms?"
):
    """Descarga leyenda oficial de la capa de urbanismo."""
    try:
        url = (
            f"{wms_url}service=WMS&version=1.1.0&request=GetLegendGraphic&"
            f"layer=SIT_USU_PLA_URB_CARM:clases_plu_ze_37mun&format=image/png"
        )
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            return r.content
        return None
    except Exception:
        return None


# ============================================
# CONVERSIÓN DE COORDENADAS
# ============================================
def bbox_4326_a_3857(bbox_4326):
    """
    Convierte bbox EPSG:4326 a EPSG:3857 (Web Mercator).
    bbox: (minx, miny, maxx, maxy)
    """
    from pyproj import Transformer
    transformer = Transformer.from_epsg(4326, 3857)
    minx, miny, maxx, maxy = bbox_4326
    minx_3857, miny_3857 = transformer.transform(miny, minx)
    maxx_3857, maxy_3857 = transformer.transform(maxy, maxx)
    return (minx_3857, miny_3857, maxx_3857, maxy_3857)


def bbox_3857_a_4326(bbox_3857):
    """Convierte bbox EPSG:3857 a EPSG:4326."""
    from pyproj import Transformer
    transformer = Transformer.from_epsg(3857, 4326)
    minx, miny, maxx, maxy = bbox_3857
    miny_4326, minx_4326 = transformer.transform(miny, minx)
    maxy_4326, maxx_4326 = transformer.transform(maxy, maxx)
    return (minx_4326, miny_4326, maxx_4326, maxy_4326)


# ============================================
# GENERACIÓN DE MAPA COMPUESTO
# ============================================
def generar_mapa_urbanismo(
    gdf_parcela,
    bbox_3857,
    ortofoto_bytes,
    urbanismo_bytes,
    leyenda_bytes=None,
    titulo="Análisis de Planeamiento Urbano"
):
    """
    Genera mapa final: ortofoto + urbanismo + parcela + leyenda.
    Retorna imagen como bytes PNG.
    """
    try:
        from PIL import Image
        
        fig, ax = plt.subplots(figsize=(12, 10), dpi=100)
        
        # Cargar y mostrar ortofoto
        ortofoto = Image.open(BytesIO(ortofoto_bytes))
        minx, miny, maxx, maxy = bbox_3857
        extent_3857 = [minx, maxx, miny, maxy]
        ax.imshow(ortofoto, extent=extent_3857, origin="upper", zorder=1)
        
        # Cargar y mostrar urbanismo
        if urbanismo_bytes:
            urbanismo = Image.open(BytesIO(urbanismo_bytes))
            ax.imshow(urbanismo, extent=extent_3857, origin="upper", alpha=0.5, zorder=2)
        
        # Reproyectar parcela a 3857 y dibujar
        gdf_parcela_3857 = gdf_parcela.to_crs(epsg=3857)
        gdf_parcela_3857.boundary.plot(ax=ax, color="red", linewidth=3, zorder=3)
        
        fecha = date.today().strftime("%d-%m-%Y")
        ax.set_title(f"{titulo}\n({fecha})", fontsize=14, fontweight="bold")
        ax.axis("off")
        
        # Añadir leyenda si está disponible
        if leyenda_bytes:
            leyenda_img = Image.open(BytesIO(leyenda_bytes))
            ax_leyenda = fig.add_axes([0.72, 0.05, 0.25, 0.25])
            ax_leyenda.imshow(leyenda_img)
            ax_leyenda.axis("off")
        
        plt.tight_layout()
        
        # Guardar a bytes
        buf = BytesIO()
        plt.savefig(buf, dpi=150, format='png', bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        
        return buf.read()
    except Exception as e:
        raise Exception(f"Error generando mapa: {e}")


# ============================================
# PROCESAMIENTO COMPLETO
# ============================================
def procesar_consulta_urbanismo(
    geojson_content,
    referencia_catastral,
    base_url_wfs="https://mapas-gis-inter.carm.es/geoserver/SIT_USU_PLA_URB_CARM/wfs?",
    typename="SIT_USU_PLA_URB_CARM:clases_plu_ze_37mun",
    encuadre_factor=4
):
    """
    Procesa consulta de urbanismo: parsea GeoJSON, descarga WFS, calcula intersecciones,
    genera mapa con ortofoto y urbanismo.
    
    Retorna diccionario con resultados e imágenes.
    """
    try:
        # Cargar parcela desde GeoJSON
        gdf_parcela = geojson_a_gdf(geojson_content)
        
        # Calcular BBOX con encuadre
        bounds = gdf_parcela.total_bounds  # minx, miny, maxx, maxy en 25830
        
        # Convertir a 4326 para calcular encuadre
        from pyproj import Transformer
        transformer_to_4326 = Transformer.from_epsg(25830, 4326)
        transformer_to_3857 = Transformer.from_epsg(25830, 3857)
        
        # Aplicar factor de encuadre en 25830
        minx, miny, maxx, maxy = bounds
        ancho = maxx - minx
        alto = maxy - miny
        minx -= (encuadre_factor - 1) * ancho / 2
        maxx += (encuadre_factor - 1) * ancho / 2
        miny -= (encuadre_factor - 1) * alto / 2
        maxy += (encuadre_factor - 1) * alto / 2
        
        # Convertir a 3857 para WMS
        lat_min, lon_min = transformer_to_4326.transform(miny, minx)
        lat_max, lon_max = transformer_to_4326.transform(maxy, maxx)
        bbox_3857 = bbox_4326_a_3857((lon_min, lat_min, lon_max, lat_max))
        
        resultados = {
            "referencia": referencia_catastral,
            "porcentajes": {},
            "area_total_m2": 0,
            "imagenes": {}
        }
        
        # Descargar capa WFS de planeamiento
        try:
            gdf_planeamiento = descargar_capa_wfs(base_url_wfs, typename)
            resumen, total_area = calcular_porcentajes_planeamiento(gdf_parcela, gdf_planeamiento)
            
            resultados["porcentajes"] = resumen
            resultados["area_total_m2"] = total_area
        except Exception as e:
            resultados["porcentajes_error"] = str(e)
        
        # Descargar mapas WMS
        try:
            ortofoto_bytes = descargar_ortofoto_wms(bbox_3857)
            resultados["imagenes"]["ortofoto"] = ortofoto_bytes
        except Exception as e:
            resultados["ortofoto_error"] = str(e)
        
        try:
            urbanismo_bytes = descargar_urbanismo_wms(bbox_3857)
            resultados["imagenes"]["urbanismo"] = urbanismo_bytes
        except Exception as e:
            resultados["urbanismo_error"] = str(e)
        
        try:
            leyenda_bytes = descargar_leyenda_urbanismo()
            resultados["imagenes"]["leyenda"] = leyenda_bytes
        except Exception as e:
            resultados["leyenda_error"] = str(e)
        
        # Generar mapa compuesto
        try:
            ortofoto = resultados["imagenes"].get("ortofoto")
            urbanismo = resultados["imagenes"].get("urbanismo")
            leyenda = resultados["imagenes"].get("leyenda")
            
            if ortofoto:
                mapa_bytes = generar_mapa_urbanismo(
                    gdf_parcela,
                    bbox_3857,
                    ortofoto,
                    urbanismo,
                    leyenda,
                    titulo=f"Planeamiento Urbano - {referencia_catastral}"
                )
                resultados["imagenes"]["mapa_compuesto"] = mapa_bytes
        except Exception as e:
            resultados["mapa_error"] = str(e)
        
        return resultados
        
    except Exception as e:
        return {
            "referencia": referencia_catastral,
            "error": str(e),
            "porcentajes": {},
            "imagenes": {}
        }
