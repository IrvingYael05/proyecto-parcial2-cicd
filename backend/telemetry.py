import base64
import logging
import os

from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.sqlite3 import SQLite3Instrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_initialized = False


class TelemetryState:
    def __init__(self):
        self.logger = logging.getLogger("api_tareas")
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            stream_handler = logging.StreamHandler()
            self.logger.addHandler(stream_handler)

        self.request_counter = None
        self.error_counter = None
        self.duration_histogram = None


telemetry = TelemetryState()


def init_telemetry(app):
    global _initialized
    if _initialized:
        return telemetry

    otel_enabled = os.getenv("OTEL_ENABLED", "false").lower() == "true"
    if not otel_enabled:
        _initialized = True
        return telemetry

    o2_base_url = os.getenv("O2_BASE_URL", "http://127.0.0.1:5080").rstrip("/")
    o2_user = os.getenv("O2_USER", "admin@uteq.edu.mx")
    o2_pass = os.getenv("O2_PASS", "ObsAdmin#2026")
    service_name = os.getenv("OTEL_SERVICE_NAME", "api-tareas-backend")

    token = base64.b64encode(f"{o2_user}:{o2_pass}".encode("utf-8")).decode("utf-8")
    base_headers = {"Authorization": f"Basic {token}"}
    log_headers = {**base_headers, "stream-name": "api_logs"}

    resource = Resource.create({"service.name": service_name})

    # 1. Trazas distribuidas (Flask + SQLite)
    tracer_provider = TracerProvider(resource=resource)
    span_exporter = OTLPSpanExporter(
        endpoint=f"{o2_base_url}/api/default/v1/traces",
        headers=base_headers,
    )
    tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(tracer_provider)

    # 2. Métricas (Latencia, RPS y Tasa de error por endpoint)
    metric_exporter = OTLPMetricExporter(
        endpoint=f"{o2_base_url}/api/default/v1/metrics",
        headers=base_headers,
    )
    metric_reader = PeriodicExportingMetricReader(
        metric_exporter,
        export_interval_millis=10000,
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    meter = metrics.get_meter(service_name)
    telemetry.request_counter = meter.create_counter(
        name="http_requests_total",
        description="Total de peticiones HTTP recibidas por endpoint",
    )
    telemetry.error_counter = meter.create_counter(
        name="http_errors_total",
        description="Total de respuestas HTTP con error (4xx/5xx)",
    )
    telemetry.duration_histogram = meter.create_histogram(
        name="http_request_duration_ms",
        description="Tiempo de respuesta HTTP en milisegundos",
        unit="ms",
    )

    # 3. Logs estructurados vía OTLP hacia el stream api_logs
    logger_provider = LoggerProvider(resource=resource)
    log_exporter = OTLPLogExporter(
        endpoint=f"{o2_base_url}/api/default/v1/logs",
        headers=log_headers,
    )
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
    set_logger_provider(logger_provider)

    otel_log_handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
    telemetry.logger.addHandler(otel_log_handler)

    # Auto-instrumentación de Flask y consultas SQLite
    FlaskInstrumentor().instrument_app(app)
    SQLite3Instrumentor().instrument()

    _initialized = True
    return telemetry