from datetime import datetime, timezone
from functools import wraps
import os
import sqlite3
import time

from flask import Flask, g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from telemetry import init_telemetry, telemetry

app = Flask(__name__)
DB_PATH = os.getenv("DB_PATH", "tareas.db")

APP_USER = os.getenv("APP_USER") or os.getenv("O2_USER", "admin@uteq.edu.mx")
APP_PASS = os.getenv("APP_PASS") or os.getenv("O2_PASS", "ObsAdmin#2026")
SECRET_KEY = os.getenv("APP_SECRET_KEY", "parcial2-devop-secret-key-2026")

serializer = URLSafeTimedSerializer(SECRET_KEY)

init_telemetry(app)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tareas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            descripcion TEXT DEFAULT '',
            completada INTEGER DEFAULT 0
        )
        """
    )
    conn.commit()
    conn.close()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "No autorizado"}), 401
        token = auth_header.split(" ", 1)[1].strip()
        try:
            payload = serializer.loads(token, max_age=86400)
            g.current_user = payload.get("email")
        except (BadSignature, SignatureExpired):
            return jsonify({"error": "Token inválido o expirado"}), 401
        return fn(*args, **kwargs)

    return wrapper


init_db()


# ==========================================
# MIDDLEWARE DE LOGGING Y MÉTRICAS OTLP
# ==========================================

@app.before_request
def start_timer():
    g.start_time = time.perf_counter()


@app.after_request
def log_and_record_metrics(response):
    elapsed_ms = round((time.perf_counter() - getattr(g, "start_time", time.perf_counter())) * 1000, 2)
    route_label = str(request.url_rule) if request.url_rule else request.path
    timestamp_iso = datetime.now(timezone.utc).isoformat()

    attrs = {
        "endpoint": route_label,
        "tipo": request.method,
        "statusCode": response.status_code,
    }

    if telemetry.request_counter:
        telemetry.request_counter.add(1, attrs)
    if telemetry.duration_histogram:
        telemetry.duration_histogram.record(elapsed_ms, attrs)
    if telemetry.error_counter and response.status_code >= 400:
        telemetry.error_counter.add(1, attrs)

    log_data = {
        "tiempo_respuesta_ms": elapsed_ms,
        "endpoint": request.path,
        "tipo": request.method,
        "statusCode": response.status_code,
        "timestamp": timestamp_iso,
    }

    level = "warning" if 400 <= response.status_code < 500 else ("error" if response.status_code >= 500 else "info")
    getattr(telemetry.logger, level)(
        f"{request.method} {request.path} -> {response.status_code} ({elapsed_ms} ms)",
        extra=log_data,
    )
    return response


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    telemetry.logger.exception(
        f"Excepción no controlada en {request.method} {request.path}: {error}",
        extra={
            "endpoint": request.path,
            "tipo": request.method,
            "statusCode": 500,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    return jsonify({"error": "Error interno del servidor"}), 500


# ==========================================
# ENDPOINTS PÚBLICOS Y AUTENTICACIÓN
# ==========================================

@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "service": "api-tareas-parcial2"}), 200


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Debes enviar correo y contraseña"}), 400

    email = str(data.get("email", "")).strip()
    password = str(data.get("password", ""))

    if not email or not password:
        return jsonify({"error": "Completa correo y contraseña"}), 400

    if email != APP_USER or password != APP_PASS:
        return jsonify({"error": "Credenciales incorrectas"}), 401

    token = serializer.dumps({"email": email})
    return jsonify({"token": token, "user": {"email": email}}), 200


@app.route("/api/me", methods=["GET"])
@require_auth
def get_me():
    return jsonify({"user": {"email": g.current_user}}), 200


@app.route("/api/logout", methods=["POST"])
@require_auth
def logout():
    return jsonify({"message": "Sesión cerrada correctamente"}), 200


# ==========================================
# ENDPOINTS PROTEGIDOS DE TAREAS
# ==========================================

@app.route("/api/tareas", methods=["GET"])
@require_auth
def get_tareas():
    conn = get_db()
    rows = conn.execute("SELECT * FROM tareas ORDER BY id DESC").fetchall()
    conn.close()
    tareas = [
        {
            "id": r["id"],
            "titulo": r["titulo"],
            "descripcion": r["descripcion"],
            "completada": bool(r["completada"]),
        }
        for r in rows
    ]
    return jsonify({"data": tareas}), 200


@app.route("/api/tareas/<int:tarea_id>", methods=["GET"])
@require_auth
def get_tarea(tarea_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM tareas WHERE id = ?", (tarea_id,)).fetchone()
    conn.close()
    if row is None:
        return jsonify({"error": "Tarea no encontrada"}), 404
    return jsonify({
        "data": {
            "id": row["id"],
            "titulo": row["titulo"],
            "descripcion": row["descripcion"],
            "completada": bool(row["completada"]),
        }
    }), 200


@app.route("/api/tareas", methods=["POST"])
@require_auth
def create_tarea():
    data = request.get_json(silent=True)
    if not data or not str(data.get("titulo", "")).strip():
        return jsonify({"error": "El título es obligatorio"}), 400

    titulo = str(data["titulo"]).strip()
    descripcion = str(data.get("descripcion", "")).strip()
    completada = 1 if data.get("completada", False) else 0

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tareas (titulo, descripcion, completada) VALUES (?, ?, ?)",
        (titulo, descripcion, completada),
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()

    return jsonify({
        "data": {
            "id": new_id,
            "titulo": titulo,
            "descripcion": descripcion,
            "completada": bool(completada),
        }
    }), 201


@app.route("/api/tareas/<int:tarea_id>", methods=["PUT"])
@require_auth
def update_tarea(tarea_id):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Datos inválidos"}), 400

    conn = get_db()
    row = conn.execute("SELECT * FROM tareas WHERE id = ?", (tarea_id,)).fetchone()
    if row is None:
        conn.close()
        return jsonify({"error": "Tarea no encontrada"}), 404

    nuevo_titulo = str(data.get("titulo", row["titulo"])).strip()
    if not nuevo_titulo:
        conn.close()
        return jsonify({"error": "El título no puede estar vacío"}), 400

    nueva_desc = str(data.get("descripcion", row["descripcion"])).strip()
    nueva_comp = 1 if data.get("completada", bool(row["completada"])) else 0

    conn.execute(
        "UPDATE tareas SET titulo = ?, descripcion = ?, completada = ? WHERE id = ?",
        (nuevo_titulo, nueva_desc, nueva_comp, tarea_id),
    )
    conn.commit()
    conn.close()

    return jsonify({
        "data": {
            "id": tarea_id,
            "titulo": nuevo_titulo,
            "descripcion": nueva_desc,
            "completada": bool(nueva_comp),
        }
    }), 200


@app.route("/api/tareas/<int:tarea_id>", methods=["DELETE"])
@require_auth
def delete_tarea(tarea_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM tareas WHERE id = ?", (tarea_id,)).fetchone()
    if row is None:
        conn.close()
        return jsonify({"error": "Tarea no encontrada"}), 404

    conn.execute("DELETE FROM tareas WHERE id = ?", (tarea_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Tarea eliminada correctamente"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)