import os
import pytest
from playwright.sync_api import expect, sync_playwright

APP_URL = os.getenv("APP_URL", "http://localhost:8090").rstrip("/")
VALID_EMAIL = os.getenv("APP_USER", "admin@uteq.edu.mx")
VALID_PASS = os.getenv("APP_PASS", "ObsAdmin#2026")

# 20 casos de login incompleto (-> 400)
LOGIN_EMPTY_CASES = [
    (" " * i, VALID_PASS) for i in range(0, 10)
] + [
    (f"correo{i}@uteq.edu.mx", "") for i in range(1, 11)
]

# 60 casos de login con credenciales erróneas (-> 401)
LOGIN_WRONG_CASES = [
    (VALID_EMAIL, f"PassIncorrecta#{i}") for i in range(1, 31)
] + [
    (f"usuario_invalido_{i}@uteq.edu.mx", VALID_PASS) for i in range(1, 31)
]

# 50 casos de título inválido en formulario de tareas (-> 400)
INVALID_TASK_CASES = [
    (" " * (i % 6), f"Descripción sin título #{i}") for i in range(1, 51)
]

# 59 pasos alternando filtros sobre 5 tareas (2 completadas, 3 pendientes)
_FILTER_PATTERN = [("todas", 5), ("pendientes", 3), ("completadas", 2)]
FILTER_SEQUENCE = [
    (i + 1, _FILTER_PATTERN[i % 3][0], _FILTER_PATTERN[i % 3][1])
    for i in range(59)
]


def _limpiar_tareas_existentes(request_ctx):
    login_res = request_ctx.post(
        f"{APP_URL}/api/login",
        data={"email": VALID_EMAIL, "password": VALID_PASS},
    )
    if not login_res.ok:
        return
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    list_res = request_ctx.get(f"{APP_URL}/api/tareas", headers=headers)
    if not list_res.ok:
        return
    for tarea in list_res.json().get("data", []):
        request_ctx.delete(f"{APP_URL}/api/tareas/{tarea['id']}", headers=headers)


@pytest.fixture(scope="module")
def page(pytestconfig):
    headed = bool(pytestconfig.getoption("--headed", default=False))
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        context = browser.new_context(viewport={"width": 1024, "height": 680})
        _limpiar_tareas_existentes(context.request)
        p_page = context.new_page()
        p_page.goto(APP_URL, wait_until="networkidle")
        yield p_page
        context.close()
        browser.close()


# ==========================================
# BLOQUE 1: ESTADO INICIAL Y ATRIBUTOS (25)
# ==========================================

@pytest.mark.parametrize(
    "testid,check,expected",
    [
        ("app-title", "text", "Gestor de Tareas"),
        ("health-badge", "text", "API Online"),
        ("login-section", "visible", None),
        ("login-form", "visible", None),
        ("login-email", "visible", None),
        ("login-password", "visible", None),
        ("btn-login", "text", "Ingresar"),
        ("app-section", "hidden", None),
        ("user-bar", "hidden", None),
        ("login-error", "hidden", None),
    ],
)
def test_01_elementos_iniciales(page, testid, check, expected):
    loc = page.get_by_test_id(testid)
    if check == "visible":
        expect(loc).to_be_visible()
    elif check == "hidden":
        expect(loc).to_be_hidden()
    else:
        expect(loc).to_have_text(expected)


@pytest.mark.parametrize(
    "testid,attr,expected",
    [
        ("login-email", "type", "email"),
        ("login-email", "placeholder", "Correo electrónico"),
        ("login-email", "autocomplete", "username"),
        ("login-email", "id", "login-email"),
        ("login-password", "type", "password"),
        ("login-password", "placeholder", "Contraseña"),
        ("login-password", "autocomplete", "current-password"),
        ("login-password", "id", "login-password"),
        ("btn-login", "type", "submit"),
        ("btn-login", "class", "btn-primary"),
        ("btn-login", "id", "btn-login"),
        ("login-form", "id", "login-form"),
        ("health-badge", "id", "health-badge"),
        ("health-badge", "class", "badge ok"),
        ("login-section", "class", "card login-card"),
    ],
)
def test_02_atributos_login(page, testid, attr, expected):
    expect(page.get_by_test_id(testid)).to_have_attribute(attr, expected)


# ==========================================
# BLOQUE 2: LOGIN INVÁLIDO (80)
# ==========================================

@pytest.mark.parametrize("email,password", LOGIN_EMPTY_CASES)
def test_03_login_campos_incompletos(page, email, password):
    page.get_by_test_id("login-email").fill(email)
    page.get_by_test_id("login-password").fill(password)

    with page.expect_response(lambda r: r.url.endswith("/api/login") and r.request.method == "POST") as resp_info:
        page.get_by_test_id("btn-login").click()

    assert resp_info.value.status == 400
    expect(page.get_by_test_id("login-error")).to_be_visible()
    expect(page.get_by_test_id("login-error")).to_contain_text("Completa correo y contraseña")
    expect(page.get_by_test_id("app-section")).to_be_hidden()


@pytest.mark.parametrize("email,password", LOGIN_WRONG_CASES)
def test_04_login_credenciales_erroneas(page, email, password):
    page.get_by_test_id("login-email").fill(email)
    page.get_by_test_id("login-password").fill(password)

    with page.expect_response(lambda r: r.url.endswith("/api/login") and r.request.method == "POST") as resp_info:
        page.get_by_test_id("btn-login").click()

    assert resp_info.value.status == 401
    expect(page.get_by_test_id("login-error")).to_be_visible()
    expect(page.get_by_test_id("login-error")).to_contain_text("Credenciales incorrectas")
    expect(page.get_by_test_id("app-section")).to_be_hidden()


# ==========================================
# BLOQUE 3: LOGIN EXITOSO Y DASHBOARD (20)
# ==========================================

def test_05_login_exitoso(page):
    page.get_by_test_id("login-email").fill(VALID_EMAIL)
    page.get_by_test_id("login-password").fill(VALID_PASS)

    with page.expect_response(lambda r: r.url.endswith("/api/login") and r.request.method == "POST") as resp_info:
        page.get_by_test_id("btn-login").click()

    assert resp_info.value.status == 200
    expect(page.get_by_test_id("app-section")).to_be_visible()
    expect(page.get_by_test_id("user-email")).to_have_text(VALID_EMAIL)
    expect(page.get_by_test_id("empty-state")).to_be_visible()


@pytest.mark.parametrize("recarga", range(1, 5))
def test_06_persistencia_sesion_recargas(page, recarga):
    page.reload(wait_until="networkidle")
    expect(page.get_by_test_id("app-section")).to_be_visible()
    expect(page.get_by_test_id("user-email")).to_have_text(VALID_EMAIL)


@pytest.mark.parametrize(
    "testid,check,expected",
    [
        ("app-section", "visible", None),
        ("tarea-form", "visible", None),
        ("input-titulo", "visible", None),
        ("input-descripcion", "visible", None),
        ("btn-guardar", "text", "Agregar tarea"),
        ("btn-cancelar", "hidden", None),
        ("error-msg", "hidden", None),
        ("filter-todas", "text", "Todas"),
        ("filter-todas", "class", "active"),
        ("filter-pendientes", "text", "Pendientes"),
        ("filter-completadas", "text", "Completadas"),
        ("lista-tareas", "visible", None),
        ("empty-state", "text", "No hay tareas para mostrar."),
        ("user-bar", "visible", None),
        ("btn-logout", "text", "Cerrar sesión"),
    ],
)
def test_07_elementos_dashboard(page, testid, check, expected):
    loc = page.get_by_test_id(testid)
    if check == "visible":
        expect(loc).to_be_visible()
    elif check == "hidden":
        expect(loc).to_be_hidden()
    elif check == "class":
        expect(loc).to_have_class(expected)
    else:
        expect(loc).to_have_text(expected)


# ==========================================
# BLOQUE 4: VALIDACIONES DE FORMULARIO (50)
# ==========================================

@pytest.mark.parametrize("titulo,descripcion", INVALID_TASK_CASES)
def test_08_validacion_titulo_invalido(page, titulo, descripcion):
    page.get_by_test_id("input-titulo").fill(titulo)
    page.get_by_test_id("input-descripcion").fill(descripcion)

    with page.expect_response(lambda r: r.url.endswith("/api/tareas") and r.request.method == "POST") as resp_info:
        page.get_by_test_id("btn-guardar").click()

    assert resp_info.value.status == 400
    expect(page.get_by_test_id("error-msg")).to_be_visible()
    expect(page.get_by_test_id("error-msg")).to_contain_text("obligatorio")


# ==========================================
# BLOQUE 5: CREAR Y ELIMINAR EN UI (100)
# ==========================================

@pytest.mark.parametrize("idx", range(1, 101))
def test_09_crear_verificar_y_eliminar_tarea(page, idx):
    titulo = f"Tarea E2E #{idx:03d}"
    descripcion = f"Detalle automatizado {idx}" if idx % 2 == 1 else ""

    page.get_by_test_id("input-titulo").fill(titulo)
    page.get_by_test_id("input-descripcion").fill(descripcion)

    with page.expect_response(lambda r: r.url.endswith("/api/tareas") and r.request.method == "POST") as post_info:
        page.get_by_test_id("btn-guardar").click()
    assert post_info.value.status == 201

    lista = page.get_by_test_id("lista-tareas")
    expect(lista).to_contain_text(titulo)
    if descripcion:
        expect(lista).to_contain_text(descripcion)

    with page.expect_response(lambda r: "/api/tareas/" in r.url and r.request.method == "DELETE") as del_info:
        page.get_by_test_id("btn-eliminar").first.click()
    assert del_info.value.status == 200
    expect(page.get_by_test_id("empty-state")).to_be_visible()


# ==========================================
# BLOQUE 6: EDICIÓN Y CANCELACIÓN (80)
# ==========================================

def test_10_preparar_tarea_edicion(page):
    page.get_by_test_id("input-titulo").fill("Tarea Base Edición")
    page.get_by_test_id("input-descripcion").fill("Descripción inicial")

    with page.expect_response(lambda r: r.url.endswith("/api/tareas") and r.request.method == "POST") as resp_info:
        page.get_by_test_id("btn-guardar").click()
    assert resp_info.value.status == 201
    expect(page.get_by_test_id("lista-tareas")).to_contain_text("Tarea Base Edición")


@pytest.mark.parametrize("idx", range(1, 30))
def test_11_cancelar_edicion(page, idx):
    page.get_by_test_id("btn-editar").first.click()
    expect(page.get_by_test_id("btn-guardar")).to_have_text("Guardar cambios")
    expect(page.get_by_test_id("btn-cancelar")).to_be_visible()

    page.get_by_test_id("input-titulo").fill(f"Borrador descartado {idx}")
    page.get_by_test_id("btn-cancelar").click()

    expect(page.get_by_test_id("btn-guardar")).to_have_text("Agregar tarea")
    expect(page.get_by_test_id("btn-cancelar")).to_be_hidden()
    expect(page.get_by_test_id("lista-tareas")).to_contain_text("Tarea Base Edición")


@pytest.mark.parametrize("idx", range(1, 51))
def test_12_editar_tarea_exitosa(page, idx):
    nuevo_titulo = f"Tarea Editada #{idx:02d}"
    nueva_desc = f"Desc actualizada {idx}"

    page.get_by_test_id("btn-editar").first.click()
    page.get_by_test_id("input-titulo").fill(nuevo_titulo)
    page.get_by_test_id("input-descripcion").fill(nueva_desc)

    with page.expect_response(lambda r: "/api/tareas/" in r.url and r.request.method == "PUT") as resp_info:
        page.get_by_test_id("btn-guardar").click()
    assert resp_info.value.status == 200

    expect(page.get_by_test_id("lista-tareas")).to_contain_text(nuevo_titulo)
    expect(page.get_by_test_id("lista-tareas")).to_contain_text(nueva_desc)


# ==========================================
# BLOQUE 7: COMPLETAR Y REABRIR (60)
# ==========================================

@pytest.mark.parametrize("ciclo", range(1, 61))
def test_13_toggle_completar_reabrir(page, ciclo):
    item = page.locator('[data-testid="lista-tareas"] li').first
    btn_toggle = item.get_by_test_id("btn-toggle")

    with page.expect_response(lambda r: "/api/tareas/" in r.url and r.request.method == "PUT") as resp_info:
        btn_toggle.click()
    assert resp_info.value.status == 200

    if ciclo % 2 == 1:
        expect(item).to_have_class("completada")
        expect(btn_toggle).to_have_text("Reabrir")
    else:
        expect(item).not_to_have_class("completada")
        expect(btn_toggle).to_have_text("Completar")


# ==========================================
# BLOQUE 8: FILTROS COMBINADOS (60)
# ==========================================

def test_14_preparar_lote_filtros(page):
    for i in range(1, 5):
        page.get_by_test_id("input-titulo").fill(f"Tarea Filtro #{i}")
        page.get_by_test_id("input-descripcion").fill(f"Grupo filtros {i}")
        with page.expect_response(lambda r: r.url.endswith("/api/tareas") and r.request.method == "POST") as resp_info:
            page.get_by_test_id("btn-guardar").click()
        assert resp_info.value.status == 201

    items = page.locator('[data-testid="lista-tareas"] li')
    expect(items).to_have_count(5)

    for idx in (0, 1):
        with page.expect_response(lambda r: "/api/tareas/" in r.url and r.request.method == "PUT") as resp_info:
            items.nth(idx).get_by_test_id("btn-toggle").click()
        assert resp_info.value.status == 200
        expect(items.nth(idx)).to_have_class("completada")


@pytest.mark.parametrize("paso,filtro,esperados", FILTER_SEQUENCE)
def test_15_navegacion_filtros(page, paso, filtro, esperados):
    btn = page.get_by_test_id(f"filter-{filtro}")
    btn.click()
    expect(btn).to_have_class("active")
    expect(page.locator('[data-testid="lista-tareas"] li')).to_have_count(esperados)


# ==========================================
# BLOQUE 9: VACIADO DEL LOTE (10)
# ==========================================

@pytest.mark.parametrize("restantes", [4, 3, 2, 1, 0])
def test_16_eliminar_lote_tareas(page, restantes):
    page.get_by_test_id("filter-todas").click()
    with page.expect_response(lambda r: "/api/tareas/" in r.url and r.request.method == "DELETE") as resp_info:
        page.get_by_test_id("btn-eliminar").first.click()
    assert resp_info.value.status == 200

    if restantes > 0:
        expect(page.get_by_test_id("btn-eliminar")).to_have_count(restantes)
    else:
        expect(page.get_by_test_id("empty-state")).to_be_visible()


@pytest.mark.parametrize("filtro", ["todas", "pendientes", "completadas", "todas", "pendientes"])
def test_17_filtros_en_estado_vacio(page, filtro):
    page.get_by_test_id(f"filter-{filtro}").click()
    expect(page.get_by_test_id("empty-state")).to_be_visible()


# ==========================================
# BLOQUE 10: CIERRE Y REINGRESO DE SESIÓN (15)
# ==========================================

@pytest.mark.parametrize("ciclo", range(1, 15))
def test_18_cerrar_sesion_y_reingresar(page, ciclo):
    with page.expect_response(lambda r: r.url.endswith("/api/logout") and r.request.method == "POST") as out_info:
        page.get_by_test_id("btn-logout").click()
    assert out_info.value.status == 200
    expect(page.get_by_test_id("login-section")).to_be_visible()

    page.get_by_test_id("login-email").fill(VALID_EMAIL)
    page.get_by_test_id("login-password").fill(VALID_PASS)
    with page.expect_response(lambda r: r.url.endswith("/api/login") and r.request.method == "POST") as in_info:
        page.get_by_test_id("btn-login").click()
    assert in_info.value.status == 200
    expect(page.get_by_test_id("app-section")).to_be_visible()
    expect(page.get_by_test_id("user-email")).to_have_text(VALID_EMAIL)


def test_19_cierre_sesion_final(page):
    with page.expect_response(lambda r: r.url.endswith("/api/logout") and r.request.method == "POST") as out_info:
        page.get_by_test_id("btn-logout").click()
    assert out_info.value.status == 200
    expect(page.get_by_test_id("login-section")).to_be_visible()
    expect(page.get_by_test_id("app-section")).to_be_hidden()
    expect(page.get_by_test_id("user-bar")).to_be_hidden()
    assert page.evaluate("() => localStorage.getItem('auth_token')") is None