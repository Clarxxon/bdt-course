import os
import time
import logging
from datetime import datetime
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
import json

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LogSender:
    def __init__(self):
        self.es_host = os.getenv('ELASTICSEARCH_HOST', 'elasticsearch')
        self.es_port = os.getenv('ELASTICSEARCH_PORT', '9200')
        self.es_username = os.getenv('ELASTICSEARCH_USERNAME', 'elastic')
        self.es_password = os.getenv('ELASTICSEARCH_PASSWORD', 'changeme')
        self.send_interval = int(os.getenv('SEND_INTERVAL', '10'))
        
        self.es = None
        self.connect_elasticsearch()
    
    def connect_elasticsearch(self):
        """Подключение к Elasticsearch"""
        try:
            self.es = Elasticsearch(
                [f'{self.es_host}:{self.es_port}'],
                basic_auth=(self.es_username, self.es_password),
                verify_certs=False,
                ssl_show_warn=False
            )
            if self.es.ping():
                logger.info("Connected to Elasticsearch successfully")
            else:
                logger.error("Could not connect to Elasticsearch")
        except Exception as e:
            logger.error(f"Error connecting to Elasticsearch: {e}")
    
    def generate_log_message(self):
        """Генерация тестового лог-сообщения"""
        levels = ['INFO', 'WARNING', 'ERROR', 'DEBUG']
        messages = [
            "Application started successfully",
            "User login attempt",
            "Database connection established",
            "Processing request",
            "Task completed",
            "Warning: High memory usage",
            "Error: Connection timeout"
        ]
        
        import random
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "level": random.choice(levels),
            "message": random.choice(messages),
            "service": "python-log-sender",
            "host": os.getenv('HOSTNAME', 'unknown')
        }
    
    def send_logs(self):
        """Отправка логов в Elasticsearch"""
        if not self.es or not self.es.ping():
            self.connect_elasticsearch()
            if not self.es or not self.es.ping():
                return
        
        try:
            log_message = self.generate_log_message()
            response = self.es.index(
                index="logs-python",
                body=log_message
            )
            logger.info(f"Log sent successfully: {response['_id']}")
        except Exception as e:
            logger.error(f"Error sending log: {e}")
    
    def run(self):
        """Основной цикл отправки логов"""
        logger.info("Starting log sender service")
        while True:
            self.send_logs()
            time.sleep(self.send_interval)

if __name__ == "__main__":
    sender = LogSender()
    sender.run()