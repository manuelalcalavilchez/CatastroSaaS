# API REFERENCE - CATASTRO SAAS

## Base URL
```
http://localhost:8001  # Desarrollo
https://api.your-domain.com  # Producción
```

## Autenticación

Todos los endpoints protegidos requieren un JWT token en el header:

```
Authorization: Bearer <token>
```

## ENDPOINTS

---

### 🏥 HEALTH & INFO

#### GET /health
Health check de la aplicación.

**Response (200):**
```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

---

### 🔐 AUTENTICACIÓN

#### POST /api/auth/register
Registrar nuevo usuario.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "secure-password",
  "full_name": "John Doe"
}
```

**Response (201):**
```json
{
  "id": 1,
  "email": "user@example.com",
  "full_name": "John Doe",
  "is_active": true,
  "created_at": "2025-12-10T10:00:00Z"
}
```

**Errors:**
- `422` - Datos inválidos
- `400` - Email ya registrado

---

#### POST /api/auth/login
Iniciar sesión y obtener token JWT.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "secure-password"
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Errors:**
- `401` - Credenciales inválidas
- `404` - Usuario no encontrado

---

### 📍 CONSULTAS CATASTRALES

#### POST /api/catastro/query
Crear nueva consulta catastral con geometría KML opcional.

**Request Body:**
```json
{
  "referencia_catastral": "28001A001001700000TN",
  "kml_content": "<?xml version=\"1.0\"?><kml>...</kml>"  // Opcional
}
```

**Response (201):**
```json
{
  "id": "query-123",
  "user_id": 1,
  "referencia_catastral": "28001A001001700000TN",
  "has_climate_data": false,
  "has_socioeconomic_data": false,
  "has_pdf": false,
  "has_wms_maps": false,
  "kml_content": null,
  "wms_affection_data": null,
  "created_at": "2025-12-10T10:00:00Z"
}
```

**Errors:**
- `401` - No autenticado
- `422` - Datos inválidos
- `429` - Límite de consultas excedido

---

#### GET /api/catastro/queries
Listar todas las consultas del usuario autenticado.

**Query Parameters:**
- `skip` (int, default=0) - Registros a saltar
- `limit` (int, default=10) - Registros a retornar

**Response (200):**
```json
{
  "total": 25,
  "items": [
    {
      "id": "query-123",
      "referencia_catastral": "28001A001001700000TN",
      "has_climate_data": false,
      "has_wms_maps": true,
      "created_at": "2025-12-10T10:00:00Z"
    }
    // ... más consultas
  ]
}
```

**Errors:**
- `401` - No autenticado

---

#### GET /api/catastro/queries/{query_id}
Obtener detalles completos de una consulta específica.

**Path Parameters:**
- `query_id` (string) - ID de la consulta

**Response (200):**
```json
{
  "id": "query-123",
  "user_id": 1,
  "referencia_catastral": "28001A001001700000TN",
  "has_climate_data": false,
  "has_socioeconomic_data": false,
  "has_pdf": false,
  "has_wms_maps": true,
  "kml_content": "<?xml version=\"1.0\"?>...",
  "wms_affection_data": {
    "montes_publicos": {
      "umbral_0.1": 15.5,
      "umbral_0.3": 8.2
    },
    "red_natura_2000": {
      "umbral_0.1": 0,
      "umbral_0.3": 0
    }
  },
  "created_at": "2025-12-10T10:00:00Z"
}
```

**Errors:**
- `401` - No autenticado
- `404` - Consulta no encontrada
- `403` - No tiene permiso para acceder

---

#### GET /api/catastro/queries/{query_id}/download
Descargar resultados de consulta como ZIP.

**Path Parameters:**
- `query_id` (string) - ID de la consulta

**Response (200):**
- Content-Type: `application/zip`
- Content-Disposition: `attachment; filename="query_<id>.zip"`

**Contenido del ZIP:**
```
query-123/
├── report.pdf              # Informe profesional con ReportLab
├── metadata.json           # Metadatos estruturados
├── geometry.kml            # Geometría original en KML
├── affection_data.json     # Análisis de afección por capas
├── README.txt              # Descripción del contenido
├── AEMET_climate_data.txt  # Datos climáticos (si disponible)
└── INE_socioeconomic_data.txt  # Datos socioeconómicos (si disponible)
```

**Errors:**
- `401` - No autenticado
- `404` - Consulta no encontrada
- `403` - No tiene permiso

---

#### POST /api/catastro/query/{query_id}/process-wms
Procesar consulta existente con análisis WMS (descargar mapas y calcular afecciones).

**Path Parameters:**
- `query_id` (string) - ID de la consulta

**Request Body:**
```json
{
  "wms_layers": ["montes_publicos", "red_natura_2000", "vias_pecuarias"],
  "thresholds": [0.1, 0.3, 0.5]  // Opcional
}
```

**Response (200):**
```json
{
  "status": "processing",
  "message": "WMS analysis iniciado",
  "query_id": "query-123",
  "layers_to_process": 3,
  "estimated_time_seconds": 30
}
```

O si ya está completado:
```json
{
  "status": "completed",
  "query_id": "query-123",
  "wms_affection_data": {
    "montes_publicos": {
      "umbral_0.1": 15.5,
      "umbral_0.3": 8.2,
      "umbral_0.5": 3.1
    }
  },
  "maps_generated": 3,
  "processing_time_seconds": 25
}
```

**Errors:**
- `401` - No autenticado
- `404` - Consulta no encontrada
- `400` - No contiene KML (necesario para WMS)
- `503` - Servicio WMS no disponible

---

#### POST /api/catastro/queries/export
Exportar múltiples consultas como un único ZIP.

**Request Body:**
```json
{
  "query_ids": ["query-123", "query-124", "query-125"]
}
```

**Response (200):**
- Content-Type: `application/zip`
- Contiene carpetas individuales para cada consulta

**Errors:**
- `401` - No autenticado
- `400` - No query_ids proporcionados
- `404` - Una o más consultas no encontradas

---

#### GET /api/catastro/stats
Obtener estadísticas de uso de consultas.

**Response (200):**
```json
{
  "total_queries": 45,
  "queries_this_month": 12,
  "queries_with_wms": 8,
  "plan": "pro",
  "plan_limit": 100,
  "queries_remaining": 55,
  "storage_used_mb": 150.5,
  "storage_limit_mb": 1000
}
```

**Errors:**
- `401` - No autenticado

---

### 💳 SUSCRIPCIONES

#### GET /api/subscriptions/plans
Listar planes disponibles.

**Response (200):**
```json
[
  {
    "id": "free",
    "name": "Free",
    "price_monthly": 0,
    "queries_included": 10,
    "features": ["basic_queries", "dashboard"]
  },
  {
    "id": "pro",
    "name": "Professional",
    "price_monthly": 29.99,
    "queries_included": 100,
    "features": ["basic_queries", "wms_analysis", "export_pdf", "api_access"]
  },
  {
    "id": "enterprise",
    "name": "Enterprise",
    "price_monthly": 199.99,
    "queries_included": 1000,
    "features": ["all"]
  }
]
```

---

#### POST /api/subscriptions/upgrade
Actualizar plan de suscripción.

**Request Body:**
```json
{
  "plan_id": "pro",
  "payment_method": "stripe"  // O "manual" para Enterprise
}
```

**Response (200):**
```json
{
  "subscription_id": "sub-123",
  "user_id": 1,
  "plan_id": "pro",
  "status": "active",
  "current_period_start": "2025-12-10T00:00:00Z",
  "current_period_end": "2026-01-10T00:00:00Z",
  "payment_method": "stripe",
  "amount_paid": 29.99
}
```

**Errors:**
- `401` - No autenticado
- `400` - Plan inválido
- `402` - Pago rechazado

---

## CÓDIGOS DE ERROR

| Código | Descripción |
|--------|-------------|
| `200` | OK - Solicitud exitosa |
| `201` | Created - Recurso creado |
| `204` | No Content - Solicitud exitosa sin contenido |
| `400` | Bad Request - Datos inválidos |
| `401` | Unauthorized - Requiere autenticación |
| `403` | Forbidden - No tiene permisos |
| `404` | Not Found - Recurso no encontrado |
| `422` | Unprocessable Entity - Validación fallida |
| `429` | Too Many Requests - Rate limit excedido |
| `500` | Internal Server Error - Error del servidor |
| `503` | Service Unavailable - Servicio no disponible |

## FORMATOS DE DATOS

### Referencia Catastral
Formato oficial español: `PPCCSZZZZZZZZ`
- `PP` - Provincia (2 dígitos)
- `CC` - Municipio (3 dígitos)
- `S` - Sector (1 dígito)
- `ZZ` - Zona (2 dígitos)
- `ZZZZZ` - Número de parcela (5 dígitos)
- `ZZ` - Dígitos de control (2 dígitos)

Ejemplo: `28001A001001700000TN`

### Formato KML
```xml
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              -3.6,-40.4,0
              -3.67,-40.4,0
              -3.67,-40.43,0
              -3.6,-40.43,0
              -3.6,-40.4,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>
```

### Datos de Afección
```json
{
  "capa": {
    "umbral_X": porcentaje_float,
    "umbral_Y": porcentaje_float
  }
}
```

## RATE LIMITING

- Free Plan: 10 consultas/mes
- Pro Plan: 100 consultas/mes  
- Enterprise: Ilimitado

**Header de respuesta:**
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1702000000
```

## EJEMPLOS DE USO

### cURL

```bash
# Crear consulta
curl -X POST http://localhost:8001/api/catastro/query \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "referencia_catastral": "28001A001001700000TN"
  }'

# Descargar ZIP
curl -X GET http://localhost:8001/api/catastro/queries/query-123/download \
  -H "Authorization: Bearer TOKEN" \
  -o results.zip

# Procesar con WMS
curl -X POST http://localhost:8001/api/catastro/query/query-123/process-wms \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "wms_layers": ["montes_publicos"],
    "thresholds": [0.1, 0.3]
  }'
```

### Python

```python
import requests

BASE_URL = "http://localhost:8001"
TOKEN = "your-jwt-token"

headers = {"Authorization": f"Bearer {TOKEN}"}

# Crear consulta
response = requests.post(
    f"{BASE_URL}/api/catastro/query",
    json={"referencia_catastral": "28001A001001700000TN"},
    headers=headers
)
query = response.json()
print(f"Query creada: {query['id']}")

# Listar consultas
response = requests.get(
    f"{BASE_URL}/api/catastro/queries",
    headers=headers
)
queries = response.json()

# Descargar ZIP
response = requests.get(
    f"{BASE_URL}/api/catastro/queries/{query['id']}/download",
    headers=headers
)
with open("results.zip", "wb") as f:
    f.write(response.content)
```

### JavaScript

```javascript
const BASE_URL = "http://localhost:8001";
const token = localStorage.getItem("access_token");

const headers = {
  "Authorization": `Bearer ${token}`,
  "Content-Type": "application/json"
};

// Crear consulta
async function createQuery(referencia) {
  const response = await fetch(`${BASE_URL}/api/catastro/query`, {
    method: "POST",
    headers,
    body: JSON.stringify({ referencia_catastral: referencia })
  });
  return await response.json();
}

// Descargar ZIP
async function downloadQuery(queryId) {
  const response = await fetch(
    `${BASE_URL}/api/catastro/queries/${queryId}/download`,
    { headers }
  );
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `query_${queryId}.zip`;
  document.body.appendChild(a);
  a.click();
}
```

---

**Versión API:** 1.0.0  
**Última actualización:** 10/12/2025  
**Documentación interactiva:** http://localhost:8001/docs
