# Добавляем источник логов в ELK

Для примера можно использовать Filebeat. Filebeat — это легковесный «сборщик логов» (log shipper) с открытым исходным кодом, разработанный компанией Elastic. Его главная задача — собирать, агрегировать и отправлять логи (журналы событий) с ваших серверов и приложений в централизованную систему для последующего анализа.

- Устанавливается туда, где работают ваши приложения или системы (например, веб-сервер, база данных).

- Отслеживает указанные вами файлы логов (например, /var/log/nginx/access.log).

- Считывает новые строки в этих файлах по мере их появления.

- Агрегирует и отправляет эти данные в центральную систему, чаще всего в Elasticsearch, но также может отправлять в Logstash, Redis или Kafka.

Гарантирует доставку: Filebeat отслеживает, какие данные были успешно отправлены, и если отправка не удалась, он повторит попытку. Это предотвращает потерю логов.

## Шаг 1: Добавляем Filebeat в docker-compose.yml

```yaml
version: '3.8'

services:
  elasticsearch:
    image: elasticsearch:8.5.0
    container_name: elasticsearch
    environment:
      - discovery.type=single-node
      - ES_JAVA_OPTS=-Xms512m -Xmx512m
      - xpack.security.enabled=false
      - cluster.routing.allocation.disk.threshold_enabled=false
    ulimits:
      memlock:
        soft: -1
        hard: -1
    volumes:
      - es_data:/usr/share/elasticsearch/data
    ports:
      - "9200:9200"
    networks: [elastic]

  kibana:
    image: kibana:8.5.0
    container_name: kibana
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
      - ELASTICSEARCH_REQUESTTIMEOUT=120000
    ports:
      - "5601:5601"
    networks: [elastic]
    depends_on: [elasticsearch]

  filebeat:
    image: elastic/filebeat:8.11.0
    container_name: filebeat
    user: "0"                       # чтобы точно было право читать файлы
    environment:
      - STRICT_PERMS=false
    volumes:
      - ./filebeat.yml:/usr/share/filebeat/filebeat.yml:ro
      - ./logs:/logs:ro              # <-- монтируем папку с 1.log
      # Если не читаем логи контейнеров — эти два монтирования можно убрать:
      # - /var/lib/docker/containers:/var/lib/docker/containers:ro
      # - /var/run/docker.sock:/var/run/docker.sock
    networks: [elastic]
    depends_on: [elasticsearch]
    restart: unless-stopped

  nginx-test:
    image: nginx:alpine
    container_name: nginx-test
    ports:
      - "8080:80"
    networks: [elastic]
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    volumes:
      - ./nginx.conf:/etc/nginx.conf:ro
      - ./logs/nginx:/var/log/nginx

volumes:
  es_data:
    driver: local

networks:
  elastic:
    driver: bridge
```

## Шаг 2: Создаем конфигурацию Filebeat

+ создаем папку logs и в нее кладем файл с расширением .log

Создайте файл `filebeat.yml`:

```yaml
filebeat.inputs:
  - type: filestream
    id: from-one-file
    enabled: true
    paths:
      - /logs/1.log           # указываем наш файл с логами
      - /logs/nginx/error.log # оставляйте только ваши файлы!
      - /logs/nginx/access.log

output.elasticsearch:
  hosts: ["http://elasticsearch:9200"]
  # Оставляем ILM по умолчанию: индексы будут вида filebeat-8.11.0-*
  # (Самый простой и надежный старт)

setup.kibana:
  host: "kibana:5601"

logging.level: info
```

Далее выполняем  `docker compose up`

## Генерация логов

Откройте в браузере несколько раз: `http://localhost:8080`

Или используйте curl для генерации логов:
```bash
# Генерируем запросы к nginx в терминале
for i in {1..10}; do
  curl http://localhost:8080/test-$i
  sleep 1
done
```

## Настройка Kibana для просмотра логов

### 1. Создайте data view для логов:

В Kibana перейдите:
- **Management → Stack Management → Data Views**
- **Create data view**
- **Name**: `filebeat-logs`
- **Index pattern**: `filebeat-*`
- **Timestamp field**: `@timestamp`
- **Create**

### 2. Просмотр логов в Discover:

- **Analytics → Discover**
- Выберите data view `filebeat-logs`
- Вы увидите логи всех Docker-контейнеров


## Расширенная конфигурация для приложения

Если у вас есть свое приложение, добавьте его в docker-compose.yml:

```yaml
  my-app:
    image: your-app:latest
    container_name: my-app
    networks:
      - elastic
    environment:
      - LOG_LEVEL=INFO
    depends_on:
      - elasticsearch
```

## Полезные запросы для поиска логов

В **Discover** используйте KQL (Kibana Query Language):

```
# Логи с ошибками
log.level: "error"

# Логи за последний час
message: "GET"

# Комбинированный запрос
container.name: "nginx-test" and log.level: "error"
```

## Мониторинг в реальном времени

В **Analytics → Discover**:
- Нажмите **Auto refresh**
- Выберите интервал (например, 5 секунд)
