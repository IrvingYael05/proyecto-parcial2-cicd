const API_BASE = "/api";
const TOKEN_KEY = "auth_token";

let tareasCache = [];
let filtroActual = "todas";

const healthBadge = document.getElementById("health-badge");
const userBar = document.getElementById("user-bar");
const userEmailSpan = document.getElementById("user-email");
const btnLogout = document.getElementById("btn-logout");

const loginSection = document.getElementById("login-section");
const loginForm = document.getElementById("login-form");
const loginEmailInput = document.getElementById("login-email");
const loginPasswordInput = document.getElementById("login-password");
const loginError = document.getElementById("login-error");

const appSection = document.getElementById("app-section");
const form = document.getElementById("tarea-form");
const editIdInput = document.getElementById("edit-id");
const tituloInput = document.getElementById("titulo");
const descripcionInput = document.getElementById("descripcion");
const btnGuardar = document.getElementById("btn-guardar");
const btnCancelar = document.getElementById("btn-cancelar");
const errorMsg = document.getElementById("error-msg");
const listaTareas = document.getElementById("lista-tareas");

function getToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

function mostrarErrorLogin(mensaje) {
  loginError.textContent = mensaje;
  loginError.style.display = "block";
}

function limpiarErrorLogin() {
  loginError.textContent = "";
  loginError.style.display = "none";
}

function mostrarError(mensaje) {
  errorMsg.textContent = mensaje;
  errorMsg.style.display = "block";
}

function limpiarError() {
  errorMsg.textContent = "";
  errorMsg.style.display = "none";
}

function mostrarVistaLogin() {
  localStorage.removeItem(TOKEN_KEY);
  tareasCache = [];
  listaTareas.innerHTML = "";
  salirModoEdicion();
  appSection.style.display = "none";
  userBar.style.display = "none";
  userEmailSpan.textContent = "";
  loginSection.style.display = "block";
}

function mostrarVistaApp(email) {
  limpiarErrorLogin();
  loginForm.reset();
  loginSection.style.display = "none";
  userEmailSpan.textContent = email;
  userBar.style.display = "flex";
  appSection.style.display = "block";
}

function salirModoEdicion() {
  editIdInput.value = "";
  form.reset();
  btnGuardar.textContent = "Agregar tarea";
  btnCancelar.style.display = "none";
  limpiarError();
}

async function apiFetch(path, options = {}) {
  const token = getToken();
  const headers = { ...(options.headers || {}) };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (res.status === 401 && path !== "/login") {
    mostrarVistaLogin();
  }
  return res;
}

async function verificarSalud() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    const body = await res.json();
    if (res.ok && body.status === "ok") {
      healthBadge.textContent = "API Online";
      healthBadge.className = "badge ok";
    } else {
      throw new Error("Estado inválido");
    }
  } catch {
    healthBadge.textContent = "API Offline";
    healthBadge.className = "badge err";
  }
}

async function verificarSesion() {
  const token = getToken();
  if (!token) {
    mostrarVistaLogin();
    return;
  }

  try {
    const res = await apiFetch("/me");
    if (!res.ok) {
      mostrarVistaLogin();
      return;
    }
    const body = await res.json();
    mostrarVistaApp(body.user.email);
    await cargarTareas();
  } catch {
    mostrarVistaLogin();
  }
}

async function cargarTareas() {
  try {
    const res = await apiFetch("/tareas");
    if (!res.ok) return;
    const body = await res.json();
    tareasCache = body.data || [];
    renderizarTareas();
  } catch {
    mostrarError("No se pudieron cargar las tareas.");
  }
}

function renderizarTareas() {
  const filtradas = tareasCache.filter((t) => {
    if (filtroActual === "pendientes") return !t.completada;
    if (filtroActual === "completadas") return t.completada;
    return true;
  });

  if (filtradas.length === 0) {
    listaTareas.innerHTML = `<li class="empty" data-testid="empty-state">No hay tareas para mostrar.</li>`;
    return;
  }

  listaTareas.innerHTML = "";
  filtradas.forEach((tarea) => {
    const li = document.createElement("li");
    li.dataset.testid = `tarea-item-${tarea.id}`;
    if (tarea.completada) li.classList.add("completada");

    const info = document.createElement("div");
    const title = document.createElement("strong");
    title.className = "task-title";
    title.dataset.testid = "tarea-titulo";
    title.textContent = tarea.titulo;
    info.appendChild(title);

    if (tarea.descripcion) {
      const desc = document.createElement("p");
      desc.className = "task-desc";
      desc.dataset.testid = "tarea-descripcion";
      desc.textContent = tarea.descripcion;
      info.appendChild(desc);
    }

    const actions = document.createElement("div");
    actions.className = "actions";

    const btnToggle = document.createElement("button");
    btnToggle.type = "button";
    btnToggle.className = "btn-sm btn-secondary";
    btnToggle.dataset.testid = "btn-toggle";
    btnToggle.textContent = tarea.completada ? "Reabrir" : "Completar";
    btnToggle.addEventListener("click", () => toggleTarea(tarea));

    const btnEditar = document.createElement("button");
    btnEditar.type = "button";
    btnEditar.className = "btn-sm btn-primary";
    btnEditar.dataset.testid = "btn-editar";
    btnEditar.textContent = "Editar";
    btnEditar.addEventListener("click", () => iniciarEdicion(tarea));

    const btnEliminar = document.createElement("button");
    btnEliminar.type = "button";
    btnEliminar.className = "btn-sm btn-danger";
    btnEliminar.dataset.testid = "btn-eliminar";
    btnEliminar.textContent = "Eliminar";
    btnEliminar.addEventListener("click", () => eliminarTarea(tarea.id));

    actions.append(btnToggle, btnEditar, btnEliminar);
    li.append(info, actions);
    listaTareas.appendChild(li);
  });
}

function iniciarEdicion(tarea) {
  editIdInput.value = tarea.id;
  tituloInput.value = tarea.titulo;
  descripcionInput.value = tarea.descripcion || "";
  btnGuardar.textContent = "Guardar cambios";
  btnCancelar.style.display = "inline-block";
  limpiarError();
  tituloInput.focus();
}

async function toggleTarea(tarea) {
  const res = await apiFetch(`/tareas/${tarea.id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ completada: !tarea.completada }),
  });
  if (res.ok) await cargarTareas();
}

async function eliminarTarea(id) {
  const res = await apiFetch(`/tareas/${id}`, { method: "DELETE" });
  if (!res.ok) return;
  if (String(editIdInput.value) === String(id)) {
    salirModoEdicion();
  }
  await cargarTareas();
}

loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  limpiarErrorLogin();

  const email = loginEmailInput.value.trim();
  const password = loginPasswordInput.value;

  const res = await fetch(`${API_BASE}/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    mostrarErrorLogin(body.error || "No se pudo iniciar sesión.");
    return;
  }

  localStorage.setItem(TOKEN_KEY, body.token);
  mostrarVistaApp(body.user.email);
  await cargarTareas();
});

btnLogout.addEventListener("click", async () => {
  try {
    await apiFetch("/logout", { method: "POST" });
  } catch {
    // Continuar cierre de sesión local
  }
  mostrarVistaLogin();
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  limpiarError();

  const titulo = tituloInput.value.trim();
  const descripcion = descripcionInput.value.trim();
  const editId = editIdInput.value;

  const path = editId ? `/tareas/${editId}` : "/tareas";
  const method = editId ? "PUT" : "POST";

  const res = await apiFetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ titulo, descripcion }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    mostrarError(err.error || "Error al guardar la tarea.");
    return;
  }

  salirModoEdicion();
  await cargarTareas();
});

btnCancelar.addEventListener("click", salirModoEdicion);

document.querySelectorAll(".filters button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document
      .querySelectorAll(".filters button")
      .forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    filtroActual = btn.dataset.filter;
    renderizarTareas();
  });
});

verificarSalud();
verificarSesion();
