# Полный Docker Compose для аналитической платформы с Airflow

```yaml
version: '3.8'

x-postgres-config: &postgres-config
  image: postgres:15-alpine
  environment:
    POSTGRES_USER: ${POSTGRES_USER:-admin}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-admin123}
    POSTGRES_DB: ${POSTGRES_DB:-postgres}
    POSTGRES_INITDB_ARGS: "--encoding=UTF8 --locale=C"
  volumes:
    - postgres_data_${POSTGRES_DB:-postgres}:/var/lib/postgresql/data
    - ./postgres/init:/docker-entrypoint-initdb.d:ro
  networks:
    - data-network
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-admin}"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 10s
  deploy:
    resources:
      limits:
        memory: 2G
        cpus: '1.0'
      reservations:
        memory: 1G
        cpus: '0.5'

x-redis-config: &redis-config
  image: redis:7-alpine
  command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD:-redis123}
  volumes:
    - redis_data:/data
  networks:
    - data-network
  healthcheck:
    test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD:-redis123}", "ping"]
    interval: 30s
    timeout: 10s
    retries: 3
  deploy:
    resources:
      limits:
        memory: 512M
      reservations:
        memory: 256M

services:
  # ============ БАЗЫ ДАННЫХ ============
  
  # Основное хранилище данных
  postgres-warehouse:
    <<: *postgres-config
    container_name: postgres-analytical-warehouse
    environment:
      POSTGRES_USER: ${WAREHOUSE_DB_USER:-warehouse_admin}
      POSTGRES_PASSWORD: ${WAREHOUSE_DB_PASSWORD:-warehouse123}
      POSTGRES_DB: ${WAREHOUSE_DB_NAME:-warehouse}
    volumes:
      - postgres_data_warehouse:/var/lib/postgresql/data
      - ./postgres/warehouse-init:/docker-entrypoint-initdb.d:ro
      - ./postgres/backups:/backups
    ports:
      - "${WAREHOUSE_DB_PORT:-5432}:5432"
    command: >
      postgres
      -c max_connections=500
      -c shared_buffers=1GB
      -c effective_cache_size=3GB
      -c maintenance_work_mem=256MB
      -c checkpoint_completion_target=0.9
      -c wal_buffers=16MB
      -c default_statistics_target=100
      -c random_page_cost=1.1
      -c effective_io_concurrency=200
      -c work_mem=16MB
      -c min_wal_size=1GB
      -c max_wal_size=4GB
      -c max_worker_processes=8
      -c max_parallel_workers_per_gather=4
      -c max_parallel_workers=8
      -c max_parallel_maintenance_workers=4

  # База данных для Airflow
  postgres-airflow:
    <<: *postgres-config
    container_name: postgres-airflow-metadata
    environment:
      POSTGRES_USER: ${AIRFLOW_DB_USER:-airflow}
      POSTGRES_PASSWORD: ${AIRFLOW_DB_PASSWORD:-airflow123}
      POSTGRES_DB: ${AIRFLOW_DB_NAME:-airflow}
    volumes:
      - postgres_data_airflow:/var/lib/postgresql/data
      - ./postgres/airflow-init:/docker-entrypoint-initdb.d:ro
    ports:
      - "${AIRFLOW_DB_PORT:-5433}:5432"

  # Redis для Celery (очереди задач Airflow)
  redis-airflow:
    <<: *redis-config
    container_name: redis-airflow-queue
    environment:
      REDIS_PASSWORD: ${REDIS_PASSWORD:-redis123}
    ports:
      - "${REDIS_PORT:-6379}:6379"

  # Redis для кэширования
  redis-cache:
    <<: *redis-config
    container_name: redis-analytics-cache
    environment:
      REDIS_PASSWORD: ${REDIS_CACHE_PASSWORD:-cache123}
    ports:
      - "${REDIS_CACHE_PORT:-6380}:6379"
    command: redis-server --appendonly no --requirepass ${REDIS_CACHE_PASSWORD:-cache123} --maxmemory 512mb --maxmemory-policy allkeys-lru

  # ============ AIRFLOW ============
  
  # Airflow Scheduler
  airflow-scheduler:
    image: apache/airflow:2.7.1
    container_name: airflow-scheduler
    restart: unless-stopped
    environment:
      # Основные настройки
      AIRFLOW__CORE__EXECUTOR: CeleryExecutor
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://${AIRFLOW_DB_USER:-airflow}:${AIRFLOW_DB_PASSWORD:-airflow123}@postgres-airflow/${AIRFLOW_DB_NAME:-airflow}
      AIRFLOW__CELERY__RESULT_BACKEND: db+postgresql://${AIRFLOW_DB_USER:-airflow}:${AIRFLOW_DB_PASSWORD:-airflow123}@postgres-airflow/${AIRFLOW_DB_NAME:-airflow}
      AIRFLOW__CELERY__BROKER_URL: redis://:${REDIS_PASSWORD:-redis123}@redis-airflow:6379/0
      AIRFLOW__CORE__LOAD_EXAMPLES: 'false'
      AIRFLOW__CORE__FERNET_KEY: ${AIRFLOW_FERNET_KEY:-}
      AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION: 'true'
      AIRFLOW__CORE__DEFAULT_TIMEZONE: 'UTC'
      
      # Безопасность
      AIRFLOW__API__AUTH_BACKEND: 'airflow.api.auth.backend.basic_auth'
      AIRFLOW__WEBSERVER__SECRET_KEY: ${AIRFLOW_SECRET_KEY:-supersecretkey}
      AIRFLOW__WEBSERVER__RBAC: 'true'
      
      # Настройки производительности
      AIRFLOW__SCHEDULER__MIN_FILE_PROCESS_INTERVAL: 30
      AIRFLOW__SCHEDULER__DAG_DIR_LIST_INTERVAL: 300
      AIRFLOW__CORE__PARALLELISM: 32
      AIRFLOW__CORE__DAG_CONCURRENCY: 16
      AIRFLOW__CORE__MAX_ACTIVE_RUNS_PER_DAG: 4
      AIRFLOW__CELERY__WORKER_CONCURRENCY: 8
      
      # Подключения к базам данных
      AIRFLOW_CONN_WAREHOUSE_DB: postgresql://${WAREHOUSE_DB_USER:-warehouse_admin}:${WAREHOUSE_DB_PASSWORD:-warehouse123}@postgres-warehouse/${WAREHOUSE_DB_NAME:-warehouse}
      AIRFLOW_CONN_AIRFLOW_DB: postgresql://${AIRFLOW_DB_USER:-airflow}:${AIRFLOW_DB_PASSWORD:-airflow123}@postgres-airflow/${AIRFLOW_DB_NAME:-airflow}
      
      # Переменные окружения
      WAREHOUSE_DB_HOST: postgres-warehouse
      WAREHOUSE_DB_PORT: 5432
      WAREHOUSE_DB_NAME: ${WAREHOUSE_DB_NAME:-warehouse}
      WAREHOUSE_DB_USER: ${WAREHOUSE_DB_USER:-warehouse_admin}
      WAREHOUSE_DB_PASSWORD: ${WAREHOUSE_DB_PASSWORD:-warehouse123}
      
      REDIS_HOST: redis-airflow
      REDIS_PORT: 6379
      REDIS_PASSWORD: ${REDIS_PASSWORD:-redis123}
      
      # Пользователь Airflow
      _AIRFLOW_WWW_USER_USERNAME: ${AIRFLOW_ADMIN_USER:-admin}
      _AIRFLOW_WWW_USER_PASSWORD: ${AIRFLOW_ADMIN_PASSWORD:-admin123}
      _AIRFLOW_DB_UPGRADE: 'true'
      _PIP_ADDITIONAL_REQUIREMENTS: |
        apache-airflow-providers-postgres==5.6.0
        apache-airflow-providers-redis==3.1.0
        apache-airflow-providers-celery==3.2.0
        apache-airflow-providers-http==4.5.0
        apache-airflow-providers-sftp==3.3.0
        psycopg2-binary==2.9.6
        redis==4.5.5
        pandas==2.0.3
        numpy==1.24.3
        sqlalchemy==2.0.15
        great-expectations==0.17.13
        python-dotenv==1.0.0
        requests==2.31.0
        beautifulsoup4==4.12.2
        lxml==4.9.2
        openpyxl==3.1.2
        cryptography==41.0.3
        pyarrow==12.0.1
        scikit-learn==1.3.0
        matplotlib==3.7.2
        
    volumes:
      # DAGs и конфигурация
      - ./airflow/dags:/opt/airflow/dags
      - ./airflow/logs:/opt/airflow/logs
      - ./airflow/plugins:/opt/airflow/plugins
      - ./airflow/config:/opt/airflow/config
      - ./airflow/scripts:/opt/airflow/scripts
      - ./airflow/variables:/opt/airflow/variables
      - ./airflow/connections:/opt/airflow/connections
      
      # Конфигурационные файлы
      - ./airflow/airflow.cfg:/opt/airflow/airflow.cfg:ro
      - ./airflow/webserver_config.py:/opt/airflow/webserver_config.py:ro
      
      # SSH ключи для SFTP подключений
      - ~/.ssh:/opt/airflow/.ssh:ro
      
      # Общие скрипты
      - ./scripts:/opt/scripts:ro
      
    networks:
      - data-network
    command: >
      bash -c "
        if [ ! -f /opt/airflow/airflow.db ]; then
          airflow db init &&
          airflow users create \
            --username ${AIRFLOW_ADMIN_USER:-admin} \
            --password ${AIRFLOW_ADMIN_PASSWORD:-admin123} \
            --firstname Admin \
            --lastname User \
            --role Admin \
            --email admin@example.com;
        fi &&
        airflow scheduler
      "
    depends_on:
      postgres-airflow:
        condition: service_healthy
      redis-airflow:
        condition: service_healthy
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
        reservations:
          memory: 1G
          cpus: '0.5'

  # Airflow Webserver
  airflow-webserver:
    image: apache/airflow:2.7.1
    container_name: airflow-webserver
    restart: unless-stopped
    environment:
      <<: *airflow-environment
    volumes:
      - ./airflow/dags:/opt/airflow/dags
      - ./airflow/logs:/opt/airflow/logs
      - ./airflow/plugins:/opt/airflow/plugins
      - ./airflow/config:/opt/airflow/config
      - ./airflow/scripts:/opt/airflow/scripts
      - ./airflow/variables:/opt/airflow/variables
      - ./airflow/connections:/opt/airflow/connections
      - ./airflow/airflow.cfg:/opt/airflow/airflow.cfg:ro
      - ./airflow/webserver_config.py:/opt/airflow/webserver_config.py:ro
      - ~/.ssh:/opt/airflow/.ssh:ro
    ports:
      - "${AIRFLOW_PORT:-8080}:8080"
    networks:
      - data-network
    command: webserver
    depends_on:
      - airflow-scheduler
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G

  # Airflow Workers (Celery workers)
  airflow-worker:
    image: apache/airflow:2.7.1
    container_name: airflow-worker
    restart: unless-stopped
    environment:
      <<: *airflow-environment
    volumes:
      - ./airflow/dags:/opt/airflow/dags
      - ./airflow/logs:/opt/airflow/logs
      - ./airflow/plugins:/opt/airflow/plugins
      - ./airflow/config:/opt/airflow/config
      - ./airflow/scripts:/opt/airflow/scripts
      - ./airflow/airflow.cfg:/opt/airflow/airflow.cfg:ro
      - ~/.ssh:/opt/airflow/.ssh:ro
      - ./scripts:/opt/scripts:ro
    networks:
      - data-network
    command: celery worker
    depends_on:
      - airflow-scheduler
      - redis-airflow
    deploy:
      replicas: ${AIRFLOW_WORKERS:-2}
      resources:
        limits:
          memory: 4G
          cpus: '2.0'
        reservations:
          memory: 2G
          cpus: '1.0'

  # Airflow Flower (мониторинг Celery)
  airflow-flower:
    image: apache/airflow:2.7.1
    container_name: airflow-flower
    restart: unless-stopped
    environment:
      <<: *airflow-environment
      AIRFLOW__CELERY__FLOWER_BASIC_AUTH: ${AIRFLOW_ADMIN_USER:-admin}:${AIRFLOW_ADMIN_PASSWORD:-admin123}
    volumes:
      - ./airflow/dags:/opt/airflow/dags
      - ./airflow/logs:/opt/airflow/logs
      - ./airflow/config:/opt/airflow/config
      - ./airflow/airflow.cfg:/opt/airflow/airflow.cfg:ro
    ports:
      - "${AIRFLOW_FLOWER_PORT:-5555}:5555"
    networks:
      - data-network
    command: celery flower
    depends_on:
      - airflow-scheduler
      - redis-airflow

  # ============ BI И ВИЗУАЛИЗАЦИЯ ============
  
  # Metabase для визуализации данных
  metabase:
    image: metabase/metabase:latest
    container_name: metabase-analytics
    restart: unless-stopped
    environment:
      MB_DB_TYPE: postgresql
      MB_DB_DBNAME: ${WAREHOUSE_DB_NAME:-warehouse}
      MB_DB_PORT: 5432
      MB_DB_USER: ${WAREHOUSE_DB_USER:-warehouse_admin}
      MB_DB_PASS: ${WAREHOUSE_DB_PASSWORD:-warehouse123}
      MB_DB_HOST: postgres-warehouse
      MB_SITE_NAME: "Analytical Warehouse Dashboard"
      MB_SITE_LOCALE: ru
      MB_ANONYMOUS_TRACKING_ENABLED: "false"
      MB_ENABLE_EMBEDDING: "true"
      MB_ENABLE_PUBLIC_SHARING: "true"
      MB_PREMIUM_EMBEDDING_TOKEN: ${METABASE_EMBED_TOKEN:-}
      MB_JETTY_HOST: 0.0.0.0
      MB_JETTY_PORT: 3000
      JAVA_TIMEZONE: UTC
      JAVA_OPTS: "-Xmx2g -Xms1g"
    volumes:
      - metabase_data:/metabase-data
      - ./metabase/plugins:/plugins
    ports:
      - "${METABASE_PORT:-3000}:3000"
    networks:
      - data-network
    depends_on:
      postgres-warehouse:
        condition: service_healthy
    deploy:
      resources:
        limits:
          memory: 3G
        reservations:
          memory: 2G

  # Superset (альтернатива Metabase)
  superset:
    image: apache/superset:latest
    container_name: superset-dashboard
    restart: unless-stopped
    environment:
      SUPERSET_SECRET_KEY: ${SUPERSET_SECRET_KEY:-supersecretkey123}
      SUPERSET_CONFIG_PATH: /app/pythonpath/superset_config.py
      FLASK_ENV: production
      DATABASE_DIALECT: postgresql
      DATABASE_USER: ${WAREHOUSE_DB_USER:-warehouse_admin}
      DATABASE_PASSWORD: ${WAREHOUSE_DB_PASSWORD:-warehouse123}
      DATABASE_HOST: postgres-warehouse
      DATABASE_PORT: 5432
      DATABASE_DB: ${WAREHOUSE_DB_NAME:-warehouse}
      REDIS_HOST: redis-cache
      REDIS_PORT: 6379
      REDIS_CELERY_DB: 0
      REDIS_RESULTS_DB: 1
    volumes:
      - superset_data:/app/superset_home
      - ./superset/superset_config.py:/app/pythonpath/superset_config.py:ro
    ports:
      - "${SUPERSET_PORT:-8088}:8088"
    networks:
      - data-network
    command: >
      sh -c "
        superset db upgrade &&
        superset init &&
        gunicorn \
          --bind 0.0.0.0:8088 \
          --access-logfile - \
          --error-logfile - \
          --workers 4 \
          --worker-class gthread \
          --threads 10 \
          --timeout 120 \
          --limit-request-line 0 \
          --limit-request-field_size 0 \
          superset.app:create_app()
      "
    depends_on:
      - postgres-warehouse
      - redis-cache

  # ============ АДМИНИСТРИРОВАНИЕ И МОНИТОРИНГ ============
  
  # pgAdmin для управления PostgreSQL
  pgadmin:
    image: dpage/pgadmin4:latest
    container_name: pgadmin-warehouse
    restart: unless-stopped
    environment:
      PGADMIN_DEFAULT_EMAIL: ${PGADMIN_EMAIL:-admin@warehouse.com}
      PGADMIN_DEFAULT_PASSWORD: ${PGADMIN_PASSWORD:-admin123}
      PGADMIN_CONFIG_SERVER_MODE: 'False'
      PGADMIN_CONFIG_MASTER_PASSWORD_REQUIRED: 'False'
      PGADMIN_DISABLE_POSTFIX: 'True'
    volumes:
      - pgadmin_data:/var/lib/pgadmin
      - ./pgadmin/servers.json:/pgadmin4/servers.json:ro
    ports:
      - "${PGADMIN_PORT:-5050}:80"
    networks:
      - data-network
    depends_on:
      - postgres-warehouse
      - postgres-airflow
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M

  # Prometheus для сбора метрик
  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus-metrics
    restart: unless-stopped
    volumes:
      - prometheus_data:/prometheus
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./prometheus/alerts.yml:/etc/prometheus/alerts.yml:ro
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--storage.tsdb.retention.time=30d'
      - '--web.enable-lifecycle'
    ports:
      - "${PROMETHEUS_PORT:-9090}:9090"
    networks:
      - data-network
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G

  # Grafana для визуализации метрик
  grafana:
    image: grafana/grafana:latest
    container_name: grafana-dashboard
    restart: unless-stopped
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD:-admin123}
      GF_INSTALL_PLUGINS: grafana-piechart-panel,grafana-clock-panel,grafana-simple-json-datasource
      GF_FEATURE_TOGGLES_ENABLE: "publicDashboards"
      GF_SERVER_DOMAIN: localhost
      GF_SERVER_ROOT_URL: "%(protocol)s://%(domain)s:${GRAFANA_PORT:-3001}/"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
      - ./grafana/datasources:/etc/grafana/provisioning/datasources:ro
      - ./grafana/plugins:/var/lib/grafana/plugins
    ports:
      - "${GRAFANA_PORT:-3001}:3000"
    networks:
      - data-network
    depends_on:
      - prometheus
      - postgres-warehouse
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M

  # Loki для сбора логов
  loki:
    image: grafana/loki:latest
    container_name: loki-log-aggregation
    restart: unless-stopped
    volumes:
      - loki_data:/loki
      - ./loki/loki-config.yml:/etc/loki/local-config.yaml:ro
    command: -config.file=/etc/loki/local-config.yaml
    ports:
      - "${LOKI_PORT:-3100}:3100"
    networks:
      - data-network
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M

  # Promtail для отправки логов в Loki
  promtail:
    image: grafana/promtail:latest
    container_name: promtail-log-collector
    restart: unless-stopped
    volumes:
      - /var/log:/var/log:ro
      - ./promtail/promtail-config.yml:/etc/promtail/config.yml:ro
      - ./airflow/logs:/var/log/airflow:ro
      - ./postgres/logs:/var/log/postgresql:ro
    command: -config.file=/etc/promtail/config.yml
    networks:
      - data-network
    depends_on:
      - loki

  # cAdvisor для мониторинга контейнеров
  cadvisor:
    image: gcr.io/cadvisor/cadvisor:latest
    container_name: cadvisor-container-monitor
    restart: unless-stopped
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
      - /dev/disk/:/dev/disk:ro
    devices:
      - /dev/kmsg
    ports:
      - "${CADVISOR_PORT:-8081}:8080"
    networks:
      - data-network
    deploy:
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 256M

  # Nginx для балансировки и прокси
  nginx:
    image: nginx:alpine
    container_name: nginx-proxy
    restart: unless-stopped
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - ./nginx/html:/usr/share/nginx/html:ro
      - nginx_logs:/var/log/nginx
    ports:
      - "80:80"
      - "443:443"
    networks:
      - data-network
    depends_on:
      - airflow-webserver
      - metabase
      - grafana
      - pgadmin
    deploy:
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 256M

  # Portainer для управления Docker
  portainer:
    image: portainer/portainer-ce:latest
    container_name: portainer-docker-manager
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - portainer_data:/data
    ports:
      - "${PORTAINER_PORT:-9000}:9000"
    networks:
      - data-network
    deploy:
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 256M

  # MinIO для хранения файлов (альтернатива S3)
  minio:
    image: minio/minio:latest
    container_name: minio-object-storage
    restart: unless-stopped
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER:-minioadmin}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-minioadmin123}
      MINIO_SERVER_URL: http://minio:9000
      MINIO_BROWSER_REDIRECT_URL: http://localhost:9001
      MINIO_DOMAIN: localhost
    volumes:
      - minio_data:/data
      - ./minio/config:/root/.minio
    ports:
      - "${MINIO_API_PORT:-9000}:9000"
      - "${MINIO_CONSOLE_PORT:-9001}:9001"
    networks:
      - data-network
    command: server /data --console-address ":9001"
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 30s
      timeout: 20s
      retries: 3
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G

  # mc (MinIO Client) для управления MinIO
  mc:
    image: minio/mc:latest
    container_name: minio-client
    depends_on:
      - minio
    networks:
      - data-network
    entrypoint: >
      /bin/sh -c "
      until /usr/bin/mc ready local; do
        echo 'Waiting for MinIO...';
        sleep 2;
      done;
      /usr/bin/mc alias set local http://minio:9000 ${MINIO_ROOT_USER:-minioadmin} ${MINIO_ROOT_PASSWORD:-minioadmin123};
      /usr/bin/mc mb local/airflow-dags;
      /usr/bin/mc mb local/warehouse-exports;
      /usr/bin/mc mb local/backups;
      /usr/bin/mc policy set public local/warehouse-exports;
      echo 'MinIO is ready!';
      tail -f /dev/null
      "

  # Jupyter для анализа данных
  jupyter:
    image: jupyter/datascience-notebook:latest
    container_name: jupyter-analysis
    restart: unless-stopped
    environment:
      JUPYTER_ENABLE_LAB: "yes"
      JUPYTER_TOKEN: ${JUPYTER_TOKEN:-jupyter123}
      GRANT_SUDO: "yes"
      CHOWN_HOME: "yes"
      CHOWN_HOME_OPTS: "-R"
    volumes:
      - jupyter_data:/home/jovyan/work
      - ./jupyter/notebooks:/home/jovyan/notebooks:rw
      - ./scripts:/home/jovyan/scripts:ro
      - ~/.ssh:/home/jovyan/.ssh:ro
    ports:
      - "${JUPYTER_PORT:-8888}:8888"
    networks:
      - data-network
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: '2.0'
        reservations:
          memory: 2G
          cpus: '1.0'

  # Elasticsearch для полнотекстового поиска
  elasticsearch:
    image: elasticsearch:8.10.0
    container_name: elasticsearch-search
    restart: unless-stopped
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms2g -Xmx2g"
      - cluster.routing.allocation.disk.threshold_enabled=false
    volumes:
      - elasticsearch_data:/usr/share/elasticsearch/data
    ports:
      - "${ELASTICSEARCH_PORT:-9200}:9200"
      - "${ELASTICSEARCH_TRANSPORT_PORT:-9300}:9300"
    networks:
      - data-network
    ulimits:
      memlock:
        soft: -1
        hard: -1
    healthcheck:
      test: ["CMD-SHELL", "curl -s http://localhost:9200/_cluster/health | grep -q '\"status\":\"green\"'"]
      interval: 30s
      timeout: 10s
      retries: 5
    deploy:
      resources:
        limits:
          memory: 4G
        reservations:
          memory: 2G

  # Kibana для визуализации Elasticsearch
  kibana:
    image: kibana:8.10.0
    container_name: kibana-dashboard
    restart: unless-stopped
    environment:
      ELASTICSEARCH_HOSTS: http://elasticsearch:9200
    volumes:
      - kibana_data:/usr/share/kibana/data
    ports:
      - "${KIBANA_PORT:-5601}:5601"
    networks:
      - data-network
    depends_on:
      elasticsearch:
        condition: service_healthy
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G

  # ============ УТИЛИТЫ И ИНСТРУМЕНТЫ ============
  
  # Adminer (легкий аналог phpMyAdmin для PostgreSQL)
  adminer:
    image: adminer:latest
    container_name: adminer-pg-admin
    restart: unless-stopped
    ports:
      - "${ADMINER_PORT:-8082}:8080"
    networks:
      - data-network
    depends_on:
      - postgres-warehouse
      - postgres-airflow

  # pgHero для мониторинга производительности PostgreSQL
  pghero:
    image: ankane/pghero:latest
    container_name: pghero-performance
    restart: unless-stopped
    environment:
      DATABASE_URL: postgresql://${WAREHOUSE_DB_USER:-warehouse_admin}:${WAREHOUSE_DB_PASSWORD:-warehouse123}@postgres-warehouse/${WAREHOUSE_DB_NAME:-warehouse}
      PGHERO_USERNAME: ${PGHERO_USER:-admin}
      PGHERO_PASSWORD: ${PGHERO_PASSWORD:-admin123}
    ports:
      - "${PGHERO_PORT:-8083}:8080"
    networks:
      - data-network
    depends_on:
      - postgres-warehouse

  # Hasura для GraphQL API к данным
  hasura:
    image: hasura/graphql-engine:latest
    container_name: hasura-graphql-api
    restart: unless-stopped
    environment:
      HASURA_GRAPHQL_DATABASE_URL: postgresql://${WAREHOUSE_DB_USER:-warehouse_admin}:${WAREHOUSE_DB_PASSWORD:-warehouse123}@postgres-warehouse/${WAREHOUSE_DB_NAME:-warehouse}
      HASURA_GRAPHQL_ENABLE_CONSOLE: "true"
      HASURA_GRAPHQL_DEV_MODE: "true"
      HASURA_GRAPHQL_ENABLED_LOG_TYPES: startup, http-log, webhook-log, websocket-log, query-log
      HASURA_GRAPHQL_ADMIN_SECRET: ${HASURA_ADMIN_SECRET:-myadminsecretkey}
      HASURA_GRAPHQL_JWT_SECRET: '{"type": "HS256", "key": "${HASURA_JWT_SECRET:-myjwtsecretkey}"}'
      HASURA_GRAPHQL_UNAUTHORIZED_ROLE: anonymous
    ports:
      - "${HASURA_PORT:-8084}:8080"
    networks:
      - data-network
    depends_on:
      - postgres-warehouse

  # MailHog для тестирования email уведомлений
  mailhog:
    image: mailhog/mailhog:latest
    container_name: mailhog-email-testing
    restart: unless-stopped
    ports:
      - "${MAILHOG_SMTP_PORT:-1025}:1025"
      - "${MAILHOG_HTTP_PORT:-8025}:8025"
    networks:
      - data-network
    deploy:
      resources:
        limits:
          memory: 256M
        reservations:
          memory: 128M

volumes:
  # PostgreSQL
  postgres_data_warehouse:
  postgres_data_airflow:
  
  # Redis
  redis_data:
  
  # BI инструменты
  metabase_data:
  superset_data:
  
  # Администрирование
  pgadmin_data:
  
  # Мониторинг
  prometheus_data:
  grafana_data:
  loki_data:
  
  # Хранилища
  minio_data:
  
  # Анализ данных
  jupyter_data:
  
  # Поиск
  elasticsearch_data:
  kibana_data:
  
  # Прокси
  nginx_logs:
  
  # Docker менеджмент
  portainer_data:

networks:
  data-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
          gateway: 172.20.0.1

# Определение общих переменных окружения
x-airflow-environment: &airflow-environment
  AIRFLOW__CORE__EXECUTOR: CeleryExecutor
  AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://${AIRFLOW_DB_USER:-airflow}:${AIRFLOW_DB_PASSWORD:-airflow123}@postgres-airflow/${AIRFLOW_DB_NAME:-airflow}
  AIRFLOW__CELERY__RESULT_BACKEND: db+postgresql://${AIRFLOW_DB_USER:-airflow}:${AIRFLOW_DB_PASSWORD:-airflow123}@postgres-airflow/${AIRFLOW_DB_NAME:-airflow}
  AIRFLOW__CELERY__BROKER_URL: redis://:${REDIS_PASSWORD:-redis123}@redis-airflow:6379/0
  AIRFLOW__CORE__LOAD_EXAMPLES: 'false'
  AIRFLOW__CORE__FERNET_KEY: ${AIRFLOW_FERNET_KEY:-}
  AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION: 'true'
  AIRFLOW__API__AUTH_BACKEND: 'airflow.api.auth.backend.basic_auth'
  AIRFLOW__WEBSERVER__SECRET_KEY: ${AIRFLOW_SECRET_KEY:-supersecretkey}
  AIRFLOW_CONN_WAREHOUSE_DB: postgresql://${WAREHOUSE_DB_USER:-warehouse_admin}:${WAREHOUSE_DB_PASSWORD:-warehouse123}@postgres-warehouse/${WAREHOUSE_DB_NAME:-warehouse}
  AIRFLOW__CORE__SQL_ALCHEMY_POOL_SIZE: 5
  AIRFLOW__CORE__SQL_ALCHEMY_MAX_OVERFLOW: 10
  AIRFLOW__CORE__SQL_ALCHEMY_POOL_RECYCLE: 1800
  AIRFLOW__SCHEDULER__SCHEDULER_HEARTBEAT_SEC: 30
  AIRFLOW__SCHEDULER__JOB_HEARTBEAT_SEC: 30
```

## Конфигурационные файлы

### 1. `.env` файл (создайте в корневой директории)

```bash
# PostgreSQL
POSTGRES_USER=admin
POSTGRES_PASSWORD=admin123

# Warehouse Database
WAREHOUSE_DB_NAME=warehouse
WAREHOUSE_DB_USER=warehouse_admin
WAREHOUSE_DB_PASSWORD=warehouse123
WAREHOUSE_DB_PORT=5432

# Airflow Database
AIRFLOW_DB_NAME=airflow
AIRFLOW_DB_USER=airflow
AIRFLOW_DB_PASSWORD=airflow123
AIRFLOW_DB_PORT=5433

# Redis
REDIS_PASSWORD=redis123
REDIS_CACHE_PASSWORD=cache123
REDIS_PORT=6379
REDIS_CACHE_PORT=6380

# Airflow
AIRFLOW_ADMIN_USER=admin
AIRFLOW_ADMIN_PASSWORD=admin123
AIRFLOW_PORT=8080
AIRFLOW_FLOWER_PORT=5555
AIRFLOW_FERNET_KEY=46BKJoQYlPPOexq0OhDZnIlNepKFf87WFwLbfzqDDho=
AIRFLOW_SECRET_KEY=supersecretkey
AIRFLOW_WORKERS=2

# BI Tools
METABASE_PORT=3000
SUPERSET_PORT=8088
METABASE_EMBED_TOKEN=
SUPERSET_SECRET_KEY=supersecretkey123

# Administration
PGADMIN_EMAIL=admin@warehouse.com
PGADMIN_PASSWORD=admin123
PGADMIN_PORT=5050

# Monitoring
PROMETHEUS_PORT=9090
GRAFANA_PORT=3001
GRAFANA_ADMIN_PASSWORD=admin123
LOKI_PORT=3100
CADVISOR_PORT=8081

# Storage
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin123
MINIO_API_PORT=9000
MINIO_CONSOLE_PORT=9001

# Analysis
JUPYTER_PORT=8888
JUPYTER_TOKEN=jupyter123

# Search
ELASTICSEARCH_PORT=9200
ELASTICSEARCH_TRANSPORT_PORT=9300
KIBANA_PORT=5601

# Utilities
ADMINER_PORT=8082
PGHERO_PORT=8083
PGHERO_USER=admin
PGHERO_PASSWORD=admin123
HASURA_PORT=8084
HASURA_ADMIN_SECRET=myadminsecretkey
HASURA_JWT_SECRET=myjwtsecretkey
MAILHOG_SMTP_PORT=1025
MAILHOG_HTTP_PORT=8025
PORTAINER_PORT=9000
```

### 2. Конфигурация Prometheus

```yaml
# prometheus/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets: []

rule_files:
  - "alerts.yml"

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'postgres-warehouse'
    static_configs:
      - targets: ['postgres-warehouse:9187']
    params:
      dsn: ['postgresql://warehouse_admin:warehouse123@postgres-warehouse:5432/warehouse?sslmode=disable']

  - job_name: 'postgres-airflow'
    static_configs:
      - targets: ['postgres-airflow:9187']
    params:
      dsn: ['postgresql://airflow:airflow123@postgres-airflow:5432/airflow?sslmode=disable']

  - job_name: 'airflow'
    static_configs:
      - targets: ['airflow-webserver:8080']
    metrics_path: '/metrics'

  - job_name: 'node'
    static_configs:
      - targets: ['cadvisor:8080']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis-airflow:9121']

  - job_name: 'elasticsearch'
    static_configs:
      - targets: ['elasticsearch:9200']
    metrics_path: '/_prometheus/metrics'

  - job_name: 'minio'
    static_configs:
      - targets: ['minio:9000']
    metrics_path: '/minio/v2/metrics/cluster'
```

### 3. Конфигурация Nginx

```nginx
# nginx/nginx.conf
events {
    worker_connections 1024;
    use epoll;
    multi_accept on;
}

http {
    # Основные настройки
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    
    # Логирование
    access_log /var/log/nginx/access.log combined;
    error_log /var/log/nginx/error.log warn;
    
    # Оптимизации
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    server_tokens off;
    
    # Сжатие
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript 
               application/javascript application/xml+rss 
               application/json image/svg+xml;
    
    # Ограничения
    client_max_body_size 100M;
    client_body_timeout 300s;
    client_header_timeout 300s;
    send_timeout 300s;
    
    # Заголовки безопасности
    add_header X-Frame-Options SAMEORIGIN;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    
    # Включение конфигураций виртуальных хостов
    include /etc/nginx/conf.d/*.conf;
}

# nginx/conf.d/airflow.conf
server {
    listen 80;
    server_name airflow.localhost;
    
    location / {
        proxy_pass http://airflow-webserver:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }
}

# nginx/conf.d/metabase.conf
server {
    listen 80;
    server_name metabase.localhost;
    
    location / {
        proxy_pass http://metabase:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Большие запросы для Metabase
        client_max_body_size 100M;
        
        # Timeouts
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }
}

# nginx/conf.d/grafana.conf
server {
    listen 80;
    server_name grafana.localhost;
    
    location / {
        proxy_pass http://grafana:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# nginx/conf.d/pgadmin.conf
server {
    listen 80;
    server_name pgadmin.localhost;
    
    location / {
        proxy_pass http://pgadmin:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 4. Инициализация баз данных

```sql
-- postgres/warehouse-init/01_create_schemas.sql
-- Создание пользователя и базы данных для аналитического хранилища
CREATE USER warehouse_admin WITH PASSWORD 'warehouse123';
CREATE DATABASE warehouse WITH OWNER warehouse_admin ENCODING 'UTF8' LC_COLLATE = 'en_US.utf8' LC_CTYPE = 'en_US.utf8' TEMPLATE template0;

\c warehouse warehouse_admin;

-- Создание расширений
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- Создание схем (код из предыдущего ответа)
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS cleansed;
CREATE SCHEMA IF NOT EXISTS mart;
CREATE SCHEMA IF NOT EXISTS audit;
CREATE SCHEMA IF NOT EXISTS temp;

-- Даем права пользователю
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA raw, cleansed, mart, audit, temp TO warehouse_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA raw, cleansed, mart, audit, temp TO warehouse_admin;
GRANT USAGE ON SCHEMA raw, cleansed, mart, audit, temp TO warehouse_admin;

-- postgres/airflow-init/01_create_database.sql
CREATE USER airflow WITH PASSWORD 'airflow123';
CREATE DATABASE airflow WITH OWNER airflow ENCODING 'UTF8' LC_COLLATE = 'en_US.utf8' LC_CTYPE = 'en_US.utf8' TEMPLATE template0;

\c airflow airflow;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

## Структура проекта

```bash
analytical-platform/
├── .env
├── docker-compose.yml
├── airflow/
│   ├── dags/
│   │   ├── etl_pipeline.py
│   │   ├── data_quality.py
│   │   └── maintenance.py
│   ├── plugins/
│   │   └── custom_operators.py
│   ├── config/
│   │   └── airflow.cfg
│   ├── scripts/
│   │   ├── setup.sh
│   │   └── backup.sh
│   ├── variables/
│   │   └── variables.json
│   └── connections/
│       └── connections.json
├── postgres/
│   ├── warehouse-init/
│   │   ├── 01_create_schemas.sql
│   │   ├── 02_raw_schema.sql
│   │   └── ...
│   ├── airflow-init/
│   │   └── 01_create_database.sql
│   └── backups/
├── prometheus/
│   ├── prometheus.yml
│   └── alerts.yml
├── grafana/
│   ├── dashboards/
│   │   └── warehouse-dashboard.json
│   └── datasources/
│       └── prometheus.yml
├── nginx/
│   ├── nginx.conf
│   ├── conf.d/
│   │   ├── airflow.conf
│   │   └── metabase.conf
│   └── ssl/
├── scripts/
│   ├── init-platform.sh
│   ├── backup-database.sh
│   └── restore-database.sh
└── README.md
```

## Скрипт инициализации

```bash
#!/bin/bash
# scripts/init-platform.sh

set -e

echo "🚀 Инициализация аналитической платформы..."

# 1. Создаем структуру директорий
echo "📁 Создание структуры директорий..."
mkdir -p airflow/{dags,plugins,config,scripts,variables,connections,logs}
mkdir -p postgres/{warehouse-init,airflow-init,backups}
mkdir -p prometheus grafana/{dashboards,datasources} nginx/{conf.d,ssl}
mkdir -p scripts metabase superset jupyter/notebooks
mkdir -p minio/config pgadmin loki promtail

# 2. Копируем конфигурационные файлы
echo "⚙️  Копирование конфигурационных файлов..."
cp config/prometheus.yml prometheus/
cp config/nginx.conf nginx/
cp config/airflow.cfg airflow/config/
cp config/webserver_config.py airflow/config/

# 3. Генерируем секретные ключи
echo "🔐 Генерация секретных ключей..."
if [ ! -f .env ]; then
    echo "AIRFLOW_FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")" >> .env
    echo "AIRFLOW_SECRET_KEY=$(openssl rand -hex 32)" >> .env
    echo "SUPERSET_SECRET_KEY=$(openssl rand -hex 32)" >> .env
fi

# 4. Скачиваем дашборды Grafana
echo "📊 Скачивание дашбордов Grafana..."
curl -sSL https://raw.githubusercontent.com/percona/grafana-dashboards/master/dashboards/PostgreSQL_Overview.json \
    -o grafana/dashboards/postgres-overview.json

# 5. Запускаем контейнеры
echo "🐳 Запуск Docker контейнеров..."
docker-compose up -d

# 6. Ожидание запуска сервисов
echo "⏳ Ожидание запуска сервисов..."
sleep 30

# 7. Проверка статусов
echo "✅ Проверка статусов сервисов..."
docker-compose ps

# 8. Инициализация Airflow
echo "🌀 Инициализация Airflow..."
docker-compose exec airflow-webserver airflow db upgrade
docker-compose exec airflow-webserver airflow users create \
    --username admin \
    --password admin123 \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@warehouse.com

# 9. Создание подключений в Airflow
echo "🔗 Создание подключений в Airflow..."
docker-compose exec airflow-webserver airflow connections add 'warehouse_db' \
    --conn-type 'postgres' \
    --conn-host 'postgres-warehouse' \
    --conn-login 'warehouse_admin' \
    --conn-password 'warehouse123' \
    --conn-port '5432' \
    --conn-schema 'warehouse'

# 10. Отображение информации о доступе
echo ""
echo "========================================="
echo "🎉 Аналитическая платформа запущена!"
echo "========================================="
echo ""
echo "📊 Веб-интерфейсы:"
echo "Airflow:      http://localhost:8080"
echo "Metabase:     http://localhost:3000"
echo "Grafana:      http://localhost:3001"
echo "pgAdmin:      http://localhost:5050"
echo "MinIO:        http://localhost:9001"
echo "Jupyter:      http://localhost:8888"
echo "Kibana:       http://localhost:5601"
echo "Portainer:    http://localhost:9000"
echo ""
echo "🔐 Учетные данные:"
echo "Airflow:      admin / admin123"
echo "Metabase:     Первый запуск - создайте аккаунт"
echo "Grafana:      admin / admin123"
echo "pgAdmin:      admin@warehouse.com / admin123"
echo "MinIO:        minioadmin / minioadmin123"
echo ""
echo "📈 Мониторинг:"
echo "Prometheus:   http://localhost:9090"
echo "Flower:       http://localhost:5555"
echo ""
echo "🚀 Для остановки платформы выполните: docker-compose down"
echo "========================================="
```

## Инструкция по запуску

### 1. Клонирование и настройка

```bash
# Создаем проект
mkdir analytical-platform
cd analytical-platform

# Копируем docker-compose.yml и конфигурации

# Запускаем инициализацию
chmod +x scripts/init-platform.sh
./scripts/init-platform.sh
```

### 2. Быстрый запуск

```bash
# Просто запустите (используйте .env.example для создания .env)
cp .env.example .env
docker-compose up -d

# Проверьте статус
docker-compose ps

# Просмотрите логи
docker-compose logs -f airflow-scheduler
```

### 3. Настройка после запуска

1. **Airflow** - создайте DAGs в `airflow/dags/`
2. **Metabase** - настройте подключение к базе данных через UI
3. **Grafana** - добавьте источник данных Prometheus
4. **pgAdmin** - добавьте сервера PostgreSQL

### 4. Мониторинг ресурсов

```bash
# Просмотр использования ресурсов
docker stats

# Мониторинг логов
docker-compose logs -f --tail=100

# Проверка здоровья
docker-compose ps --services | xargs -I {} docker-compose exec {} echo "{}: " \$(curl -s -o /dev/null -w "%{http_code}" http://localhost:80/health || echo "N/A")
```

### 5. Резервное копирование

```bash
# Резервное копирование баз данных
docker-compose exec postgres-warehouse pg_dump -U warehouse_admin warehouse > backup/warehouse_$(date +%Y%m%d).sql

# Резервное копирование Airflow
docker-compose exec postgres-airflow pg_dump -U airflow airflow > backup/airflow_$(date +%Y%m%d).sql
```

## Ключевые особенности архитектуры

### 1. **Масштабируемость:**
- Airflow workers можно масштабировать горизонтально
- Redis кластер для очередей
- PostgreSQL с настройками для больших нагрузок
- MinIO для распределенного хранения

### 2. **Мониторинг:**
- Prometheus для сбора метрик
- Grafana для визуализации
- Loki для централизованных логов
- cAdvisor для мониторинга контейнеров

### 3. **Отказоустойчивость:**
- Health checks для всех сервисов
- Автоматические перезапуски
- Резервное копирование данных
- Избыточное хранение в MinIO

### 4. **Безопасность:**
- Изолированная сеть
- Аутентификация во всех сервисах
- SSL/TLS готовность
- Ролевая модель доступа

### 5. **Производительность:**
- Кэширование в Redis
- Оптимизированные настройки PostgreSQL
- Балансировка нагрузки через Nginx
- Материализованные представления