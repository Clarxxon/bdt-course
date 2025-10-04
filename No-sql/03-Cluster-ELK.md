# docker-compose.yml для кластера с 3 нодами

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
      - action.auto_create_index=".kibana*,.monitoring*,.watches,.triggered_watches,.watcher-history*"
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
      - ELASTICSEARCH_REQUESTTIMEOUT=120000
    ports:
      - "5601:5601"
    networks:
      - elastic
    depends_on:
      - elasticsearch

volumes:
  es_data:
    driver: local

networks:
  elastic:
    driver: bridge
```

---

### **Конфигурация Nginx (nginx.conf)**

Создайте папку `config/nginx` и поместите туда файл `nginx.conf`:

```nginx
# config/nginx/nginx.conf
events { }

http {
    upstream elasticsearch {
        # Перечисляем все ноды в кластере
        server es01:9200;
        server es02:9200;
        server es03:9200;
    }

    server {
        listen 9200;

        location / {
            # Проксируем все запросы на кластер Elasticsearch
            proxy_pass http://elasticsearch;
            proxy_http_version 1.1;
            proxy_set_header Connection "Keep-Alive";
            proxy_set_header Proxy-Connection "Keep-Alive";
            proxy_set_header Authorization $http_authorization; # Важно: передаем заголовок аутентификации
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header Host $host;
        }
    }
}
```

---

### **Файл переменных окружения (`.env`)**

```bash
# .env
ELASTIC_PASSWORD=YourSuperStrongPassword123!
```

---

### **Как это работает и ключевые особенности**

1.  **Настоящий кластер (3 ноды):**
    *   Ноды `es01`, `es02`, `es03` образуют кластер.
    *   Параметры `discovery.seed_hosts` и `cluster.initial_master_nodes` позволяют нодам найти друг друга и сформировать кластер.
    *   Каждая нода имеет свою роль (`roles=master,data,ingest`) и свое независимое хранилище (`es0X_data`).

2.  **Отказоустойчивость:**
    *   При наличии **трех master-eligible нод** кластер сможет пережить падение одной из них, сохранив возможность записи (формируется кворум).
    *   Шарды данных будут автоматически реплицироваться между нодами. Если одна нода упадет, ее данные будут доступны с реплик на других нодах.

3.  **Балансировщик нагрузки (Nginx):**
    *   Сервис `es-lb` выступает в роли единой точки входа (coordinating node).
    *   Все запросы на `localhost:9200` распределяются по очереди между тремя нодами кластера (`round-robin`).
    *   Это **снимает нагрузку** с отдельных нод и повышает отказоустойчивость: если одна нода не отвечает, Nginx перенаправит запрос на другую.

4.  **Горизонтальное масштабирование:**
    *   **Чтобы добавить новую ноду (es04)**, вам достаточно скопировать блок сервиса (например, `es03`), изменить `container_name`, `node.name` и том, а также добавить его имя в `discovery.seed_hosts` на всех существующих нодах и перезапустить стек.
    *   Elasticsearch автоматически перераспределит шарды данных на новую ноду.

5.  **Изоляция и стабильность:**
    *   Фиксированная подсеть (`10.5.0.0/16`) предотвращает случайную смену IP-адресов контейнеров при перезапуске.
    *   `Healthchecks` гарантируют, что ноды полностью готовы к работе, прежде чем от них будут зависеть другие сервисы.

### **Как запустить**

1.  Создайте структуру папок и файлов:
    ```
    my-es-cluster/
    ├── docker-compose.yml
    ├── .env
    └── config/
        └── nginx/
            └── nginx.conf
    ```
2.  Запустите кластер:
    ```bash
    docker-compose up -d
    ```
3.  Наблюдайте за запуском (это займет несколько минут):
    ```bash
    docker-compose logs -f
    ```
4.  Проверьте состояние кластера:
    ```bash
    # Через балансировщик
    curl -u elastic:YourSuperStrongPassword123! http://localhost:9200/_cluster/health?pretty
    ```
    В ответе вы должны увидеть `"status" : "green"` и `"number_of_nodes" : 3`.
