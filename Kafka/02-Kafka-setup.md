# Docker Compose для Apache Kafka с Kafdrop и Python-клиенты

## Docker Compose файл

Создайте файл `docker-compose.yml` со следующим содержимым:

```yaml
version: '3.8'

services:
  zookeeper:
    image: confluentinc/cp-zookeeper:latest
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000
    ports:
      - "2181:2181"

  kafka:
    image: confluentinc/cp-kafka:latest
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1

  kafdrop:
    image: obsidiandynamics/kafdrop:latest
    depends_on:
      - kafka
    ports:
      - "9000:9000"
    environment:
      KAFKA_BROKER_CONNECT: kafka:9092
```

## Python скрипты

Установите необходимую зависимость:
```bash
pip install kafka-python
```

### producer.py
```python
from kafka import KafkaProducer
import json
import time
from datetime import datetime

# Настройки подключения
KAFKA_BROKER = 'localhost:9092'
TOPIC_NAME = 'test-topic'

# Создание продюсера
producer = KafkaProducer(
    bootstrap_servers=[KAFKA_BROKER],
    value_serializer=lambda x: json.dumps(x).encode('utf-8')
)

def send_message(message):
    """Отправка сообщения в Kafka"""
    try:
        # Добавляем временную метку
        message['timestamp'] = datetime.now().isoformat()
        
        # Отправляем сообщение
        producer.send(TOPIC_NAME, value=message)
        producer.flush()
        
        print(f"Отправлено сообщение: {message}")
        return True
    except Exception as e:
        print(f"Ошибка при отправке: {e}")
        return False

if __name__ == "__main__":
    print("Запуск продюсера Kafka...")
    print("Для остановки нажмите Ctrl+C")
    
    try:
        counter = 0
        while True:
            # Формируем тестовое сообщение
            message = {
                'id': counter,
                'message': f'Тестовое сообщение #{counter}',
                'source': 'python-producer'
            }
            
            # Отправляем сообщение
            send_message(message)
            
            # Увеличиваем счетчик и ждем
            counter += 1
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("Остановка продюсера...")
    finally:
        producer.close()
```

### consumer.py
```python
from kafka import KafkaConsumer
import json

# Настройки подключения
KAFKA_BROKER = 'localhost:9092'
TOPIC_NAME = 'test-topic'

# Создание консьюмера
consumer = KafkaConsumer(
    TOPIC_NAME,
    bootstrap_servers=[KAFKA_BROKER],
    auto_offset_reset='earliest',  # начинать чтение с начала топика
    enable_auto_commit=True,
    group_id='python-consumer-group',
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

def consume_messages():
    """Чтение сообщений из Kafka"""
    print("Запуск консьюмера Kafka...")
    print("Ожидание сообщений. Для остановки нажмите Ctrl+C")
    
    try:
        for message in consumer:
            value = message.value
            print(f"Получено сообщение: {value}")
            print(f"Топик: {message.topic}, Партиция: {message.partition}")
            print(f"Offset: {message.offset}, Timestamp: {message.timestamp}")
            print("-" * 50)
            
    except KeyboardInterrupt:
        print("Остановка консьюмера...")
    finally:
        consumer.close()

if __name__ == "__main__":
    consume_messages()
```

## Инструкция по запуску

1. Запустите Kafka и Kafdrop:
```bash
docker-compose up -d
```

2. Проверьте, что все сервисы работают:
```bash
docker-compose ps
```

3. Откройте Kafdrop в браузере:
```
http://localhost:9000
```

4. В отдельном терминале запустите консьюмер:
```bash
python consumer.py
```

5. В другом терминале запустите продюсер:
```bash
python producer.py
```

6. Наблюдайте за сообщениями в терминале консьюмера и в Kafdrop

## Kafdrop - веб-интерфейс для Kafka

Kafdrop предоставляет удобный веб-интерфейс для:
- Просмотра списка топиков
- Просмотра сообщений в топиках
- Мониторинга потребителей и групп
- Создания новых топиков
- Просмотра информации о брокерах

После запуска откройте http://localhost:9000 для доступа к интерфейсу.