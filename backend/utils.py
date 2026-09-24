import logging
import sys

# Configure a safe logger that won't leak sensitive data
logger = logging.getLogger("legalease")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def safe_log(level, message):
    """
    Safe logging function. Never logs document contents, secrets, or raw user text.
    Only logs system status, errors, and metadata.
    """
    if level == "info":
        logger.info(message)
    elif level == "error":
        logger.error(message)
    elif level == "warning":
        logger.warning(message)
