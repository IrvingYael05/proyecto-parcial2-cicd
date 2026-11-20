import pytest
import app as app_module

VALID_EMAIL = app_module.APP_USER
VALID_PASS = app_module.APP_PASS

# 60 casos de login inválido (10 -> 400, 50 -> 401)
INVALID_LOGIN_CASES = [
    (None, 400),
    ({}, 400),
    ({"email": "", "password": ""}, 400),
    ({"email": VALID_EMAIL, "password": ""}, 400),
    ({"email": "", "password": VALID_PASS}, 400),
    ({"email": "   ", "password": VALID_PASS}, 400),
    ({"email": "\t\n", "password": VALID_PASS}, 400),
    ({"email": VALID_EMAIL}, 400),
    ({"password": VALID_PASS}, 400),
    ({"campo_extra": "valor"}, 400),
] + [
    ({"email": VALID_EMAIL, "password": f"ClaveIncorrecta_{i}"}, 401)
    for i in range(1, 26)
] + [
    ({"email": f"intruso{i}@uteq.edu.mx", "password": VALID_PASS}, 401)
    for i in range(1, 26)
]

PROTECTED_ROUTES = [
    ("GET", "/api/me"),
    ("POST", "/api/logout"),
    ("GET", "/api/tareas"),
    ("POST", "/api/tareas"),
    ("GET", "/api/tareas/1"),
    ("PUT", "/api/tareas/1"),
    ("DELETE", "/api/tareas/1"),
]

INVALID_AUTH_HEADERS = [
    {},
    {"Authorization": ""},
    {"Authorization": "Basic YWRtaW46MTIz"},
    {"Authorization": "Bearer "},
    {"Authorization": "Bearer token_invalido"},
    {"Authorization": "Bearer 123.456.789"},
    {"Authorization": "Token abcdef"},
    {"Authorization": "Bearer a.b"},
    {"Authorization": "Bearer null"},
    {"Authorization": "Bearer firma_corrupta_2026"},
]

# 40 payloads inválidos para POST /api/tareas (todos -> 400)
INVALID_CREATE_PAYLOADS = (
    [None, {}]
    + [{"descripcion": f"Solo descripcion {i}"} for i in range(1, 14)]
    + [{"titulo": " " * i} for i in range(0, 15)]
    + [{"titulo": ("\t" * i) + "\n", "completada": False} for i in range(1, 11)]
)

# 30 payloads inválidos para PUT /api/tareas/<id> (todos -> 400)
INVALID_UPDATE_PAYLOADS = (
    [None, {}]
    + [{"titulo": " " * i} for i in range(0, 18)]
    + [{"titulo": ("\t" * i) + "\n", "descripcion": "invalida"} for i in range(1, 11)]
)


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("backend_db") / "test_tareas_500.db"
    original_db_path = app_module.DB_PATH
    app_module.DB_PATH = str(db_file)
    app_module.init_db()
    app_module.app.config["TESTING"] = True

    with app_module.app.test_client() as test_client:
        yield test_client

    app_module.DB_PATH = original_db_path


@pytest.fixture(scope="module")
def auth_headers(client):
    res = client.post("/api/login", json={"email": VALID_EMAIL, "password": VALID_PASS})
    assert res.status_code == 200
    token = res.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def tarea_base_id(client, auth_headers):
    res = client.post(
        "/api/tareas",
        headers=auth_headers,
        json={"titulo": "Tarea base fija", "descripcion": "Para pruebas de validación"},
    )
    assert res.status_code == 201
    return res.get_json()["data"]["id"]


# 1. Salud de la API (20 pruebas)
@pytest.mark.parametrize("iteracion", range(1, 21))
def test_01_health_check(client, iteracion):
    res = client.get("/api/health")
    body = res.get_json()
    assert res.status_code == 200
    assert body["status"] == "ok"
    assert body["service"] == "api-tareas-parcial2"


# 2. Login exitoso (20 pruebas)
@pytest.mark.parametrize("intento", range(1, 21))
def test_02_login_exitoso(client, intento):
    res = client.post("/api/login", json={"email": VALID_EMAIL, "password": VALID_PASS})
    body = res.get_json()
    assert res.status_code == 200
    assert isinstance(body["token"], str) and len(body["token"]) > 10
    assert body["user"]["email"] == VALID_EMAIL


# 3. Login inválido (60 pruebas)
@pytest.mark.parametrize("payload,expected_status", INVALID_LOGIN_CASES)
def test_03_login_invalido(client, payload, expected_status):
    res = client.post("/api/login", json=payload) if payload is not None else client.post("/api/login")
    assert res.status_code == expected_status
    assert "error" in res.get_json()


# 4. Rutas protegidas sin autenticación válida (7 x 10 = 70 pruebas)
@pytest.mark.parametrize("method,path", PROTECTED_ROUTES)
@pytest.mark.parametrize("headers", INVALID_AUTH_HEADERS)
def test_04_rutas_protegidas_401(client, method, path, headers):
    res = client.open(path, method=method, headers=headers, json={"titulo": "Bloqueado"})
    assert res.status_code == 401


# 5. Sesión activa /api/me y /api/logout (20 pruebas)
@pytest.mark.parametrize("sesion", range(1, 21))
def test_05_me_y_logout(client, auth_headers, sesion):
    me_res = client.get("/api/me", headers=auth_headers)
    assert me_res.status_code == 200
    assert me_res.get_json()["user"]["email"] == VALID_EMAIL

    out_res = client.post("/api/logout", headers=auth_headers)
    assert out_res.status_code == 200


# 6. Crear y consultar tareas válidas (100 pruebas)
@pytest.mark.parametrize("idx", range(1, 101))
def test_06_crear_y_consultar_tareas(client, auth_headers, idx):
    completada = idx % 2 == 0
    payload = {
        "titulo": f"Tarea Backend #{idx:03d}",
        "descripcion": f"Descripción técnica #{idx}" if idx % 3 != 0 else "",
        "completada": completada,
    }
    post_res = client.post("/api/tareas", headers=auth_headers, json=payload)
    assert post_res.status_code == 201
    created = post_res.get_json()["data"]

    get_res = client.get(f"/api/tareas/{created['id']}", headers=auth_headers)
    assert get_res.status_code == 200
    fetched = get_res.get_json()["data"]
    assert fetched["titulo"] == payload["titulo"]
    assert fetched["descripcion"] == payload["descripcion"]
    assert fetched["completada"] is completada


# 7. Validación de errores 400 al crear tareas (40 pruebas)
@pytest.mark.parametrize("payload", INVALID_CREATE_PAYLOADS)
def test_07_crear_tarea_invalida(client, auth_headers, payload):
    res = (
        client.post("/api/tareas", headers=auth_headers, json=payload)
        if payload is not None
        else client.post("/api/tareas", headers=auth_headers)
    )
    assert res.status_code == 400


# 8. Actualización completa de tareas (60 pruebas)
@pytest.mark.parametrize("idx", range(1, 61))
def test_08_actualizar_tareas(client, auth_headers, idx):
    created = client.post(
        "/api/tareas",
        headers=auth_headers,
        json={"titulo": f"Original {idx}", "descripcion": "Antes"},
    ).get_json()["data"]

    nuevo_estado = idx % 2 == 1
    put_res = client.put(
        f"/api/tareas/{created['id']}",
        headers=auth_headers,
        json={
            "titulo": f"Actualizada {idx}",
            "descripcion": f"Después {idx}",
            "completada": nuevo_estado,
        },
    )
    assert put_res.status_code == 200
    updated = put_res.get_json()["data"]
    assert updated["titulo"] == f"Actualizada {idx}"
    assert updated["completada"] is nuevo_estado

    check_res = client.get(f"/api/tareas/{created['id']}", headers=auth_headers)
    assert check_res.get_json()["data"]["titulo"] == f"Actualizada {idx}"


# 9. Validación de errores 400 al actualizar tareas (30 pruebas)
@pytest.mark.parametrize("payload", INVALID_UPDATE_PAYLOADS)
def test_09_actualizar_tarea_invalida(client, auth_headers, tarea_base_id, payload):
    res = (
        client.put(f"/api/tareas/{tarea_base_id}", headers=auth_headers, json=payload)
        if payload is not None
        else client.put(f"/api/tareas/{tarea_base_id}", headers=auth_headers)
    )
    assert res.status_code == 400


# 10. Eliminación y confirmación 404 (40 pruebas)
@pytest.mark.parametrize("idx", range(1, 41))
def test_10_eliminar_y_verificar_404(client, auth_headers, idx):
    created = client.post(
        "/api/tareas",
        headers=auth_headers,
        json={"titulo": f"Eliminar {idx}"},
    ).get_json()["data"]

    del_res = client.delete(f"/api/tareas/{created['id']}", headers=auth_headers)
    assert del_res.status_code == 200

    assert client.get(f"/api/tareas/{created['id']}", headers=auth_headers).status_code == 404
    assert client.delete(f"/api/tareas/{created['id']}", headers=auth_headers).status_code == 404


# 11. Operaciones sobre IDs inexistentes (3 x 10 = 30 pruebas)
@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
@pytest.mark.parametrize("missing_id", range(99901, 99911))
def test_11_ids_inexistentes_404(client, auth_headers, method, missing_id):
    res = client.open(
        f"/api/tareas/{missing_id}",
        method=method,
        headers=auth_headers,
        json={"titulo": "No existe"},
    )
    assert res.status_code == 404


# 12. Listado y orden descendente por ID (10 pruebas)
@pytest.mark.parametrize("lote", range(1, 11))
def test_12_listado_orden_descendente(client, auth_headers, lote):
    t1 = client.post("/api/tareas", headers=auth_headers, json={"titulo": f"Lote {lote} A"}).get_json()["data"]
    t2 = client.post("/api/tareas", headers=auth_headers, json={"titulo": f"Lote {lote} B"}).get_json()["data"]

    list_res = client.get("/api/tareas", headers=auth_headers)
    assert list_res.status_code == 200
    items = list_res.get_json()["data"]
    assert items[0]["id"] == t2["id"]
    assert items[1]["id"] == t1["id"]