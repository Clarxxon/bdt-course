# Шардирование в PostgreSQL

## Оглавление
1. [Что такое шардирование?](#что-такое-шардирование)
2. [Зачем нужно шардирование?](#зачем-нужно-шардирование)
3. [Плюсы и минусы шардирования](#плюсы-и-минусы-шардирования)
4. [Архитектурные подходы к шардированию](#архитектурные-подходы-к-шардированию)
5. [Настройка шардирования в PostgreSQL](#настройка-шардирования-в-postgresql)
6. [Примеры реализации](#примеры-реализации)
7. [Лучшие практики и рекомендации](#лучшие-практики-и-рекомендации)

## Что такое шардирование?

**Шардирование** (от англ. shard - осколок) - это метод горизонтального partitioning базы данных, при котором данные распределяются across multiple servers (шардов) на основе определенного ключа распределения. Каждый шард представляет собой независимую базу данных, содержащую подмножество общих данных.

### Ключевые концепции:

- **Шард** - отдельная база данных, хранящая часть данных
- **Ключ шардирования** - поле, по которому определяется принадлежность данных к шарду
- **Шард-контроллер** - компонент, отвечающий за маршрутизацию запросов
- **Горизонтальное масштабирование** - добавление новых серверов для увеличения мощности

## Зачем нужно шардирование?

### Основные причины:

1. **Масштабирование производительности**
   - Распределение нагрузки чтения/записи
   - Увеличение пропускной способности
   - Снижение задержек для географически распределенных пользователей

2. **Увеличение объема хранимых данных**
   - Преодоление ограничений single-node базы данных
   - Хранение петабайтов данных

3. **Повышение доступности и отказоустойчивости**
   - Изоляция отказов
   - Возможность обслуживания во время сбоев отдельных шардов

### Типичные сценарии использования:
- Системы с высокой нагрузкой (социальные сети, IoT)
- Большие объемы временных данных
- Мультитенантные приложения
- Географически распределенные системы

## Плюсы и минусы шардирования

### Преимущества:

1. **Горизонтальное масштабирование** - возможность добавлять новые шарды
2. **Улучшенная производительность** - параллельная обработка запросов
3. **Высокая доступность** - отказ одного шарда не влияет на всю систему
4. **Географическое распределение** - данные ближе к пользователям

### Недостатки:

1. **Сложность реализации** - требуется careful planning
2. **Операционные накладные расходы** - управление multiple databases
3. **Ограничения JOIN** - сложные межшардовые соединения
4. **Проблемы консистентности** - distributed transactions
5. **Миграция данных** - сложность rebalancing шардов

## Архитектурные подходы к шардированию

### 1. Key-based (Hash-based) Sharding
```sql
-- Пример: шардирование по хэшу user_id
shard_id = hash(user_id) % total_shards
```

### 2. Range-based Sharding
```sql
-- Пример: шардирование по диапазону дат
shard_id = determine_shard_by_date_range(created_at)
```

### 3. Directory-based Sharding
```sql
-- Использование lookup-таблицы для определения шарда
shard_id = lookup_shard_id(customer_id)
```

### 4. Geographic Sharding
```sql
-- Распределение по географическому признаку
shard_id = determine_shard_by_region(user_region)
```

## Настройка шардирования в PostgreSQL

PostgreSQL не имеет встроенной поддержки шардирования, но существует несколько подходов:

### Подход 1: Использование расширения Citus

**Citus** - популярное расширение для шардирования в PostgreSQL.

#### Установка и настройка:

1. **Установка Citus**:
```bash
# Для Ubuntu/Debian
sudo apt-get install postgresql-15-citus

# Добавление в shared_preload_libraries
echo "shared_preload_libraries = 'citus'" >> /etc/postgresql/15/main/postgresql.conf
```

2. **Создание coordinator и worker nodes**:
```sql
-- На coordinator node
SELECT * from master_add_node('worker1.example.com', 5432);
SELECT * from master_add_node('worker2.example.com', 5432);
SELECT * from master_add_node('worker3.example.com', 5432);
```

3. **Создание распределенной таблицы**:
```sql
-- Создание таблицы
CREATE TABLE events (
    event_id bigserial,
    user_id bigint,
    event_type text,
    created_at timestamptz
);

-- Преобразование в распределенную таблицу
SELECT create_distributed_table('events', 'user_id');

-- Автоматическое создание шардов
SELECT master_create_worker_shards('events', 16, 2);
```

### Подход 2: Ручная реализация с использованием таблиц-партиций и FDW

#### Шаг 1: Настройка Foreign Data Wrappers
```sql
-- Установка расширения
CREATE EXTENSION postgres_fdw;

-- Создание серверов для каждого шарда
CREATE SERVER shard1 FOREIGN DATA WRAPPER postgres_fdw 
OPTIONS (host 'shard1.example.com', dbname 'mydb', port '5432');

CREATE SERVER shard2 FOREIGN DATA WRAPPER postgres_fdw 
OPTIONS (host 'shard2.example.com', dbname 'mydb', port '5432');

-- Создание user mapping
CREATE USER MAPPING FOR current_user
SERVER shard1 OPTIONS (user 'postgres', password 'password');

CREATE USER MAPPING FOR current_user
SERVER shard2 OPTIONS (user 'postgres', password 'password');
```

#### Шаг 2: Создание распределенного представления
```sql
-- Создание foreign tables
CREATE FOREIGN TABLE events_shard1 (
    event_id bigint,
    user_id bigint,
    event_type text,
    created_at timestamptz
) SERVER shard1 OPTIONS (table_name 'events');

CREATE FOREIGN TABLE events_shard2 (
    event_id bigint,
    user_id bigint,
    event_type text,
    created_at timestamptz
) SERVER shard2 OPTIONS (table_name 'events');

-- Создание представления, объединяющего шарды
CREATE VIEW events AS
    SELECT * FROM events_shard1
    UNION ALL
    SELECT * FROM events_shard2;
```

#### Шаг 3: Реализация router функции
```sql
CREATE OR REPLACE FUNCTION insert_event(
    p_user_id bigint,
    p_event_type text,
    p_created_at timestamptz
) RETURNS void AS $$
DECLARE
    v_shard_id int;
BEGIN
    -- Определение шарда на основе user_id
    v_shard_id = abs(mod(p_user_id, 2)) + 1;
    
    -- Вставка в соответствующий шард
    IF v_shard_id = 1 THEN
        INSERT INTO events_shard1 (user_id, event_type, created_at)
        VALUES (p_user_id, p_event_type, p_created_at);
    ELSE
        INSERT INTO events_shard2 (user_id, event_type, p_created_at)
        VALUES (p_user_id, p_event_type, p_created_at);
    END IF;
END;
$$ LANGUAGE plpgsql;
```

### Подход 3: Использование прикладного шардирования

Реализация логики шардирования на уровне приложения:

```python
# Пример на Python
import psycopg2
from hashlib import md5

class ShardManager:
    def __init__(self, shards):
        self.shards = shards
        self.connections = {}
        
    def get_shard_connection(self, shard_key):
        shard_id = self.get_shard_id(shard_key)
        if shard_id not in self.connections:
            conn = psycopg2.connect(**self.shards[shard_id])
            self.connections[shard_id] = conn
        return self.connections[shard_id]
    
    def get_shard_id(self, shard_key):
        # Простой хэш-алгоритм для определения шарда
        hash_val = int(md5(str(shard_key).encode()).hexdigest(), 16)
        return hash_val % len(self.shards)

# Конфигурация шардов
shards_config = [
    {'host': 'shard1.example.com', 'dbname': 'mydb', 'user': 'postgres'},
    {'host': 'shard2.example.com', 'dbname': 'mydb', 'user': 'postgres'},
    {'host': 'shard3.example.com', 'dbname': 'mydb', 'user': 'postgres'}
]

shard_manager = ShardManager(shards_config)

# Использование в приложении
def save_event(user_id, event_type):
    conn = shard_manager.get_shard_connection(user_id)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO events (user_id, event_type) VALUES (%s, %s)",
            (user_id, event_type)
        )
    conn.commit()
```

## Примеры реализации

### Пример 1: Шардирование пользовательских данных

```sql
-- Создание таблицы пользователей на каждом шарде
CREATE TABLE users (
    user_id bigserial PRIMARY KEY,
    username varchar(50) NOT NULL,
    email varchar(100) NOT NULL,
    created_at timestamptz DEFAULT now()
);

-- Функция для определения шарда пользователя
CREATE OR REPLACE FUNCTION get_user_shard(user_id bigint)
RETURNS int AS $$
BEGIN
    RETURN (user_id % 4) + 1; -- 4 шарда
END;
$$ LANGUAGE plpgsql;

-- Таблица для mapping пользователей к шардам
CREATE TABLE user_shard_map (
    user_id bigint PRIMARY KEY,
    shard_id int NOT NULL,
    created_at timestamptz DEFAULT now()
);
```

### Пример 2: Межшардовые запросы с использованием Citus

```sql
-- Создание reference таблицы (реплицируется на все шарды)
CREATE TABLE countries (
    country_code char(2) PRIMARY KEY,
    country_name text NOT NULL
);

SELECT create_reference_table('countries');

-- Создание distributed таблицы
CREATE TABLE users (
    user_id bigserial,
    country_code char(2),
    name text,
    email text
);

SELECT create_distributed_table('users', 'country_code');

-- Выполнение запроса, который будет распределен по шардам
SELECT c.country_name, COUNT(*) as user_count
FROM users u
JOIN countries c ON u.country_code = c.country_code
GROUP BY c.country_name
ORDER BY user_count DESC;
```

### Пример 3: Миграция данных между шардами

```sql
-- Функция для миграции пользователя на другой шард
CREATE OR REPLACE FUNCTION migrate_user(
    p_user_id bigint,
    p_new_shard_id int
) RETURNS void AS $$
DECLARE
    v_old_shard_id int;
    v_user_data jsonb;
BEGIN
    -- Получение текущего шарда пользователя
    SELECT shard_id INTO v_old_shard_id
    FROM user_shard_map
    WHERE user_id = p_user_id;
    
    -- Если пользователь уже на нужном шарде
    IF v_old_shard_id = p_new_shard_id THEN
        RETURN;
    END IF;
    
    -- Получение данных пользователя со старого шарда
    -- (реализация зависит от вашей архитектуры)
    
    -- Вставка данных в новый шард
    -- (реализация зависит от вашей архитектуры)
    
    -- Обновление mapping таблицы
    UPDATE user_shard_map
    SET shard_id = p_new_shard_id
    WHERE user_id = p_user_id;
    
    -- Удаление данных со старого шарда
    -- (реализация зависит от вашей архитектуры)
    
    -- Коммит транзакции
    -- Важно: требуется distributed transaction coordination
END;
$$ LANGUAGE plpgsql;
```

## Лучшие практики и рекомендации

### 1. Выбор ключа шардирования
- Используйте ключ с равномерным распределением
- Избегайте hot spots - шардов с непропорциональной нагрузкой
- Учитывайте паттерны доступа к данным

### 2. Мониторинг и балансировка
```sql
-- Мониторинг распределения данных в Citus
SELECT * FROM citus_shards;
SELECT * FROM citus_shard_placement;

-- Мониторинг размера шардов
SELECT nodename, nodeport, shardid, pg_size_pretty(shard_size)
FROM citus_shards
ORDER BY shard_size DESC;
```

### 3. Резервное копирование и восстановление
- Реализуйте coordinated backup across shards
- Используйте point-in-time recovery для каждого шарда
- Тестируйте процедуры восстановления

### 4. Безопасность
- Настройте межшардовое шифрование
- Реализуйте единую аутентификацию
- Обеспечьте безопасность данных в движении

### 5. Производительность
- Используйте connection pooling
- Настройте индексы на каждом шарде
- Реализуйте кэширование часто запрашиваемых данных

### 6. Миграция и масштабирование
- Планируйте capacity заранее
- Реализуйте инструменты для rebalancing
- Тестируйте миграционные сценарии

## Заключение

Шардирование в PostgreSQL - это мощный, но сложный метод масштабирования, который требует тщательного планирования и реализации. Выбор подхода зависит от конкретных требований вашего приложения:

- **Citus** - оптимален для большинства случаев, предоставляет богатый функционал
- **FDW** - гибкое решение для custom-реализаций
- **Прикладное шардирование** - максимальный контроль, но высокая сложность

Помните, что шардирование добавляет значительную сложность в систему, поэтому используйте его только когда действительно необходимо горизонтальное масштабирование beyond the capabilities of a single PostgreSQL instance.

Перед внедрением шардирования рассмотрите альтернативы:
- Вертикальное масштабирование (более мощный сервер)
- Репликация для чтения
- Оптимизация запросов и индексов
- Архитектурные изменения приложения