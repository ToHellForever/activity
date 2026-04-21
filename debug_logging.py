import logging
import os

# Создаем файл лога вручную
log_file_path = os.path.join(os.getcwd(), "debug.log")

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_file_path), logging.StreamHandler()],
)

logger = logging.getLogger(__name__)
logger.info(f"Логирование настроено. Файл лога: {log_file_path}")
