import base64
import os
from pathlib import Path
import re
import sys

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
SCREENSHOT_DIR = ROOT_DIR / "screenshots_parcial2"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("OTEL_ENABLED", "false")

_test_counter = 0


def pytest_addoption(parser):
    try:
        parser.addoption(
            "--headed",
            action="store_true",
            default=False,
            help="Ejecuta Playwright con navegador visible",
        )
    except ValueError:
        pass


def pytest_html_results_summary(prefix, summary, postfix):
    prefix.append(
        """
        <style>
          .extras-row { display: table-row !important; }
          .media-container { display: block !important; }
          .evidence-img {
            max-width: 720px;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            margin-top: 6px;
          }
        </style>
        """
    )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    global _test_counter
    outcome = yield
    report = outcome.get_result()

    if report.when != "call":
        return

    page = item.funcargs.get("page")
    if page is None:
        return

    _test_counter += 1
    mode = os.getenv("CAPTURE_SCREENSHOTS", "all").lower()
    should_capture = mode == "all" or (mode == "failures" and report.failed)
    if not should_capture:
        return

    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", item.name).strip("_")[:55]
    img_path = SCREENSHOT_DIR / f"{_test_counter:03d}_{safe_name}.jpg"

    try:
        jpg_bytes = page.screenshot(
            path=str(img_path),
            type="jpeg",
            quality=55,
            full_page=False,
            animations="disabled",
        )
        print(f"\n[PRUEBA #{_test_counter:03d}] {item.name} | {page.url} | {img_path.name}")

        pytest_html = item.config.pluginmanager.getplugin("html")
        if pytest_html is not None:
            b64_img = base64.b64encode(jpg_bytes).decode("utf-8")
            extras = getattr(report, "extras", [])
            extras.append(
                pytest_html.extras.html(
                    f'<div><p><strong>[PRUEBA #{_test_counter:03d}]</strong> {page.url}</p>'
                    f'<img class="evidence-img" src="data:image/jpeg;base64,{b64_img}" /></div>'
                )
            )
            report.extras = extras
    except Exception as exc:
        print(f"\n[PRUEBA #{_test_counter:03d}] No se pudo capturar pantalla: {exc}")