import logging.config
import structlog
from structlog import configure, processors, stdlib, threadlocal
from pythonjsonlogger import jsonlogger
import sys


def get_logger(name):
    handler = logging.FileHandler("analysis.log")
    handler.setFormatter(jsonlogger.JsonFormatter("%(message)s %(name)s"))
    root_logger = logging.getLogger(name)
    root_logger.addHandler(handler)
    root_logger.setLevel(level=logging.INFO)
    struct_logger = structlog.wrap_logger(
        root_logger, 
        context_class=threadlocal.wrap_dict(dict),
        logger_factory=stdlib.LoggerFactory(),
        wrapper_class=stdlib.BoundLogger,
        processors=[
            stdlib.filter_by_level,
            stdlib.add_logger_name,
            stdlib.add_log_level,
            stdlib.PositionalArgumentsFormatter(),
            processors.TimeStamper(fmt="iso"),
            processors.StackInfoRenderer(),
            processors.format_exc_info,
            processors.UnicodeDecoder(),
            stdlib.render_to_log_kwargs]
    )
    return struct_logger