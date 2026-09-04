import orjson
import structlog
import sys
import logging
import os

def configure_fastapi_logging():
    benchmark_mode=os.getenv("BENCHMARK_MODE", "false").lower() == "true"
    target_log_level = logging.WARNING if benchmark_mode else logging.INFO

    def orjson_dumps(obj, **kwargs):
        return orjson.dumps(obj).decode('utf-8')

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(serializer=orjson_dumps)
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(target_log_level) 

    for _log in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
        logger_instance = logging.getLogger(_log)
        logger_instance.handlers = [handler]
        logger_instance.setLevel(target_log_level)
        logger_instance.propagate = False

    access_logger = logging.getLogger("uvicorn.access")
    access_logger.handlers = []
    access_logger.propagate = False