# DEVELOPER GUIDE - CATASTRO SAAS

## Índice
1. [Estructura del Proyecto](#estructura-del-proyecto)
2. [Stack Tecnológico](#stack-tecnológico)
3. [Configuración del Entorno](#configuración-del-entorno)
4. [Desarrollo Local](#desarrollo-local)
5. [Arquitectura](#arquitectura)
6. [Flujos de Trabajo](#flujos-de-trabajo)
7. [Testing](#testing)
8. [Debugging](#debugging)
9. [Contribución](#contribución)

---

## Estructura del Proyecto

```
CatastroSaaS/
├── app.py                      # Punto de entrada FastAPI
├── config.py                   # Configuración centralizada
├── database.py                 # Conexión y setup de BD
├── models.py                   # SQLAlchemy ORM models
├── schemas.py                  # Pydantic validation schemas
├── requirements.txt            # Dependencias Python
├── docker-compose.yml          # Orquestación de contenedores
├── Dockerfile                  # Imagen Docker
│
├── auth/                       # Módulo de autenticación
│   ├── __init__.py
│   ├── dependencies.py         # JWT dependencies
│   ├── jwt.py                  # Token generation/validation
│   └── utils.py                # Password hashing, etc.
│
├── routers/                    # Endpoints API
│   ├── __init__.py
│   ├── auth.py                 # Auth endpoints (register/login)
│   ├── catastro.py             # Cadastral/WMS endpoints
│   └── subscriptions.py        # Payment/subscription endpoints
│
├── services/                   # Business logic
│   ├── __init__.py
│   ├── stripe_service.py       # Stripe integration
│   └── wms_service.py          # Geospatial processing (NUEVO)
│
├── static/                     # Frontend assets
│   ├── dashboard.html          # SaaS dashboard (MEJORADO)
│   ├── login.html
│   ├── register.html
│   ├── terms.html              # Legal page (NUEVO)
│   ├── privacy.html            # Legal page (NUEVO)
│   ├── contact.html            # Legal page (NUEVO)
│   ├── query.html              # Query detail page (NUEVO)
│   ├── css/
│   │   ├── main.css
│   │   └── data-selector.css
│   └── js/
│       └── auth.js
│
├── templates/                  # Jinja2 templates
│   └── pages/
│       └── landing.html
│
├── .env                        # Secrets & config (NUEVO)
├── README.md
├── QUICKSTART.md
├── TEST_REPORT.md              # Reporte de pruebas (NUEVO)
├── DEPLOYMENT.md               # Guía de deployment (NUEVO)
└── API_REFERENCE.md            # Documentación API (NUEVO)
```

---

## Stack Tecnológico

### Backend
- **FastAPI 0.115.6** - Framework web asincrónico
- **Uvicorn 0.32.0** - ASGI server
- **SQLAlchemy 2.0.36** - ORM
- **Pydantic** - Data validation
- **PyJWT** - Token generation

### Base de Datos
- **SQLite** (desarrollo)
- **PostgreSQL** (producción)

### Geospatial
- **Shapely 2.0.2** - Geometría vectorial
- **Matplotlib 3.8.4** - Visualización de mapas
- **Pillow 10.1.0** - Procesamiento de imágenes
- **Numpy 1.26.4** - Operaciones numéricas

### PDF & Export
- **ReportLab 4.0.0** - Generación de PDFs profesionales
- **Platypus** - Layout engine para PDFs

### Frontend
- **HTML5** - Markup
- **CSS3** - Styling
- **Vanilla JavaScript** - Interactividad
- **Bootstrap** (opcional) - UI framework

### DevOps
- **Docker & Docker Compose** - Containerización
- **Git** - Version control
- **Nginx** - Reverse proxy (producción)

---

## Configuración del Entorno

### Requisitos
- Python 3.9+
- pip o poetry
- PostgreSQL (opcional, para producción)
- Git

### Instalación Inicial

```bash
# 1. Clonar repositorio
git clone <repository-url>
cd CatastroSaaS

# 2. Crear entorno virtual
python -m venv venv

# 3. Activar entorno
# Windows:
.\venv\Scripts\Activate.ps1
# Linux/Mac:
source venv/bin/activate

# 4. Instalar dependencias
pip install -r requirements.txt

# 5. Crear archivo .env
cp .env.example .env
# Editar .env con valores locales

# 6. Inicializar base de datos
python -c "from database import Base, engine; Base.metadata.create_all(bind=engine)"
```

### Variables de Entorno (.env)

```env
# Database
DATABASE_URL=sqlite:///./test.db

# Security
SECRET_KEY=dev-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Stripe (opcional)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...

# AEMET (opcional)
AEMET_API_KEY=your-key

# App
APP_NAME=CatastroSaaS
APP_VERSION=1.0.0
DEBUG=True
```

---

## Desarrollo Local

### Iniciar Servidor

```bash
# Modo normal
python -m uvicorn app:app --host 0.0.0.0 --port 8001

# Modo desarrollo (con auto-reload)
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8001

# Con logs detallados
python -m uvicorn app:app --reload --log-level debug
```

### Acceder a la Aplicación
- Frontend: http://localhost:8001
- API docs (Swagger): http://localhost:8001/docs
- API docs (ReDoc): http://localhost:8001/redoc

### Con Docker

```bash
# Construir imagen
docker build -t catastro-saas:dev .

# Ejecutar contenedor
docker run -d \
  -p 8001:8001 \
  --env-file .env \
  --name catastro-dev \
  catastro-saas:dev

# Con docker-compose
docker-compose up -d

# Ver logs
docker-compose logs -f app
```

---

## Arquitectura

### Patrones de Diseño

#### 1. **Service Layer Pattern**
Toda lógica de negocio en `services/`:
```python
# services/wms_service.py
def procesar_consulta_catastral(kml_content, referencia):
    # 1. Parse KML
    polygons = parse_kml_polygons(kml_content)
    
    # 2. Validate geometry
    geometry = polygons_to_shapely(polygons)
    
    # 3. Calculate bounds
    bbox = get_bbox_from_polygons(polygons)
    
    # 4. Download WMS maps
    ortho_image = download_wms_image(...)
    theme_image = download_wms_image(...)
    
    # 5. Compute affection
    affection_pct = calcular_porcentaje_pixeles(...)
    
    return {"affection_data": ..., "maps": ...}
```

#### 2. **Router/Endpoint Pattern**
Endpoints ligeros que orquestan services:
```python
# routers/catastro.py
@router.post("/query")
async def create_query(
    query: QueryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. Validate subscription
    check_quota(current_user)
    
    # 2. Call service
    result = catastro_service.process(query.referencia_catastral)
    
    # 3. Save to DB
    db_query = Query(user_id=current_user.id, ...)
    db.add(db_query)
    db.commit()
    
    # 4. Return response
    return QueryResponse.from_orm(db_query)
```

#### 3. **Dependency Injection**
FastAPI dependencies para auth, DB, config:
```python
# auth/dependencies.py
async def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    username = payload.get("sub")
    user = db.query(User).filter(User.email == username).first()
    return user

# Uso en endpoints
@router.get("/profile")
async def get_profile(current_user: User = Depends(get_current_user)):
    return current_user
```

### Flujo de Datos

```
Cliente (HTML/JS)
    ↓ HTTP Request
FastAPI Router (catastro.py)
    ↓ Call Service
WMS Service (wms_service.py)
    ├─→ Parse KML (services/wms_service.py)
    ├─→ Shapely Geometry (services/wms_service.py)
    ├─→ Download WMS (services/wms_service.py)
    └─→ Calculate Affection (services/wms_service.py)
    ↓ Return Results
Database (SQLAlchemy)
    ├─→ Query Model (models.py)
    └─→ User Model (models.py)
    ↓ Prepare Response
Pydantic Schema (schemas.py)
    ├─→ QueryResponse
    └─→ Validation
    ↓ HTTP Response (JSON/ZIP/PDF)
Cliente
```

---

## Flujos de Trabajo

### Crear Nueva Funcionalidad

#### 1. Definir Modelo
```python
# models.py
class NewFeature(Base):
    __tablename__ = "new_features"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"))
    data = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
```

#### 2. Crear Schema
```python
# schemas.py
class NewFeatureCreate(BaseModel):
    data: str

class NewFeatureResponse(BaseModel):
    id: int
    data: str
    created_at: datetime
    
    class Config:
        from_attributes = True
```

#### 3. Implementar Service
```python
# services/new_service.py
def process_feature(data: str):
    # Business logic
    return {"result": ...}
```

#### 4. Crear Endpoint
```python
# routers/new.py
@router.post("/features")
async def create_feature(
    feature: NewFeatureCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = new_service.process_feature(feature.data)
    db_feature = NewFeature(user_id=current_user.id, data=feature.data)
    db.add(db_feature)
    db.commit()
    return NewFeatureResponse.from_orm(db_feature)
```

#### 5. Incluir Router
```python
# app.py
from routers import new
app.include_router(new.router, prefix="/api")
```

---

## Testing

### Tests Unitarios

```python
# test_wms_service.py
import pytest
from services.wms_service import parse_kml_polygons

@pytest.fixture
def sample_kml():
    return """<?xml version="1.0"?>
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
    </kml>"""

def test_parse_kml_polygons(sample_kml):
    polygons = parse_kml_polygons(sample_kml)
    assert len(polygons) == 1
    assert len(polygons[0]["exterior"]) == 5
```

### Tests de Integración

```python
# test_api.py
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_create_query():
    response = client.post(
        "/api/catastro/query",
        json={"referencia_catastral": "28001A001001700000TN"},
        headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 201
    assert response.json()["referencia_catastral"] == "28001A001001700000TN"

def test_list_queries():
    response = client.get(
        "/api/catastro/queries",
        headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 200
```

### Ejecutar Tests

```bash
# Todos los tests
pytest

# Con cobertura
pytest --cov=. --cov-report=html

# Test específico
pytest test_wms_service.py::test_parse_kml_polygons -v

# Con output detallado
pytest -vv --tb=short
```

---

## Debugging

### Logs en Desarrollo

```python
# Usar logging en lugar de print()
import logging

logger = logging.getLogger(__name__)

# En tu código
logger.debug("Debug info")
logger.info("Info importante")
logger.warning("Advertencia")
logger.error("Error ocurrido", exc_info=True)
```

### Debugger de Python

```bash
# Instalar debugger
pip install debugpy

# Ejecutar con debugger
python -m debugpy --listen 5678 -m uvicorn app:app --reload
```

### VS Code Debugging

Crear `.vscode/launch.json`:
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["app:app", "--reload"],
      "jinja": true,
      "justMyCode": true
    }
  ]
}
```

### Inspeccionar Base de Datos

```bash
# SQLite (desarrollo)
sqlite3 test.db

# Ver tablas
.tables

# Ver estructura
.schema query

# Ejecutar query
SELECT * FROM query LIMIT 5;
```

---

## Contribución

### Workflow Git

```bash
# 1. Crear rama feature
git checkout -b feature/nueva-funcionalidad

# 2. Hacer cambios
# ... editar archivos ...

# 3. Commit
git add .
git commit -m "feat: agregar nueva funcionalidad"

# 4. Push
git push origin feature/nueva-funcionalidad

# 5. Pull Request en GitHub

# 6. Merge a main
git checkout main
git merge feature/nueva-funcionalidad
git push origin main
```

### Convenciones de Commits

```
feat: Agregar nueva funcionalidad
fix: Corregir bug
docs: Actualizar documentación
style: Cambios de formato (sin cambio lógico)
refactor: Refactorización sin cambio de funcionalidad
test: Agregar o actualizar tests
chore: Tareas de mantenimiento
```

### Code Style

```bash
# Instalar formateadores
pip install black flake8 isort

# Formatear código
black .

# Verificar estilo
flake8 .

# Ordenar imports
isort .
```

### Pre-commit Hooks

```bash
# Instalar pre-commit
pip install pre-commit

# Crear .pre-commit-config.yaml
cat > .pre-commit-config.yaml << EOF
repos:
  - repo: https://github.com/psf/black
    rev: 23.7.0
    hooks:
      - id: black
  - repo: https://github.com/PyCQA/isort
    rev: 5.12.0
    hooks:
      - id: isort
  - repo: https://github.com/PyCQA/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
EOF

# Instalar hooks
pre-commit install

# Ejecutar manualmente
pre-commit run --all-files
```

---

## Recursos Adicionales

- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [SQLAlchemy Docs](https://docs.sqlalchemy.org/)
- [Pydantic Docs](https://docs.pydantic.dev/)
- [Shapely Docs](https://shapely.readthedocs.io/)
- [ReportLab Docs](https://www.reportlab.com/docs/reportlab-userguide.pdf)

---

**Versión:** 1.0.0  
**Última actualización:** 10/12/2025  
**Mantenedor:** [Tu Nombre]
