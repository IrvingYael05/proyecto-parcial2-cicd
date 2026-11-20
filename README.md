# Proyecto Integrador Parcial 2: Arquitectura CI/CD, 1,000 Pruebas Automatizadas y Observabilidad con OpenObserve

Este repositorio implementa un flujo automatizado de Integración Continua y Despliegue Continuo (CI/CD) mediante **GitHub Actions** hacia una instancia de **AWS EC2**, condicionado a la aprobación de **1,000 pruebas automatizadas** (500 pruebas de Backend con **Pytest** y 500 pruebas End-to-End de Frontend con **Playwright**), e integrado con **OpenTelemetry (OTLP)** y **OpenObserve** para el monitoreo centralizado de la aplicación, del pipeline y de los recursos del servidor.

---

## Enlaces de Producción y Credenciales de Acceso

| Recurso | URL / Valor |
| :--- | :--- |
| **Aplicación Web (AWS EC2)** | `http://3.16.151.74:8090` |
| **Health Check de la API** | `http://3.16.151.74:8090/api/health` |
| **Plataforma OpenObserve** | `http://3.16.151.74:5080` |
| **Usuario (Sistema Web y OpenObserve)** | `admin@uteq.edu.mx` |
| **Contraseña (Sistema Web y OpenObserve)** | `ObsAdmin#2026` |

---

## Arquitectura y Stack Tecnológico

* **Backend:** Python 3.12, **Flask 3.1.0**, **SQLite** y autenticación por tokens firmados (`itsdangerous`).
* **Frontend:** HTML5, CSS3 y JavaScript Vanilla servido por **Nginx 1.27** con proxy inverso hacia `/api/`.
* **Aseguramiento de Calidad (QA):**
  * **500 pruebas de Backend** (`tests/test_backend.py`) con **Pytest** y `pytest-cov` (umbral mínimo exigido: 70%).
  * **500 pruebas E2E de Frontend** (`tests/test_frontend_e2e.py`) con **Playwright (`playwright.sync_api`)**, sesión única por módulo y reporte autoincluido con `pytest-html` y capturas JPEG en Base64.
* **Observabilidad y Telemetría:**
  * **OpenTelemetry (OTLP sobre HTTP)** exportando logs estructurados (`tiempo_respuesta_ms`, `endpoint`, `tipo`, `statusCode`, `timestamp`), métricas (`http_requests_total`, `http_errors_total`, `http_request_duration_ms`) y trazas distribuidas (Flask + SQLite).
  * **OpenObserve** desplegado en el puerto `5080` en una pila independiente (`~/observability`) junto con el agente `ec2-metrics-agent` (`psutil`) para recolectar CPU (%), RAM (%), ancho de banda (kbps) y temperatura estimada (°C) cada 5 segundos.
* **Orquestación CI/CD e Infraestructura:** **GitHub Actions**, **Docker / Docker Compose**, **Docker Hub** y **AWS EC2 (Ubuntu Server)**.

---

## Estructura del Repositorio

```text
proyecto-parcial2-cicd/
├── .github/
│   └── workflows/
│       └── main.yml               # Pipeline CI/CD, trazabilidad O2 y despliegue condicionado
├── backend/
│   ├── app.py                     # API REST con autenticación Bearer, CRUD y middleware de logs
│   ├── telemetry.py               # Configuración de Logs, Métricas y Trazas OTLP
│   ├── requirements.txt           # Dependencias de producción del backend
│   └── Dockerfile
├── frontend/
│   ├── index.html                 # Interfaz con Login y Gestor de Tareas (selectores data-testid)
│   ├── app.js                     # Cliente HTTP con manejo de token y sesión
│   ├── nginx.conf                 # Servidor estático + reverse proxy hacia backend:5000
│   └── Dockerfile
├── tests/
│   ├── conftest.py                # Hook de capturas JPEG Base64 y soporte --headed / CI
│   ├── test_backend.py            # 500 pruebas automatizadas de Backend (Pytest)
│   └── test_frontend_e2e.py       # 500 pruebas E2E de Frontend (Playwright)
├── docker-compose.yml             # Orquestación local y en EC2 (puerto 8090)
├── requirements-test.txt          # Dependencias de QA (Pytest, Coverage, Playwright)
├── .dockerignore
├── .gitignore
└── README.md
```

---

## Ejecución Local (Desarrollo y Pruebas)

### 1. Clonar el repositorio e instalar dependencias

```bash
git clone https://github.com/IrvingYael05/proyecto-parcial2-cicd.git
cd proyecto-parcial2-cicd
pip install -r backend/requirements.txt -r requirements-test.txt
python -m playwright install chromium
```

### 2. Levantar la aplicación con Docker Compose

```bash
docker compose up -d --build
```

La aplicación quedará disponible en `http://localhost:8090`.

### 3. Ejecutar las 500 pruebas de Backend con cobertura

**En PowerShell (Windows):**
```powershell
$env:PYTHONPATH="backend"
python -m pytest tests/test_backend.py --cov=app --cov-report=term-missing --cov-fail-under=70
```

**En Linux / macOS:**
```bash
PYTHONPATH=backend python -m pytest tests/test_backend.py --cov=app --cov-report=term-missing --cov-fail-under=70
```

### 4. Ejecutar las 500 pruebas E2E de Frontend con Playwright

Con la aplicación corriendo en `http://localhost:8090`, ejecuta en modo visual (`--headed`) generando el reporte HTML autoincluido:

```bash
python -m pytest tests/test_frontend_e2e.py --headed --html=reporte_pruebas_parcial2.html --self-contained-html
```

*(Opcional: para una ejecución rápida sin generar capturas en disco, define `CAPTURE_SCREENSHOTS=none` antes de correr el comando; por defecto guarda las 500 evidencias en `screenshots_parcial2/`.)*

---

## Endpoints de la API REST

| Método | Ruta | Autenticación | Descripción |
| :--- | :--- | :---: | :--- |
| `GET` | `/api/health` | Pública | Verifica el estado de salud del servicio. |
| `POST` | `/api/login` | Pública | Valida credenciales y genera un token Bearer firmado. |
| `GET` | `/api/me` | Bearer | Devuelve los datos del usuario autenticado. |
| `POST` | `/api/logout` | Bearer | Registra el cierre de sesión del usuario. |
| `GET` | `/api/tareas` | Bearer | Lista todas las tareas ordenadas de forma descendente. |
| `GET` | `/api/tareas/<id>` | Bearer | Consulta una tarea específica por identificador. |
| `POST` | `/api/tareas` | Bearer | Crea una nueva tarea en SQLite. |
| `PUT` | `/api/tareas/<id>` | Bearer | Actualiza título, descripción o estado de una tarea. |
| `DELETE` | `/api/tareas/<id>` | Bearer | Elimina una tarea existente. |

---

## Pipeline CI/CD y Secretos de GitHub Actions

El workflow `.github/workflows/main.yml` se ejecuta automáticamente en cada `push` o `pull_request` a `main`:

1. **`ci-tests`:** Ejecuta las 500 pruebas de Backend (exigiendo cobertura mínima del 70%), levanta el stack con Docker Compose en el runner, corre las 500 pruebas E2E de Playwright, transmite el resultado (`success` o `failure`, commit, rama y autor) hacia el stream `cicd_events` de OpenObserve vía HTTP/JSON y bloquea el pipeline si cualquier suite falla.
2. **`build-and-deploy`:** Condicionado a la aprobación total de `ci-tests`. Compila y publica en Docker Hub las imágenes `parcial2-backend` y `parcial2-frontend` (`:latest` y `:${{ github.sha }}`), despliega vía SSH en AWS EC2 con `OTEL_ENABLED=true`, valida `/api/health` y reporta el evento `ec2_deploy` en OpenObserve.

### Secretos requeridos en GitHub (`Settings > Secrets and variables > Actions`)

| Secret | Descripción |
| :--- | :--- |
| `DOCKER_USERNAME` | Usuario de Docker Hub |
| `DOCKER_PASSWORD` | Personal Access Token (PAT) de Docker Hub |
| `EC2_HOST` | Dirección IP pública de la instancia AWS EC2 |
| `EC2_USER` | Usuario SSH del servidor (`ubuntu`) |
| `EC2_SSH_KEY` | Contenido completo de la llave privada `.pem` |
| `O2_BASE_URL` | URL base de OpenObserve (`http://3.16.151.74:5080`) |
| `O2_USER` | Correo administrador de OpenObserve (`admin@uteq.edu.mx`) |
| `O2_PASS` | Contraseña de OpenObserve |

---

## Streams y Observabilidad en OpenObserve

| Stream | Tipo | Contenido |
| :--- | :--- | :--- |
| `ec2_metrics` | Logs | CPU (%), RAM (% y MB), ancho de banda (kbps) y temperatura estimada (°C) de la instancia EC2. |
| `api_logs` | Logs | Registros estructurados OTLP por petición (`tiempo_respuesta_ms`, `endpoint`, `tipo`, `statusCode`, `timestamp`). |
| `default` | Traces | Trazas distribuidas OTLP de peticiones HTTP en Flask y consultas ejecutadas en SQLite. |
| `cicd_events` | Logs | Trazabilidad de ejecuciones de pruebas (`ci_test_run`) y despliegues (`ec2_deploy`) desde GitHub Actions. |