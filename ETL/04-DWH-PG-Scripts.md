# Код схем данных для PostgreSQL

```sql
-- 01_create_schemas.sql
-- Создание схем для аналитического хранилища

-- Удаление существующих схем (осторожно!)
-- DROP SCHEMA IF EXISTS raw CASCADE;
-- DROP SCHEMA IF EXISTS cleansed CASCADE;
-- DROP SCHEMA IF EXISTS mart CASCADE;
-- DROP SCHEMA IF EXISTS audit CASCADE;
-- DROP SCHEMA IF EXISTS temp CASCADE;

-- Создание схем
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS cleansed;
CREATE SCHEMA IF NOT EXISTS mart;
CREATE SCHEMA IF NOT EXISTS audit;
CREATE SCHEMA IF NOT EXISTS temp;

-- Установка поиска путей для удобства
SET search_path TO public, raw, cleansed, mart, audit, temp;

-- 02_raw_schema.sql
-- Создание таблиц в схеме raw (сырые данные)

CREATE TABLE IF NOT EXISTS raw.stg_users (
    id BIGSERIAL PRIMARY KEY,
    raw_data JSONB NOT NULL,
    loaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source_system VARCHAR(50) NOT NULL,
    load_id VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Индексы для производительности
    CONSTRAINT chk_raw_data_not_empty CHECK (raw_data::text != '{}'::text)
);

CREATE TABLE IF NOT EXISTS raw.stg_orders (
    id BIGSERIAL PRIMARY KEY,
    raw_data JSONB NOT NULL,
    loaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source_system VARCHAR(50) NOT NULL,
    load_id VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw.stg_products (
    id BIGSERIAL PRIMARY KEY,
    raw_data JSONB NOT NULL,
    loaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source_system VARCHAR(50) NOT NULL,
    load_id VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw.stg_payments (
    id BIGSERIAL PRIMARY KEY,
    raw_data JSONB NOT NULL,
    loaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source_system VARCHAR(50) NOT NULL,
    load_id VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для raw схемы
CREATE INDEX IF NOT EXISTS idx_raw_stg_users_load_id ON raw.stg_users(load_id);
CREATE INDEX IF NOT EXISTS idx_raw_stg_users_source ON raw.stg_users(source_system);
CREATE INDEX IF NOT EXISTS idx_raw_stg_users_loaded ON raw.stg_users(loaded_at);

CREATE INDEX IF NOT EXISTS idx_raw_stg_orders_load_id ON raw.stg_orders(load_id);
CREATE INDEX IF NOT EXISTS idx_raw_stg_orders_loaded ON raw.stg_orders(loaded_at);

CREATE INDEX IF NOT EXISTS idx_raw_stg_products_load_id ON raw.stg_products(load_id);
CREATE INDEX IF NOT EXISTS idx_raw_stg_products_loaded ON raw.stg_products(loaded_at);

CREATE INDEX IF NOT EXISTS idx_raw_stg_payments_load_id ON raw.stg_payments(load_id);
CREATE INDEX IF NOT EXISTS idx_raw_stg_payments_loaded ON raw.stg_payments(loaded_at);

-- GIN индексы для полнотекстового поиска в JSONB
CREATE INDEX IF NOT EXISTS idx_raw_stg_users_data_gin ON raw.stg_users USING GIN (raw_data);
CREATE INDEX IF NOT EXISTS idx_raw_stg_orders_data_gin ON raw.stg_orders USING GIN (raw_data);
CREATE INDEX IF NOT EXISTS idx_raw_stg_products_data_gin ON raw.stg_products USING GIN (raw_data);
CREATE INDEX IF NOT EXISTS idx_raw_stg_payments_data_gin ON raw.stg_payments USING GIN (raw_data);

-- 03_cleansed_schema.sql
-- Создание таблиц в схеме cleansed (очищенные данные)

-- Таблица пользователей (SCD Type 2 - отслеживание истории изменений)
CREATE TABLE IF NOT EXISTS cleansed.dim_users (
    user_id BIGINT PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    date_of_birth DATE,
    country VARCHAR(100),
    subscription_tier VARCHAR(50),
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL DEFAULT '9999-12-31',
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Ограничения
    CONSTRAINT chk_valid_dates CHECK (valid_from <= valid_to),
    CONSTRAINT chk_email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

-- Таблица продуктов
CREATE TABLE IF NOT EXISTS cleansed.dim_products (
    product_id BIGINT PRIMARY KEY,
    sku VARCHAR(100) UNIQUE NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    price DECIMAL(10,2) NOT NULL CHECK (price >= 0),
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Ограничения
    CONSTRAINT chk_status CHECK (status IN ('active', 'inactive', 'discontinued', 'out_of_stock'))
);

-- Таблица дат (справочник дат)
CREATE TABLE IF NOT EXISTS cleansed.dim_dates (
    date_id DATE PRIMARY KEY,
    year INTEGER NOT NULL CHECK (year BETWEEN 2000 AND 2100),
    quarter INTEGER NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    week INTEGER NOT NULL CHECK (week BETWEEN 1 AND 53),
    day_of_year INTEGER NOT NULL CHECK (day_of_year BETWEEN 1 AND 366),
    day_of_month INTEGER NOT NULL CHECK (day_of_month BETWEEN 1 AND 31),
    day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
    is_weekend BOOLEAN NOT NULL DEFAULT FALSE,
    is_holiday BOOLEAN NOT NULL DEFAULT FALSE,
    holiday_name VARCHAR(100),
    
    -- Дополнительные вычисляемые поля
    month_name VARCHAR(20) GENERATED ALWAYS AS (
        CASE month
            WHEN 1 THEN 'January' WHEN 2 THEN 'February' WHEN 3 THEN 'March'
            WHEN 4 THEN 'April' WHEN 5 THEN 'May' WHEN 6 THEN 'June'
            WHEN 7 THEN 'July' WHEN 8 THEN 'August' WHEN 9 THEN 'September'
            WHEN 10 THEN 'October' WHEN 11 THEN 'November' WHEN 12 THEN 'December'
        END
    ) STORED,
    
    quarter_name VARCHAR(10) GENERATED ALWAYS AS (
        'Q' || quarter
    ) STORED,
    
    day_name VARCHAR(10) GENERATED ALWAYS AS (
        CASE day_of_week
            WHEN 1 THEN 'Monday' WHEN 2 THEN 'Tuesday' WHEN 3 THEN 'Wednesday'
            WHEN 4 THEN 'Thursday' WHEN 5 THEN 'Friday' WHEN 6 THEN 'Saturday'
            WHEN 7 THEN 'Sunday'
        END
    ) STORED
);

-- Фактовая таблица заказов (партиционированная по месяцам)
CREATE TABLE IF NOT EXISTS cleansed.fact_orders (
    order_id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    order_date DATE NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price DECIMAL(10,2) NOT NULL CHECK (unit_price >= 0),
    total_amount DECIMAL(10,2) NOT NULL CHECK (total_amount >= 0),
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Внешние ключи
    CONSTRAINT fk_fact_orders_user FOREIGN KEY (user_id) 
        REFERENCES cleansed.dim_users(user_id),
    CONSTRAINT fk_fact_orders_product FOREIGN KEY (product_id) 
        REFERENCES cleansed.dim_products(product_id),
    CONSTRAINT fk_fact_orders_date FOREIGN KEY (order_date) 
        REFERENCES cleansed.dim_dates(date_id),
    
    -- Бизнес-правила
    CONSTRAINT chk_total_amount CHECK (total_amount = quantity * unit_price),
    CONSTRAINT chk_status_values CHECK (status IN ('pending', 'processing', 'shipped', 'delivered', 'cancelled'))
) PARTITION BY RANGE (order_date);

-- Фактовая таблица платежей
CREATE TABLE IF NOT EXISTS cleansed.fact_payments (
    payment_id BIGINT PRIMARY KEY,
    order_id BIGINT NOT NULL,
    payment_date DATE NOT NULL,
    amount DECIMAL(10,2) NOT NULL CHECK (amount > 0),
    payment_method VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    
    -- Внешние ключи
    CONSTRAINT fk_fact_payments_order FOREIGN KEY (order_id) 
        REFERENCES cleansed.fact_orders(order_id),
    CONSTRAINT fk_fact_payments_date FOREIGN KEY (payment_date) 
        REFERENCES cleansed.dim_dates(date_id),
    
    -- Бизнес-правила
    CONSTRAINT chk_payment_method CHECK (payment_method IN ('credit_card', 'debit_card', 'paypal', 'bank_transfer', 'cash')),
    CONSTRAINT chk_payment_status CHECK (status IN ('pending', 'completed', 'failed', 'refunded')),
    CONSTRAINT chk_processed_date CHECK (processed_at IS NULL OR processed_at >= created_at)
);

-- Индексы для cleansed схемы
CREATE INDEX IF NOT EXISTS idx_dim_users_current ON cleansed.dim_users(is_current);
CREATE INDEX IF NOT EXISTS idx_dim_users_email ON cleansed.dim_users(email);
CREATE INDEX IF NOT EXISTS idx_dim_users_country ON cleansed.dim_users(country);
CREATE INDEX IF NOT EXISTS idx_dim_users_valid_dates ON cleansed.dim_users(valid_from, valid_to);

CREATE INDEX IF NOT EXISTS idx_dim_products_category ON cleansed.dim_products(category);
CREATE INDEX IF NOT EXISTS idx_dim_products_status ON cleansed.dim_products(status);
CREATE INDEX IF NOT EXISTS idx_dim_products_price ON cleansed.dim_products(price);

CREATE INDEX IF NOT EXISTS idx_dim_dates_year_month ON cleansed.dim_dates(year, month);
CREATE INDEX IF NOT EXISTS idx_dim_dates_holiday ON cleansed.dim_dates(is_holiday);
CREATE INDEX IF NOT EXISTS idx_dim_dates_weekend ON cleansed.dim_dates(is_weekend);

-- Создадим базовую партицию для fact_orders (остальные создадим позже)
CREATE TABLE IF NOT EXISTS cleansed.fact_orders_default PARTITION OF cleansed.fact_orders DEFAULT;

-- Индексы для фактовых таблиц
CREATE INDEX IF NOT EXISTS idx_fact_orders_date ON cleansed.fact_orders(order_date);
CREATE INDEX IF NOT EXISTS idx_fact_orders_user ON cleansed.fact_orders(user_id);
CREATE INDEX IF NOT EXISTS idx_fact_orders_product ON cleansed.fact_orders(product_id);
CREATE INDEX IF NOT EXISTS idx_fact_orders_status ON cleansed.fact_orders(status);

CREATE INDEX IF NOT EXISTS idx_fact_payments_date ON cleansed.fact_payments(payment_date);
CREATE INDEX IF NOT EXISTS idx_fact_payments_order ON cleansed.fact_payments(order_id);
CREATE INDEX IF NOT EXISTS idx_fact_payments_method ON cleansed.fact_payments(payment_method);
CREATE INDEX IF NOT EXISTS idx_fact_payments_status ON cleansed.fact_payments(status);

-- 04_mart_schema.sql
-- Создание таблиц в схеме mart (витрины данных)

-- Витрина продаж
CREATE TABLE IF NOT EXISTS mart.sales_mart (
    sale_date DATE NOT NULL,
    product_category VARCHAR(100) NOT NULL,
    user_country VARCHAR(100) NOT NULL,
    total_orders INTEGER NOT NULL DEFAULT 0,
    total_revenue DECIMAL(15,2) NOT NULL DEFAULT 0,
    avg_order_value DECIMAL(10,2) NOT NULL DEFAULT 0,
    unique_customers INTEGER NOT NULL DEFAULT 0,
    revenue_per_customer DECIMAL(10,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (sale_date, product_category, user_country),
    
    -- Ограничения
    CONSTRAINT chk_positive_values CHECK (
        total_orders >= 0 AND 
        total_revenue >= 0 AND 
        avg_order_value >= 0 AND 
        unique_customers >= 0 AND 
        revenue_per_customer >= 0
    )
);

-- Витрина клиентов
CREATE TABLE IF NOT EXISTS mart.customer_mart (
    user_id BIGINT PRIMARY KEY,
    first_order_date DATE,
    last_order_date DATE,
    total_orders INTEGER NOT NULL DEFAULT 0,
    total_spent DECIMAL(15,2) NOT NULL DEFAULT 0,
    days_since_last_order INTEGER,
    customer_segment VARCHAR(50) NOT NULL,
    clv_30d DECIMAL(10,2),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Внешний ключ
    CONSTRAINT fk_customer_mart_user FOREIGN KEY (user_id) 
        REFERENCES cleansed.dim_users(user_id),
    
    -- Ограничения
    CONSTRAINT chk_dates_order CHECK (first_order_date <= last_order_date OR last_order_date IS NULL),
    CONSTRAINT chk_segment_values CHECK (customer_segment IN ('new', 'regular', 'vip', 'churned')),
    CONSTRAINT chk_positive_metrics CHECK (total_orders >= 0 AND total_spent >= 0)
);

-- Витрина инвентаря (денормализованная)
CREATE TABLE IF NOT EXISTS mart.inventory_mart (
    product_id BIGINT PRIMARY KEY,
    sku VARCHAR(100) NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    price DECIMAL(10,2) NOT NULL,
    status VARCHAR(50) NOT NULL,
    total_orders BIGINT NOT NULL DEFAULT 0,
    total_quantity_sold BIGINT NOT NULL DEFAULT 0,
    total_revenue DECIMAL(15,2) NOT NULL DEFAULT 0,
    avg_order_value DECIMAL(10,2),
    days_since_last_sale INTEGER,
    stock_level INTEGER,
    reorder_point INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Внешний ключ
    CONSTRAINT fk_inventory_mart_product FOREIGN KEY (product_id) 
        REFERENCES cleansed.dim_products(product_id)
);

-- Материализованное представление для быстрых агрегаций
CREATE MATERIALIZED VIEW IF NOT EXISTS mart.daily_sales_summary AS
SELECT 
    order_date as sale_date,
    COUNT(DISTINCT order_id) as total_orders,
    COUNT(DISTINCT user_id) as unique_customers,
    SUM(total_amount) as total_revenue,
    AVG(total_amount) as avg_order_value,
    SUM(quantity) as total_items_sold
FROM cleansed.fact_orders
GROUP BY order_date
WITH DATA;

-- Индексы для mart схемы
CREATE INDEX IF NOT EXISTS idx_sales_mart_date ON mart.sales_mart(sale_date);
CREATE INDEX IF NOT EXISTS idx_sales_mart_category ON mart.sales_mart(product_category);
CREATE INDEX IF NOT EXISTS idx_sales_mart_country ON mart.sales_mart(user_country);

CREATE INDEX IF NOT EXISTS idx_customer_mart_segment ON mart.customer_mart(customer_segment);
CREATE INDEX IF NOT EXISTS idx_customer_mart_last_order ON mart.customer_mart(last_order_date);
CREATE INDEX IF NOT EXISTS idx_customer_mart_total_spent ON mart.customer_mart(total_spent);

CREATE INDEX IF NOT EXISTS idx_inventory_mart_category ON mart.inventory_mart(category);
CREATE INDEX IF NOT EXISTS idx_inventory_mart_status ON mart.inventory_mart(status);
CREATE INDEX IF NOT EXISTS idx_inventory_mart_revenue ON mart.inventory_mart(total_revenue DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_daily_sales_summary_date ON mart.daily_sales_summary(sale_date);

-- 05_audit_schema.sql
-- Создание таблиц в схеме audit (аудит и мониторинг)

-- Логи выполнения ETL процессов
CREATE TABLE IF NOT EXISTS audit.etl_logs (
    log_id BIGSERIAL PRIMARY KEY,
    dag_id VARCHAR(255) NOT NULL,
    task_id VARCHAR(255) NOT NULL,
    execution_date TIMESTAMP NOT NULL,
    status VARCHAR(50) NOT NULL,
    records_processed INTEGER,
    duration_seconds INTEGER,
    error_message TEXT,
    stack_trace TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Индексы
    INDEX idx_etl_logs_dag_task (dag_id, task_id),
    INDEX idx_etl_logs_execution_date (execution_date DESC),
    INDEX idx_etl_logs_status (status),
    
    -- Ограничения
    CONSTRAINT chk_etl_status CHECK (status IN ('success', 'failed', 'running', 'skipped'))
);

-- Проверки качества данных
CREATE TABLE IF NOT EXISTS audit.data_quality (
    check_id BIGSERIAL PRIMARY KEY,
    check_date DATE NOT NULL,
    check_name VARCHAR(100) NOT NULL,
    table_name VARCHAR(255) NOT NULL,
    column_name VARCHAR(255),
    expected_value VARCHAR(255),
    actual_value VARCHAR(255),
    status VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'warning',
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Индексы
    INDEX idx_data_quality_date (check_date DESC),
    INDEX idx_data_quality_table (table_name),
    INDEX idx_data_quality_status (status),
    INDEX idx_data_quality_severity (severity),
    
    -- Ограничения
    CONSTRAINT chk_quality_status CHECK (status IN ('passed', 'failed', 'warning')),
    CONSTRAINT chk_severity_level CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info'))
);

-- Линейность данных (data lineage)
CREATE TABLE IF NOT EXISTS audit.data_lineage (
    lineage_id BIGSERIAL PRIMARY KEY,
    source_schema VARCHAR(100) NOT NULL,
    source_table VARCHAR(255) NOT NULL,
    source_column VARCHAR(255) NOT NULL,
    target_schema VARCHAR(100) NOT NULL,
    target_table VARCHAR(255) NOT NULL,
    target_column VARCHAR(255) NOT NULL,
    transformation_type VARCHAR(100),
    transformation_logic TEXT,
    last_execution TIMESTAMP,
    last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Индексы
    INDEX idx_lineage_source (source_schema, source_table),
    INDEX idx_lineage_target (target_schema, target_table),
    INDEX idx_lineage_last_execution (last_execution DESC),
    
    -- Ограничения
    CONSTRAINT uniq_lineage UNIQUE (
        source_schema, source_table, source_column,
        target_schema, target_table, target_column
    )
);

-- Мониторинг производительности
CREATE TABLE IF NOT EXISTS audit.performance_metrics (
    metric_id BIGSERIAL PRIMARY KEY,
    metric_name VARCHAR(100) NOT NULL,
    metric_value NUMERIC NOT NULL,
    metric_unit VARCHAR(50),
    collection_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    tags JSONB,
    
    -- Индексы
    INDEX idx_performance_name_time (metric_name, collection_time DESC),
    INDEX idx_performance_tags_gin USING GIN (tags)
);

-- 06_temp_schema.sql
-- Создание таблиц в схеме temp (временные таблицы)

-- Временная таблица для промежуточных данных
CREATE TABLE IF NOT EXISTS temp.staging (
    id BIGSERIAL PRIMARY KEY,
    table_name VARCHAR(255) NOT NULL,
    data JSONB NOT NULL,
    operation VARCHAR(20) NOT NULL DEFAULT 'insert',
    processed BOOLEAN NOT NULL DEFAULT FALSE,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    
    -- Индексы
    INDEX idx_staging_table (table_name),
    INDEX idx_staging_processed (processed),
    INDEX idx_staging_created (created_at DESC),
    
    -- Ограничения
    CONSTRAINT chk_operation_type CHECK (operation IN ('insert', 'update', 'delete', 'merge'))
);

-- Временная таблица для агрегаций
CREATE TABLE IF NOT EXISTS temp.aggregations (
    id BIGSERIAL PRIMARY KEY,
    aggregation_name VARCHAR(255) NOT NULL,
    aggregation_key VARCHAR(500) NOT NULL,
    aggregation_value JSONB NOT NULL,
    computed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL DEFAULT (CURRENT_TIMESTAMP + INTERVAL '1 day'),
    
    -- Индексы
    INDEX idx_aggregations_name_key (aggregation_name, aggregation_key),
    INDEX idx_aggregations_expires (expires_at),
    
    -- Ограничение уникальности
    CONSTRAINT uniq_aggregation UNIQUE (aggregation_name, aggregation_key)
);

-- Временная таблица для обработки ошибок
CREATE TABLE IF NOT EXISTS temp.error_queue (
    error_id BIGSERIAL PRIMARY KEY,
    source_table VARCHAR(255) NOT NULL,
    error_type VARCHAR(100) NOT NULL,
    error_data JSONB NOT NULL,
    error_message TEXT NOT NULL,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    next_retry_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    
    -- Индексы
    INDEX idx_error_queue_type (error_type),
    INDEX idx_error_queue_retry (next_retry_at),
    INDEX idx_error_queue_resolved (resolved_at),
    
    -- Ограничения
    CONSTRAINT chk_retry_count CHECK (retry_count <= max_retries)
);

-- 07_functions_and_triggers.sql
-- Создание функций и триггеров

-- Функция для автоматического обновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Триггеры для обновления updated_at
CREATE TRIGGER update_dim_users_updated_at
    BEFORE UPDATE ON cleansed.dim_users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_dim_products_updated_at
    BEFORE UPDATE ON cleansed.dim_products
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_fact_orders_updated_at
    BEFORE UPDATE ON cleansed.fact_orders
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_sales_mart_updated_at
    BEFORE UPDATE ON mart.sales_mart
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_customer_mart_updated_at
    BEFORE UPDATE ON mart.customer_mart
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Функция для создания партиций fact_orders
CREATE OR REPLACE FUNCTION create_fact_orders_partition(partition_date DATE)
RETURNS VOID AS $$
DECLARE
    partition_name TEXT;
    start_date DATE;
    end_date DATE;
BEGIN
    -- Определяем начало месяца
    start_date := DATE_TRUNC('month', partition_date);
    -- Определяем конец месяца
    end_date := start_date + INTERVAL '1 month';
    
    -- Формируем имя партиции
    partition_name := 'fact_orders_' || 
                      EXTRACT(YEAR FROM start_date) || '_' || 
                      LPAD(EXTRACT(MONTH FROM start_date)::TEXT, 2, '0');
    
    -- Проверяем, существует ли уже партиция
    IF NOT EXISTS (
        SELECT 1 FROM pg_tables 
        WHERE schemaname = 'cleansed' 
        AND tablename = partition_name
    ) THEN
        -- Создаем партицию
        EXECUTE format('
            CREATE TABLE cleansed.%I PARTITION OF cleansed.fact_orders
            FOR VALUES FROM (%L) TO (%L)
        ', partition_name, start_date, end_date);
        
        -- Создаем индексы для партиции
        EXECUTE format('
            CREATE INDEX idx_%s_date ON cleansed.%I(order_date)
        ', partition_name, partition_name);
        
        EXECUTE format('
            CREATE INDEX idx_%s_user ON cleansed.%I(user_id)
        ', partition_name, partition_name);
        
        RAISE NOTICE 'Создана партиция: cleansed.%', partition_name;
    ELSE
        RAISE NOTICE 'Партиция cleansed.% уже существует', partition_name;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Функция для заполнения таблицы дат
CREATE OR REPLACE FUNCTION populate_dim_dates(start_date DATE, end_date DATE)
RETURNS INTEGER AS $$
DECLARE
    current_date DATE := start_date;
    inserted_count INTEGER := 0;
BEGIN
    WHILE current_date <= end_date LOOP
        INSERT INTO cleansed.dim_dates (
            date_id, year, quarter, month, week,
            day_of_year, day_of_month, day_of_week,
            is_weekend, is_holiday
        ) VALUES (
            current_date,
            EXTRACT(YEAR FROM current_date),
            EXTRACT(QUARTER FROM current_date),
            EXTRACT(MONTH FROM current_date),
            EXTRACT(WEEK FROM current_date),
            EXTRACT(DOY FROM current_date),
            EXTRACT(DAY FROM current_date),
            EXTRACT(ISODOW FROM current_date),
            EXTRACT(ISODOW FROM current_date) IN (6, 7),
            FALSE -- По умолчанию не праздник, можно дополнить
        )
        ON CONFLICT (date_id) DO NOTHING;
        
        IF FOUND THEN
            inserted_count := inserted_count + 1;
        END IF;
        
        current_date := current_date + INTERVAL '1 day';
    END LOOP;
    
    RETURN inserted_count;
END;
$$ LANGUAGE plpgsql;

-- Функция для очистки старых данных в raw схеме
CREATE OR REPLACE FUNCTION cleanup_raw_data(retention_days INTEGER DEFAULT 90)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER := 0;
BEGIN
    DELETE FROM raw.stg_users 
    WHERE loaded_at < CURRENT_TIMESTAMP - (retention_days || ' days')::INTERVAL;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    DELETE FROM raw.stg_orders 
    WHERE loaded_at < CURRENT_TIMESTAMP - (retention_days || ' days')::INTERVAL;
    
    GET DIAGNOSTICS deleted_count = deleted_count + ROW_COUNT;
    
    DELETE FROM raw.stg_products 
    WHERE loaded_at < CURRENT_TIMESTAMP - (retention_days || ' days')::INTERVAL;
    
    GET DIAGNOSTICS deleted_count = deleted_count + ROW_COUNT;
    
    DELETE FROM raw.stg_payments 
    WHERE loaded_at < CURRENT_TIMESTAMP - (retention_days || ' days')::INTERVAL;
    
    GET DIAGNOSTICS deleted_count = deleted_count + ROW_COUNT;
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- 08_views.sql
-- Создание представлений для удобства работы

-- Представление для сырых данных пользователей
CREATE OR REPLACE VIEW vw_raw_users AS
SELECT 
    id,
    raw_data->>'id' as user_id,
    raw_data->>'email' as email,
    raw_data->>'full_name' as full_name,
    raw_data->>'date_of_birth' as date_of_birth,
    raw_data->>'country' as country,
    raw_data->>'subscription_tier' as subscription_tier,
    raw_data->>'created_at' as created_at_raw,
    raw_data->>'updated_at' as updated_at_raw,
    loaded_at,
    source_system,
    load_id,
    created_at as record_created_at
FROM raw.stg_users;

-- Представление для текущих пользователей
CREATE OR REPLACE VIEW vw_current_users AS
SELECT 
    user_id,
    email,
    full_name,
    date_of_birth,
    country,
    subscription_tier,
    valid_from,
    valid_to,
    created_at,
    updated_at
FROM cleansed.dim_users
WHERE is_current = TRUE;

-- Представление для ежедневных продаж
CREATE OR REPLACE VIEW vw_daily_sales AS
SELECT 
    fo.order_date,
    dd.day_name,
    dd.is_weekend,
    COUNT(DISTINCT fo.order_id) as total_orders,
    COUNT(DISTINCT fo.user_id) as unique_customers,
    SUM(fo.total_amount) as total_revenue,
    AVG(fo.total_amount) as avg_order_value,
    SUM(fo.quantity) as total_items_sold
FROM cleansed.fact_orders fo
JOIN cleansed.dim_dates dd ON fo.order_date = dd.date_id
GROUP BY fo.order_date, dd.day_name, dd.is_weekend
ORDER BY fo.order_date DESC;

-- Представление для топ продуктов
CREATE OR REPLACE VIEW vw_top_products AS
SELECT 
    dp.product_id,
    dp.sku,
    dp.product_name,
    dp.category,
    dp.price,
    COUNT(DISTINCT fo.order_id) as total_orders,
    SUM(fo.quantity) as total_quantity_sold,
    SUM(fo.total_amount) as total_revenue,
    RANK() OVER (ORDER BY SUM(fo.total_amount) DESC) as revenue_rank
FROM cleansed.dim_products dp
LEFT JOIN cleansed.fact_orders fo ON dp.product_id = fo.product_id
WHERE dp.status = 'active'
GROUP BY dp.product_id, dp.sku, dp.product_name, dp.category, dp.price
ORDER BY total_revenue DESC NULLS LAST;

-- Представление для клиентских метрик
CREATE OR REPLACE VIEW vw_customer_metrics AS
SELECT 
    du.user_id,
    du.email,
    du.country,
    du.subscription_tier,
    COUNT(DISTINCT fo.order_id) as total_orders,
    SUM(fo.total_amount) as total_spent,
    MIN(fo.order_date) as first_order_date,
    MAX(fo.order_date) as last_order_date,
    AVG(fo.total_amount) as avg_order_value,
    CASE 
        WHEN MAX(fo.order_date) > CURRENT_DATE - INTERVAL '30 days' THEN 'active'
        WHEN MAX(fo.order_date) > CURRENT_DATE - INTERVAL '90 days' THEN 'warm'
        ELSE 'churned'
    END as activity_status
FROM cleansed.dim_users du
LEFT JOIN cleansed.fact_orders fo ON du.user_id = fo.user_id
WHERE du.is_current = TRUE
GROUP BY du.user_id, du.email, du.country, du.subscription_tier
ORDER BY total_spent DESC NULLS LAST;

-- 09_init_data.sql
-- Инициализация начальных данных

-- Заполняем таблицу дат на 5 лет вперед
SELECT populate_dim_dates(
    '2023-01-01'::DATE,
    '2028-12-31'::DATE
);

-- Создаем партиции на ближайший год
DO $$
DECLARE
    month_date DATE;
BEGIN
    FOR i IN 0..11 LOOP
        month_date := DATE_TRUNC('month', CURRENT_DATE + (i || ' months')::INTERVAL);
        PERFORM create_fact_orders_partition(month_date);
    END LOOP;
END $$;

-- Добавляем тестовые данные (опционально)
INSERT INTO cleansed.dim_products (product_id, sku, product_name, category, price, status)
VALUES 
    (1, 'PROD-001', 'Laptop Pro', 'Electronics', 1299.99, 'active'),
    (2, 'PROD-002', 'Wireless Mouse', 'Electronics', 49.99, 'active'),
    (3, 'PROD-003', 'Office Chair', 'Furniture', 299.99, 'active'),
    (4, 'PROD-004', 'Desk Lamp', 'Home', 29.99, 'active'),
    (5, 'PROD-005', 'Notebook', 'Stationery', 9.99, 'active')
ON CONFLICT (product_id) DO NOTHING;

-- 10_grants.sql
-- Настройка прав доступа

-- Создание ролей
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'etl_user') THEN
        CREATE ROLE etl_user WITH LOGIN PASSWORD 'etl_password123';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'analyst_user') THEN
        CREATE ROLE analyst_user WITH LOGIN PASSWORD 'analyst_password123';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'readonly_user') THEN
        CREATE ROLE readonly_user WITH LOGIN PASSWORD 'readonly_password123';
    END IF;
END $$;

-- Права для ETL пользователя
GRANT USAGE ON SCHEMA raw, cleansed, mart, audit, temp TO etl_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA raw, cleansed, mart, audit, temp TO etl_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA raw, cleansed, mart, audit, temp TO etl_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO etl_user;

-- Права для аналитика
GRANT USAGE ON SCHEMA cleansed, mart TO analyst_user;
GRANT SELECT ON ALL TABLES IN SCHEMA cleansed, mart TO analyst_user;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA cleansed, mart TO analyst_user;
GRANT EXECUTE ON FUNCTION populate_dim_dates, cleanup_raw_data TO analyst_user;

-- Права только для чтения
GRANT USAGE ON SCHEMA mart TO readonly_user;
GRANT SELECT ON ALL TABLES IN SCHEMA mart TO readonly_user;
GRANT SELECT ON mart.daily_sales_summary TO readonly_user;

-- Применение прав к новым таблицам
ALTER DEFAULT PRIVILEGES IN SCHEMA raw GRANT ALL ON TABLES TO etl_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA cleansed GRANT ALL ON TABLES TO etl_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA mart GRANT ALL ON TABLES TO etl_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA audit GRANT ALL ON TABLES TO etl_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA temp GRANT ALL ON TABLES TO etl_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA cleansed GRANT SELECT ON TABLES TO analyst_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA mart GRANT SELECT ON TABLES TO analyst_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA mart GRANT SELECT ON TABLES TO readonly_user;
```

## Docker Compose для развертывания (исправленная версия)

```yaml
version: '3.8'

services:
  postgres-warehouse:
    image: postgres:15-alpine
    container_name: postgres-analytical-warehouse
    environment:
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: admin123
      POSTGRES_DB: warehouse
      POSTGRES_INITDB_ARGS: "--encoding=UTF8 --locale=C"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./sql:/docker-entrypoint-initdb.d
    ports:
      - "5432:5432"
    networks:
      - data-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U admin -d warehouse"]
      interval: 30s
      timeout: 10s
      retries: 3
    command: >
      postgres
      -c max_connections=200
      -c shared_buffers=256MB
      -c effective_cache_size=768MB
      -c maintenance_work_mem=64MB
      -c checkpoint_completion_target=0.9
      -c wal_buffers=16MB
      -c default_statistics_target=100

  pgadmin:
    image: dpage/pgadmin4:latest
    container_name: pgadmin-warehouse
    environment:
      PGADMIN_DEFAULT_EMAIL: admin@warehouse.com
      PGADMIN_DEFAULT_PASSWORD: admin123
      PGADMIN_CONFIG_SERVER_MODE: 'False'
    volumes:
      - pgadmin_data:/var/lib/pgadmin
    ports:
      - "5050:80"
    depends_on:
      - postgres-warehouse
    networks:
      - data-network

volumes:
  postgres_data:
  pgadmin_data:

networks:
  data-network:
    driver: bridge
```

## Инструкция по запуску

1. **Создайте структуру каталогов:**
```bash
mkdir -p sql
```

2. **Сохраните SQL скрипты в файлы:**
```bash
# Сохраните весь SQL код выше в файлы:
# sql/01_create_schemas.sql
# sql/02_raw_schema.sql
# sql/03_cleansed_schema.sql
# sql/04_mart_schema.sql
# sql/05_audit_schema.sql
# sql/06_temp_schema.sql
# sql/07_functions_and_triggers.sql
# sql/08_views.sql
# sql/09_init_data.sql
# sql/10_grants.sql
```

3. **Запустите Docker Compose:**
```bash
docker-compose up -d
```

4. **Подключитесь к базе данных:**
```bash
# Используя psql
psql -h localhost -p 5432 -U admin -d warehouse

# Или через pgAdmin
# Откройте http://localhost:5050
# Логин: admin@warehouse.com
# Пароль: admin123
# Добавьте сервер:
# - Host: postgres-warehouse
# - Port: 5432
# - Username: admin
# - Password: admin123
```

## Проверка установки

```sql
-- Проверьте созданные схемы
SELECT schema_name 
FROM information_schema.schemata 
WHERE schema_name IN ('raw', 'cleansed', 'mart', 'audit', 'temp')
ORDER BY schema_name;

-- Проверьте таблицы в каждой схеме
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema IN ('raw', 'cleansed', 'mart', 'audit', 'temp')
ORDER BY table_schema, table_name;

-- Проверьте заполнение таблицы дат
SELECT COUNT(*) as total_dates FROM cleansed.dim_dates;
SELECT * FROM cleansed.dim_dates ORDER BY date_id LIMIT 10;

-- Проверьте представления
SELECT table_name, is_updatable
FROM information_schema.views
WHERE table_schema IN ('public')
ORDER BY table_name;
```