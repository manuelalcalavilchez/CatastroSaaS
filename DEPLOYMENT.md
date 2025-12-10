# GUÍA DE DEPLOYMENT - CATASTRO SAAS

## 1. REQUISITOS PREVIOS

- Python 3.9+
- PostgreSQL (para producción) o SQLite (desarrollo)
- Pip o conda para gestión de paquetes
- Git para control de versiones
- Docker (opcional, recomendado)

## 2. INSTALACIÓN LOCAL

### 2.1 Clonar repositorio
```powershell
git clone <repository-url>
cd CatastroSaaS
```

### 2.2 Crear entorno virtual
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows PowerShell
# o: source venv/bin/activate  # Linux/Mac
```

### 2.3 Instalar dependencias
```powershell
pip install -r requirements.txt
```

### 2.4 Configurar variables de entorno
Crear archivo `.env` en la raíz del proyecto:

```env
# Base de datos
DATABASE_URL=sqlite:///./test.db  # Cambiar a PostgreSQL en producción

# JWT y seguridad
SECRET_KEY=your-super-secret-key-change-this-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Stripe (si aplica)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# AEMET API (datos climáticos)
AEMET_API_KEY=your-aemet-key

# Configuración de la aplicación
APP_NAME=CatastroSaaS
APP_VERSION=1.0.0
DEBUG=False  # True en desarrollo, False en producción

# URLs
APP_HOST=0.0.0.0
APP_PORT=8001
FRONTEND_URL=http://localhost:3000

# Planes de suscripción
FREE_PLAN_QUERIES=10
PRO_PLAN_QUERIES=100
ENTERPRISE_PLAN_QUERIES=1000
```

### 2.5 Inicializar base de datos
```powershell
python -c "from database import Base, engine; Base.metadata.create_all(bind=engine)"
```

### 2.6 Iniciar servidor de desarrollo
```powershell
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8001
```

La API estará disponible en: `http://localhost:8001`
- Swagger UI: `http://localhost:8001/docs`
- ReDoc: `http://localhost:8001/redoc`

## 3. DEPLOYMENT CON DOCKER

### 3.1 Construir imagen
```powershell
docker build -t catastro-saas:latest .
```

### 3.2 Ejecutar contenedor
```powershell
docker run -d `
  -p 8001:8001 `
  --env-file .env `
  --name catastro-saas `
  catastro-saas:latest
```

### 3.3 Con docker-compose
```powershell
docker-compose up -d
```

## 4. DEPLOYMENT EN PRODUCCIÓN

### 4.1 Preparar servidor (Linux/Ubuntu)

```bash
# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar Python y dependencias
sudo apt install -y python3.10 python3-pip python3-venv postgresql postgresql-contrib nginx

# Crear usuario para la aplicación
sudo useradd -m -s /bin/bash catastro

# Clonar repositorio
sudo -u catastro git clone <repository-url> /home/catastro/app
cd /home/catastro/app

# Crear entorno virtual
sudo -u catastro python3 -m venv venv
sudo -u catastro source venv/bin/activate
sudo -u catastro pip install -r requirements.txt
```

### 4.2 Configurar PostgreSQL
```bash
sudo -u postgres createdb catastro_db
sudo -u postgres createuser catastro_user
sudo -u postgres psql -c "ALTER USER catastro_user WITH PASSWORD 'secure-password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE catastro_db TO catastro_user;"
```

### 4.3 Crear servicio systemd
Crear archivo `/etc/systemd/system/catastro.service`:

```ini
[Unit]
Description=CatastroSaaS FastAPI Application
After=network.target

[Service]
Type=notify
User=catastro
WorkingDirectory=/home/catastro/app
ExecStart=/home/catastro/app/venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8001
Restart=on-failure
Environment="PATH=/home/catastro/app/venv/bin"

[Install]
WantedBy=multi-user.target
```

Activar servicio:
```bash
sudo systemctl enable catastro
sudo systemctl start catastro
sudo systemctl status catastro
```

### 4.4 Configurar Nginx como reverse proxy
Crear `/etc/nginx/sites-available/catastro`:

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    client_max_body_size 50M;
    
    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSockets (si aplica)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    # Cache estático
    location /static/ {
        alias /home/catastro/app/static/;
        expires 30d;
    }
}
```

Activar sitio:
```bash
sudo ln -s /etc/nginx/sites-available/catastro /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 4.5 SSL con Let's Encrypt
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## 5. MONITORING Y LOGS

### Ver logs del servicio
```bash
sudo journalctl -u catastro -f
```

### Logs de Nginx
```bash
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Verificar salud de la aplicación
```bash
curl https://your-domain.com/health
```

## 6. MANTENIMIENTO

### 6.1 Actualizar código
```bash
cd /home/catastro/app
sudo -u catastro git pull origin main
sudo -u catastro source venv/bin/activate
sudo -u catastro pip install -r requirements.txt
sudo systemctl restart catastro
```

### 6.2 Backup de base de datos
```bash
pg_dump -U catastro_user catastro_db > catastro_db_backup_$(date +%Y%m%d).sql
```

### 6.3 Restaurar base de datos
```bash
psql -U catastro_user catastro_db < catastro_db_backup_20231210.sql
```

## 7. VARIABLES DE ENTORNO POR AMBIENTE

### Desarrollo
```env
DEBUG=True
DATABASE_URL=sqlite:///./test.db
SECRET_KEY=dev-key-not-secure
CORS_ORIGINS=["http://localhost:3000", "http://localhost:8001"]
```

### Staging
```env
DEBUG=False
DATABASE_URL=postgresql://user:password@staging-db:5432/catastro
SECRET_KEY=staging-secret-key-change-this
CORS_ORIGINS=["https://staging.your-domain.com"]
```

### Producción
```env
DEBUG=False
DATABASE_URL=postgresql://user:password@prod-db:5432/catastro
SECRET_KEY=prod-secret-key-very-secure
CORS_ORIGINS=["https://your-domain.com"]
```

## 8. PRUEBAS ANTES DE DEPLOYMENT

```powershell
# Health check
curl http://localhost:8001/health

# Swagger UI disponible
curl http://localhost:8001/docs

# Test de endpoints críticos
curl -X POST http://localhost:8001/api/catastro/query `
  -H "Content-Type: application/json" `
  -d '{"referencia_catastral": "test123"}'
```

## 9. TROUBLESHOOTING

### Problema: ModuleNotFoundError
**Solución:** Verificar que el entorno virtual está activado
```powershell
pip list  # Debe mostrar paquetes instalados
```

### Problema: Puerto 8001 en uso
**Solución:** Cambiar puerto o matar proceso
```powershell
# Cambiar puerto
python -m uvicorn app:app --port 8002

# O matar proceso existente
Get-Process | Where-Object {$_.Name -eq "python"} | Stop-Process
```

### Problema: Error de base de datos
**Solución:** Verificar DATABASE_URL en .env y credenciales de PostgreSQL

### Problema: 403 en descargas de WMS
**Solución:** Verificar conexión a Internet y firewall

## 10. INFORMACIÓN DE SOPORTE

- **Documentación API:** http://localhost:8001/docs
- **Issue Tracker:** [GitHub Issues](link-to-repo)
- **Email Support:** support@your-domain.com

---

**Versión:** 1.0.0  
**Última actualización:** 10/12/2025
