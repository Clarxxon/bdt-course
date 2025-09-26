import os
import time
import logging
import json
from datetime import datetime
from elasticsearch import Elasticsearch
from pythonjsonlogger import jsonlogger

# Настройка JSON логгера для Elasticsearch
def setup_elasticsearch_logger():
    """Настройка логгера который сразу пишет в формате Elasticsearch"""
    
    # Создаем логгер
    logger = logging.getLogger('elastic-logger')
    logger.setLevel(logging.INFO)
    
    # Создаем JSON форматтер для Elasticsearch
    formatter = jsonlogger.JsonFormatter(
        fmt='%(asctime)s %(levelname)s %(message)s %(name)s %(module)s %(funcName)s',
        rename_fields={
            'asctime': '@timestamp',
            'levelname': 'level',
            'message': 'message',
            'name': 'logger_name',
            'module': 'module',
            'funcName': 'function'
        },
        datefmt='%Y-%m-%dT%H:%M:%S.%fZ',  # Формат времени для ES
        static_fields={
            'service': 'python-log-sender',
            'environment': os.getenv('ENVIRONMENT', 'development'),
            'host': os.getenv('HOSTNAME', 'unknown'),
            'type': 'log'
        }
    )
    
    # Хендлер для вывода в консоль (в JSON формате)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

class ElasticsearchHandler(logging.Handler):
    """Кастомный хендлер для отправки логов напрямую в Elasticsearch"""
    
    def __init__(self, es_client, index_prefix="logs"):
        super().__init__()
        self.es = es_client
        self.index_prefix = index_prefix
        self.setFormatter(jsonlogger.JsonFormatter())
    
    def emit(self, record):
        """Отправка лога в Elasticsearch"""
        try:
            # Преобразуем запись лога в словарь
            log_entry = self.format_record(record)
            
            # Создаем индекс с датой (например: logs-2024.01.15)
            index_name = f"{self.index_prefix}-{datetime.utcnow().strftime('%Y.%m.%d')}"
            
            # Отправляем в Elasticsearch
            self.es.index(
                index=index_name,
                body=log_entry,
                pipeline="timestamp"  # Опционально: для парсинга timestamp
            )
        except Exception as e:
            print(f"Error sending log to Elasticsearch: {e}")
    
    def format_record(self, record):
        """Форматирование записи лога для Elasticsearch"""
        if isinstance(record.msg, dict):
            # Если сообщение уже словарь, используем его как основу
            log_data = record.msg.copy()
        else:
            # Если сообщение строка, создаем базовую структуру
            log_data = {'message': record.msg}
        
        # Добавляем стандартные поля
        log_data.update({
            '@timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger_name': record.name,
            'module': record.module,
            'function': record.funcName,
            'line_number': record.lineno,
            'service': 'python-log-sender',
            'environment': os.getenv('ENVIRONMENT', 'development'),
            'host': os.getenv('HOSTNAME', 'unknown')
        })
        
        # Добавляем экстра-поля если есть
        if hasattr(record, 'extra_fields') and isinstance(record.extra_fields, dict):
            log_data.update(record.extra_fields)
        
        return log_data

class ElasticsearchLogger:
    """Упрощенный интерфейс для логирования в Elasticsearch"""
    
    def __init__(self, service_name="python-app"):
        self.service_name = service_name
        self.es = Elasticsearch(
            [f"{os.getenv('ELASTICSEARCH_HOST', 'elasticsearch')}:9200"],
            basic_auth=(
                os.getenv('ELASTICSEARCH_USERNAME', 'elastic'),
                os.getenv('ELASTICSEARCH_PASSWORD', 'changeme')
            ),
            verify_certs=False
        )
        
        # Настраиваем корневой логгер
        self.setup_logger()
    
    def setup_logger(self):
        """Настройка логгера с Elasticsearch хендлером"""
        logger = logging.getLogger(self.service_name)
        logger.setLevel(logging.INFO)
        
        # Очищаем существующие хендлеры
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # Добавляем Elasticsearch хендлер
        es_handler = ElasticsearchHandler(self.es, f"logs-{self.service_name}")
        es_handler.setLevel(logging.INFO)
        
        # Также добавляем консольный хендлер для отладки
        console_handler = logging.StreamHandler()
        console_formatter = jsonlogger.JsonFormatter(
            '%(@timestamp)s %(level)s %(message)s %(service)s'
        )
        console_handler.setFormatter(console_formatter)
        
        logger.addHandler(es_handler)
        logger.addHandler(console_handler)
        
        self.logger = logger
    
    def log(self, level, message, **extra_fields):
        """Упрощенный метод логирования с дополнительными полями"""
        # Создаем запись лога с дополнительными полями
        if isinstance(message, dict):
            log_data = message
        else:
            log_data = {'message': message}
        
        log_data.update(extra_fields)
        
        # Добавляем экстра-поля в запись лога
        extra = {'extra_fields': log_data}
        
        if level.lower() == 'info':
            self.logger.info(message, extra=extra)
        elif level.lower() == 'error':
            self.logger.error(message, extra=extra)
        elif level.lower() == 'warning':
            self.logger.warning(message, extra=extra)
        elif level.lower() == 'debug':
            self.logger.debug(message, extra=extra)
        else:
            self.logger.info(message, extra=extra)

# Пример использования
def main():
    # Инициализация логгера
    es_logger = ElasticsearchLogger("my-python-service")
    
    # Простой способ логирования
    logger = es_logger.logger
    
    # Примеры логирования в формате Elasticsearch
    logger.info("Application started successfully")
    
    # Логирование с дополнительными полями
    logger.info("User login attempt", extra={
        'extra_fields': {
            'user_id': 12345,
            'action': 'login',
            'ip_address': '192.168.1.1',
            'duration_ms': 150
        }
    })
    
    # Логирование ошибок с контекстом
    try:
        # Симуляция ошибки
        result = 1 / 0
    except Exception as e:
        logger.error("Division by zero error", extra={
            'extra_fields': {
                'error_type': type(e).__name__,
                'error_message': str(e),
                'operation': 'division',
                'stack_trace': 'traceback_info_here'
            }
        })
    
    # Использование упрощенного интерфейса
    es_logger.log('info', 'Processing request', 
                 request_id='req-123', 
                 endpoint='/api/users',
                 method='GET')
    
    # Логирование метрик
    es_logger.log('info', 'Performance metrics',
                 response_time_ms=245,
                 memory_usage_mb=128,
                 database_queries=15,
                 metric_type='performance')

if __name__ == "__main__":
    main()