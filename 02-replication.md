# Репликация в PostgreSQL

## Оглавление
1. [Что такое репликация?](#что-такое-репликация)
2. [Зачем нужно реплицирование?](#зачем-нужно-реплицирование)
3. [Плюсы и минусы репликации](#плюсы-и-минусы-репликации)
4. [Типы репликации в PostgreSQL](#типы-репликации-в-postgresql)
5. [Настройка репликации в PostgreSQL](#настройка-репликации-в-postgresql)
6. [Примеры реализации](#примеры-реализации)
7. [Мониторинг и управление репликацией](#мониторинг-и-управление-репликацией)
8. [Лучшие практики и рекомендации](#лучшие-практики-и-рекомендации)
9. [Полезные ссылки по репликации в PostgreSQL](#полезные-ссылки-по-репликации-в-postgresql)

## Что такое репликация?

**Репликация** в PostgreSQL — это процесс автоматического копирования и поддержания данных с одного сервера базы данных (называемого primary или master) на одном или нескольких других серверах (называемых replica или standby). Это обеспечивает избыточность данных и повышает доступность системы.

### Ключевые концепции:

- **Primary/Master сервер** — основной сервер, который принимает запросы на запись и чтение
- **Replica/Standby сервер** — сервер, который получает копии данных с primary
- **WAL (Write-Ahead Log)** — журнал предзаписи, основа репликации в PostgreSQL
- **Синхронная репликация** — гарантирует, что данные записаны на replica до подтверждения операции
- **Асинхронная репликация** — подтверждение операции происходит до гарантированной записи на replica

## Зачем нужно реплицирование?

### Основные причины:

1. **Обеспечение отказоустойчивости**
   - Автоматическое переключение при сбое primary сервера
   - Минимизация времени простоя системы

2. **Масштабирование производительности**
   - Распределение нагрузки чтения между несколькими серверами
   - Улучшение отзывчивости для географически распределенных пользователей

3. **Резервное копирование и восстановление**
   - "Горячие" резервные копии без прерывания работы основной БД
   - Возможность тестирования на актуальных данных

4. **Аналитика и отчетность**
   - Выполнение тяжелых аналитических запросов на репликах
   - Изоляция операционной нагрузки от отчетной

### Типичные сценарии использования:
- Высоконагруженные веб-приложения
- Системы, требующие минимального времени простоя
- Географически распределенные приложения
- Аналитические платформы и системы отчетности

## Плюсы и минусы репликации

### Преимущества:

1. **Повышенная доступность** — автоматическое переключение при сбоях
2. **Улучшенная производительность чтения** — распределение нагрузки
3. **Географическое распределение** — данные ближе к пользователям
4. **Безопасность данных** — избыточное хранение информации
5. **Упрощение бэкапов** — резервное копирование с реплик

### Недостатки:

1. **Задержка репликации** — возможна рассинхронизация данных
2. **Накладные расходы** — дополнительное использование ресурсов сети и диска
3. **Сложность настройки** — требуется тщательное планирование
4. **Ограничения на запись** — только primary сервер принимает запросы на запись
5. **Конфликт разрешения** — возможные проблемы при переключении

## Типы репликации в PostgreSQL

### 1. Физическая репликация (Streaming Replication)
- Копирование бинарных данных WAL-файлов
- Низкоуровневое копирование на уровне блоков
- Минимальная задержка репликации
- Требует совместимости версий PostgreSQL

### 2. Логическая репликация (Logical Replication)
- Копирование изменений на уровне строк
- Возможность выборочной репликации таблиц
- Поддержка разных версий PostgreSQL
- Возможность преобразования данных

### 3. Синхронная vs Асинхронная репликация
- **Синхронная** — гарантирует сохранность данных, но может снижать производительность
- **Асинхронная** — higher performance, но возможна потеря данных при сбое

### 4. Каскадная репликация
- Реплики могут сами быть источниками для других реплик
- Уменьшает нагрузку на primary сервер
- Увеличивает задержку репликации для конечных реплик

## Настройка репликации в PostgreSQL

### Подход 1: Физическая репликация (Streaming Replication)

#### Настройка primary сервера:

1. **Изменение postgresql.conf**:
```ini
# Включение репликации
wal_level = replica

# Максимальное количество реплик
max_wal_senders = 10

# Объем WAL-файлов, сохраняемых для репликации
wal_keep_segments = 64

# Включение потоковой репликации
max_replication_slots = 10
```

2. **Настройка pg_hba.conf**:
```ini
# Разрешение подключения для репликации
host    replication     replicator      <replica_ip>/32        md5
```

3. **Создание пользователя для репликации**:
```sql
CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD 'secure_password';
```

4. **Создание слота репликации**:
```sql
SELECT * FROM pg_create_physical_replication_slot('replica_slot');
```

#### Настройка replica сервера:

1. **Остановка PostgreSQL и очистка данных**:
```bash
sudo systemctl stop postgresql
rm -rf /var/lib/postgresql/15/main/*
```

2. **Базовый бэкап с primary**:
```bash
pg_basebackup -h <primary_ip> -D /var/lib/postgresql/15/main/ -U replicator -P -v -R -X stream -S replica_slot
```

3. **Настройка recovery.conf (PostgreSQL 12+) через postgresql.auto.conf**:
```ini
primary_conninfo = 'host=<primary_ip> port=5432 user=replicator password=secure_password application_name=replica1'
primary_slot_name = 'replica_slot'
```

4. **Запуск PostgreSQL**:
```bash
sudo systemctl start postgresql
```

### Подход 2: Логическая репликация

#### Настройка публикации на primary:

```sql
-- Создание публикации для конкретных таблиц
CREATE PUBLICATION my_publication FOR TABLE users, orders, products;

-- Или для всех таблиц
CREATE PUBLICATION all_tables FOR ALL TABLES;
```

#### Настройка подписки на replica:

```sql
-- Создание подписки
CREATE SUBSCRIPTION my_subscription
CONNECTION 'host=<primary_ip> port=5432 dbname=mydb user=replicator password=secure_password'
PUBLICATION my_publication;
```

## Примеры реализации

### Пример 1: Мониторинг репликации

```sql
-- Проверка статуса репликации на primary
SELECT * FROM pg_stat_replication;

-- Проверка статуса на replica
SELECT * FROM pg_stat_wal_receiver;

-- Проверка задержки репликации
SELECT
    client_addr,
    application_name,
    state,
    write_lag,
    flush_lag,
    replay_lag
FROM pg_stat_replication;
```

### Пример 2: Переключение при сбое (Promote replica)

```bash
# На replica сервере
sudo systemctl stop postgresql

# Создание триггер-файла для активации replica как primary
touch /var/lib/postgresql/15/main/trigger_file

# Или использование pg_ctl
pg_ctl promote -D /var/lib/postgresql/15/main/

# Запуск PostgreSQL
sudo systemctl start postgresql
```

### Пример 3: Настройка синхронной репликации

```sql
-- На primary сервере
ALTER SYSTEM SET synchronous_commit = on;
ALTER SYSTEM SET synchronous_standby_names = 'replica1';

-- Перезагрузка конфигурации
SELECT pg_reload_conf();

-- Проверка синхронной репликации
SELECT application_name, sync_state FROM pg_stat_replication;
```

### Пример 4: Управление слотами репликации

```sql
-- Создание слота репликации
SELECT * FROM pg_create_physical_replication_slot('slot1');

-- Просмотр слотов репликации
SELECT * FROM pg_replication_slots;

-- Удаление слота репликации
SELECT pg_drop_replication_slot('slot1');
```

## Мониторинг и управление репликацией

### Ключевые метрики для мониторинга:

1. **Задержка репликации**:
```sql
SELECT
    pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS replay_lag_bytes,
    pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) / 1024 / 1024 AS replay_lag_mb
FROM pg_stat_replication;
```

2. **Статус репликации**:
```sql
SELECT
    application_name,
    state,
    sync_state,
    write_lag,
    flush_lag,
    replay_lag
FROM pg_stat_replication;
```

3. **Использование слотов репликации**:
```sql
SELECT
    slot_name,
    active,
    restart_lsn,
    confirmed_flush_lsn
FROM pg_replication_slots;
```

### Инструменты мониторинга:

1. **pgAdmin** — графический интерфейс для мониторинга репликации
2. **Patroni** — инструмент для управления репликацией и автоматического переключения
3. **pg_stat_replication view** — встроенное представление для мониторинга
4. **Custom scripts** — пользовательские скрипты для проверки состояния

## Лучшие практики и рекомендации

### 1. Планирование архитектуры
- Определите нужное количество реплик
- Выберите подходящий тип репликации (sync/async)
- Продумайте географическое распределение

### 2. Настройка производительности
```ini
# Оптимизация для репликации
max_wal_senders = 10
wal_keep_segments = 64
max_replication_slots = 10
synchronous_commit = remote_write
```

### 3. Безопасность
- Используйте SSL для соединений репликации
- Ограничьте доступ к порту репликации
- Регулярно обновляйте пароли репликации

### 4. Мониторинг и оповещения
- Настройте мониторинг задержки репликации
- Создайте алерты для сбоев репликации
- Регулярно проверяйте целостность данных

### 5. Резервное копирование и восстановление
- Регулярно тестируйте процесс переключения
- Создавайте резервные копии с реплик
- Документируйте процедуры аварийного восстановления

### 6. Обслуживание
- Регулярно обновляйте программное обеспечение
- Мониторьте использование дискового пространства
- Планируйте емкость для роста данных

## Заключение

Репликация в PostgreSQL — это мощный механизм, который обеспечивает отказоустойчивость, масштабируемость и высокую доступность данных. Выбор типа репликации зависит от конкретных требований вашего приложения:

- **Физическая репликация** — идеальна для обеспечения высокой доступности и аварийного восстановления
- **Логическая репликация** — подходит для выборочной репликации и обновления между разными версиями
- **Синхронная репликация** — обеспечивает максимальную надежность данных
- **Асинхронная репликация** — предлагает лучшую производительность

<a id="полезные-ссылки-по-репликации-в-postgresql"></a>
## Полезные ссылки по репликации в PostgreSQL

### Официальная документация
1. **[PostgreSQL Documentation: Replication](https://www.postgresql.org/docs/current/warm-standby.html)** — официальная документация по репликации
2. **[Logical Replication](https://www.postgresql.org/docs/current/logical-replication.html)** — руководство по логической репликации

### Практические руководства
3. **[How to Set Up Streaming Replication in PostgreSQL](https://www.percona.com/blog/how-to-set-up-streaming-replication-in-postgresql/)** — практическое руководство по настройке потоковой репликации
4. **[PostgreSQL Replication: The Complete Guide](https://www.enterprisedb.com/postgresql-replication-complete-guide)** — полное руководство по репликации от EDB

### Мониторинг и управление
5. **[Monitoring PostgreSQL Replication](https://pgmetrics.io/docs/replication/)** — руководство по мониторингу репликации
6. **[Patroni: PostgreSQL High Availability](https://patroni.readthedocs.io/)** — документация по Patroni для управления репликацией

### Best Practices
7. **[PostgreSQL Replication Best Practices](https://www.2ndquadrant.com/en/blog/postgresql-replication-best-practices/)** — лучшие практики от 2ndQuadrant
8. **[Disaster Recovery with PostgreSQL](https://info.crunchydata.com/blog/disaster-recovery-with-postgresql-streaming-replication)** — восстановление после сбоев с помощью репликации