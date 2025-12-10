# Implementación Completada: Análisis Catastral Integral con WMS

## Cambios Realizados

### 1. **Nuevo módulo de servicios geoespaciales** (`services/wms_service.py`)
- Parseo de KML con soporte para geometrías complejas (polígonos con huecos)
- Descarga de mapas WMS desde MAPAMA e IGN
- Cálculo de porcentajes de afección por píxeles (inteligencia espacial)
- Generación de imágenes compuestas (ortofoto + capas temáticas + contorno de parcela)
- Soporte para 3 capas: Montes Públicos, Red Natura 2000, Vías Pecuarias

### 2. **Modelos actualizados** (`models.py`)
- Campos nuevos en `Query`:
  - `has_wms_maps`: Boolean que indica si se descargaron mapas WMS
  - `kml_content`: Contenido KML de la parcela (string)
  - `wms_affection_data`: JSON con resultados de afección por umbral

### 3. **PDF mejorado** (`routers/catastro.py`)
- PDF con portada, tabla de resumen, metadatos y secciones descriptivas
- Incluye sección de análisis de afección si disponible
- Soporte para encabezado, pie de página y numeración

### 4. **ZIP enriquecido**
- `report.pdf`: Informe completo con tablas y datos de afección
- `metadata.json`: Información estructurada de la consulta
- `affection_data.json`: Porcentajes de afección por capa WMS
- `geometry.kml`: Geometría original de la parcela
- `README.txt`: Descripción del contenido
- Archivos placeholder para datos temáticos (AEMET, INE)

### 5. **Nuevos endpoints**
- `POST /api/catastro/query/{query_id}/process-wms`: Procesa una consulta existente con análisis WMS
  - Input: Query ID (ya debe contener KML)
  - Output: Descarga mapas, calcula afecciones, actualiza query

### 6. **Esquemas actualizados** (`schemas.py`)
- `QueryCreate` acepta `kml_content` opcional
- `QueryResponse` incluye `has_wms_maps`

### 7. **Dependencias añadidas** (`requirements.txt`)
```
shapely==2.0.2
matplotlib==3.8.4
pillow==10.1.0
numpy==1.26.4
```

---

## Cómo Usar (Local)

### Instalación de dependencias
```powershell
pip install -r requirements.txt
```

### Iniciar la aplicación
```powershell
python -m uvicorn app:app --host 0.0.0.0 --port 8001 --reload
```

### Flujo de uso típico

#### 1. Crear una consulta con KML
```powershell
# Crear consulta con contenido KML (base64 o string XML)
curl -X POST -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "referencia_catastral": "30037A008002060000UZ",
    "kml_content": "<kml>...</kml>"
  }' \
  http://localhost:8001/api/catastro/query
```

#### 2. Procesar con análisis WMS
```powershell
# Descargar mapas, calcular afecciones
curl -X POST -H "Authorization: Bearer <TOKEN>" \
  http://localhost:8001/api/catastro/query/{QUERY_ID}/process-wms
```

#### 3. Descargar ZIP con resultados
```powershell
curl -H "Authorization: Bearer <TOKEN>" \
  -o results.zip \
  http://localhost:8001/api/catastro/queries/{QUERY_ID}/download
```

---

## Contenido del ZIP Generado

Para cada consulta procesada, el ZIP contiene:

```
catastro_query_30037A008002060000UZ_<timestamp>.zip
└── 30037A008002060000UZ_<query_id>/
    ├── report.pdf                 # Informe con tablas y análisis
    ├── metadata.json              # Metadatos estructurados
    ├── affection_data.json        # Porcentajes de afección por umbral
    ├── geometry.kml               # Geometría de la parcela
    ├── AEMET_climate_data.txt     # Placeholder datos climáticos
    ├── INE_socioeconomic_data.txt # Placeholder datos socioeconómicos
    └── README.txt                 # Descripción del contenido
```

---

## Análisis de Afección

El sistema calcula automáticamente el porcentaje de la parcela que está afectado por cada capa temática:

**Capas procesadas:**
1. **Montes Públicos** (MAPAMA)
2. **Red Natura 2000** (MAPAMA)
3. **Vías Pecuarias** (MAPAMA)

**Umbrales de píxeles:** 250, 200, 150 (valores de píxel que indican afección)

**Ejemplo de salida:**
```json
{
  "MontesPublicos": {
    "umbral_250": 45.23,
    "umbral_200": 52.10,
    "umbral_150": 58.75
  },
  "RedNatura2000": {
    "umbral_250": 12.50,
    "umbral_200": 15.20,
    "umbral_150": 18.90
  },
  "ViasPecuarias": {
    "umbral_250": 8.33,
    "umbral_200": 10.15,
    "umbral_150": 12.40
  }
}
```

---

## Mapas Generados

Cada capa temática genera una imagen PNG que combina:
- **Fondo:** Ortofoto del IGN (PNOA)
- **Capa:** Montes Públicos / Red Natura 2000 / Vías Pecuarias
- **Contorno:** Polígono de la parcela en rojo
- **Leyenda:** Oficial de la fuente (si está disponible)

Las imágenes se incluyen en el PDF del informe.

---

## Próximas Mejoras Opcionales

1. **Almacenamiento persistente:** Guardar ZIPs en disco/S3 y devolver URLs con expiración
2. **Procesamiento asíncrono:** Usar Celery para procesar múltiples consultas en background
3. **Más capas WMS:** Afecciones ambientales, hidrografía, red natura ampliada
4. **Descarga de mapas individuales:** Endpoint para descargar imágenes WMS por separado
5. **Integración con IGN:** Acceso a más servicios de mapas
6. **Generación de reportes personalizados:** Templates personalizables por usuario/plan

---

## Notas Técnicas

- Los mapas WMS se descargan bajo demanda; no se cachean
- El cálculo de afección es CPU-intensivo para parcelas grandes; se recomienda implementar queue/worker
- ReportLab genera PDFs sin dependencias externas (optimizado para servidor)
- Shapely maneja geometrías complejas (polígonos con agujeros) de forma robusta

---

Para preguntas o mejoras, consulta la documentación en `/docs` (Swagger).
