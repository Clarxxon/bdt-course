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
    image: elasticsearch:8.11.0
    container_name: elasticsearch
    environment:
      - discovery.type=single-node
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
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
    networks:
      - elastic

  kibana:
    image: kibana:8.11.0
    container_name: kibana
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
    ports:
      - "5601:5601"
    networks:
      - elastic
    depends_on:
      - elasticsearch

  # ---------- Filebeat для сбора логов ----------
  filebeat:
    image: docker.elastic.co/beats/filebeat:8.11.0
    container_name: filebeat
    environment:
      - STRICT_PERMS=false
    volumes:
      - ./filebeat.yml:/usr/share/filebeat/filebeat.yml:ro
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - /var/run/docker.sock:/var/run/docker.sock
    networks:
      - elastic
    depends_on:
      - elasticsearch
    restart: unless-stopped

  # ---------- Тестовый контейнер для логов ----------
  nginx-test:
    image: nginx:alpine
    container_name: nginx-test
    ports:
      - "8080:80"
    networks:
      - elastic
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

volumes:
  es_data:
    driver: local

networks:
  elastic:
    driver: bridge
```

## Шаг 2: Создаем конфигурацию Filebeat

Создайте файл `filebeat.yml`:

```yaml
filebeat.inputs:
- type: container
  paths:
    - '/var/lib/docker/containers/*/*.log'
  processors:
    - add_docker_metadata:
        host: "unix:///var/run/docker.sock"

# Добавляем поля Docker
processors:
  - add_docker_metadata:
      host: "unix:///var/run/docker.sock"
  - add_fields:
      target: ''
      fields:
        service: 'docker-logs'

# Настройки для парсинга JSON логов
json.keys_under_root: true
json.overwrite_keys: true
json.add_error_key: true

# Настройки вывода в Elasticsearch
output.elasticsearch:
  hosts: ["http://elasticsearch:9200"]
  indices:
    - index: "filebeat-docker-%{+yyyy.MM.dd}"
      when.equals:
        service: "docker-logs"

# Настройки для Kibana
setup.kibana:
  host: "kibana:5601"

# Настройки шаблонов индексов
setup.template:
  name: "filebeat-docker"
  pattern: "filebeat-docker-*"

# Включаем модули для Docker
filebeat.config.modules:
  path: ${path.config}/modules.d/*.yml
  reload.enabled: false

# Включаем автоматическое обнаружение
filebeat.autodiscover:
  providers:
    - type: docker
      hints.enabled: true

# Настройки логирования Filebeat
logging.level: info
logging.to_files: true
logging.files:
  path: /var/log/filebeat
  name: filebeat
  keepfiles: 7
  permissions: 0644
```

## Шаг 3: Инициализация Filebeat

Создайте скрипт для настройки Filebeat:

```bash
#!/bin/bash
# setup-filebeat.sh

# Останавливаем всё
docker-compose down

# Запускаем Elasticsearch и Kibana
docker-compose up -d elasticsearch kibana nginx-test

# Ждем готовности Elasticsearch
echo "Waiting for Elasticsearch..."
until curl -s http://localhost:9200/_cluster/health | grep -q '"status":"green"'; do
  sleep 5
done

# Создаем директорию для логов Filebeat
mkdir -p filebeat-data

# Запускаем Filebeat с настройкой
docker-compose up -d filebeat

# Инициализируем Filebeat в контейнере
docker exec filebeat filebeat setup -e

echo "Filebeat setup complete!"
echo "Generate some logs by visiting: http://localhost:8080"
```

Сделайте скрипт исполняемым и запустите:
```bash
chmod +x setup-filebeat.sh
./setup-filebeat.sh
```

## Шаг 4: Генерация логов

Откройте в браузере несколько раз: `http://localhost:8080`

Или используйте curl для генерации логов:
```bash
# Генерируем запросы к nginx в терминале
for i in {1..10}; do
  curl http://localhost:8080/test-$i
  sleep 1
done
```

## Шаг 5: Настройка Kibana для просмотра логов

### 1. Создайте data view для логов:

В Kibana перейдите:
- **Management → Stack Management → Data Views**
- **Create data view**
- **Name**: `docker-logs`
- **Index pattern**: `filebeat-docker-*`
- **Timestamp field**: `@timestamp`
- **Create**

### 2. Просмотр логов в Discover:

- **Analytics → Discover**
- Выберите data view `docker-logs`
- Вы увидите логи всех Docker-контейнеров

### 3. Создайте панель для мониторинга логов:

В **Analytics → Dashboard** создайте новую dashboard с визуализациями:

**Визуализация 1**: Количество логов по контейнерам
- Тип: **Vertical Bar**
- Ось X: `container.name` (термы)
- Ось Y: `Count`

**Визуализация 2**: Уровни логов
- Тип: **Pie chart**
- Сегменты: `log.level`

**Визуализация 3**: Последние логи
- Тип: **Data table**
- Поля: `@timestamp`, `container.name`, `message`

## Шаг 6: Расширенная конфигурация для приложения

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

## Шаг 7: Полезные запросы для поиска логов

В **Discover** используйте KQL (Kibana Query Language):

```
# Логи конкретного контейнера
container.name: "nginx-test"

# Логи с ошибками
log.level: "error"

# Логи за последний час
message: "GET"

# Комбинированный запрос
container.name: "nginx-test" and log.level: "error"
```

## Шаг 8: Мониторинг в реальном времени

В **Analytics → Discover**:
- Нажмите **Auto refresh**
- Выберите интервал (например, 5 секунд)

## Если Filebeat не работает, проверьте:

1. **Права доступа**:
```bash
chmod 644 filebeat.yml
```

2. **Логи Filebeat**:
```bash
docker logs filebeat
```

3. **Проверьте индексы в Elasticsearch**:
```bash
curl http://localhost:9200/_cat/indices?v
```