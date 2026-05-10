# -*- coding: utf-8 -*-
"""
Утилиты для работы с Redis в проекте.
Обеспечивает распределенные блокировки для предотвращения гонок в кластерных средах.
"""

import logging
import redis
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)

# Конфигурация Redis по умолчанию
DEFAULT_REDIS_CONFIG = {
    "host": "localhost",
    "port": 6379,
    "db": 0,
    "socket_timeout": 5,
    "socket_connect_timeout": 2,
}


def get_redis_connection():
    """Возвращает соединение с Redis."""
    config = getattr(settings, "REDIS_CONFIG", DEFAULT_REDIS_CONFIG)

    try:
        connection = redis.Redis(
            host=config["host"],
            port=config["port"],
            db=config["db"],
            socket_timeout=config["socket_timeout"],
            socket_connect_timeout=config["socket_connect_timeout"],
            decode_responses=True,
        )

        # Проверяем соединение
        if not connection.ping():
            logger.warning("Redis connection failed. Falling back to local locks.")
            return None

        return connection
    except redis.ConnectionError as e:
        logger.warning(
            f"Redis connection error: {str(e)}. Falling back to local locks."
        )
        return None
    except Exception as e:
        logger.error(f"Unexpected Redis error: {str(e)}")
        return None


def redis_lock(lock_name, timeout=10, blocking_timeout=5):
    """
    Контекстный менеджер для распределенной блокировки с использованием Redis.

    Args:
        lock_name: Название блокировки (например, f"ticket_{ticket_id}_lock")
        timeout: Время жизни блокировки в секундах
        blocking_timeout: Максимальное время ожидания блокировки

    Returns:
        Контекстный менеджер для использования с оператором `with`
    """

    class RedisLockManager:
        def __init__(self):
            self.connection = get_redis_connection()
            self.lock = None
            self.lock_name = lock_name
            self.timeout = timeout
            self.blocking_timeout = blocking_timeout
            self.acquired = False

        def __enter__(self):
            if not self.connection:
                logger.warning("Redis not available. Using local lock only.")
                return self

            try:
                self.lock = self.connection.lock(
                    self.lock_name,
                    timeout=self.timeout,
                    blocking_timeout=self.blocking_timeout,
                )
                self.acquired = self.lock.acquire(blocking=True)
                if self.acquired:
                    logger.debug(f"Acquired Redis lock: {self.lock_name}")
                else:
                    logger.warning(f"Failed to acquire Redis lock: {self.lock_name}")
                return self
            except Exception as e:
                logger.error(f"Redis lock error: {str(e)}")
                self.acquired = False
                return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.acquired and self.lock:
                try:
                    self.lock.release()
                    logger.debug(f"Released Redis lock: {self.lock_name}")
                except Exception as e:
                    logger.error(f"Redis unlock error: {str(e)}")
            return False

    return RedisLockManager()


def get_lock(ticket_id, use_redis=True):
    """
    Возвращает подходящий механизм блокировки для билета.

    Args:
        ticket_id: ID билета
        use_redis: Использовать Redis для распределенных блокировок
    """
    if use_redis:
        return redis_lock(f"ticket_{ticket_id}_lock")
    else:
        # Локальная блокировка через select_for_update
        from django.db import transaction
        from core.models import Ticket

        class LocalLockManager:
            def __enter__(self):
                # Начинаем транзакцию
                transaction.atomic().__enter__()
                # Блокируем билет
                Ticket.objects.select_for_update().get(pk=ticket_id)
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                transaction.atomic().__exit__(exc_type, exc_val, exc_tb)

        return LocalLockManager()
