# Архитектура аналитического хранилища на базе PostgreSQL с Airflow

```mermaid
flowchart TD
    subgraph "Слой 1: Источники данных (Sources)"
        S1["Transactional DBs<br/>PostgreSQL/MySQL"]
        S2["API & Services<br/>REST, gRPC, GraphQL"]
        S3["Файловые источники<br/>CSV, JSON, Parquet"]
        S4["Потоковые данные<br/>Kafka, RabbitMQ"]
        S5["Внешние источники<br/>S3, FTP, HTTP"]
    end

    subgraph "Слой 2: Оркестрация (Airflow)"
        A1["DAG 1: ELT Pipeline<br/>schedule: @daily"]
        A2["DAG 2: CDC Replication<br/>schedule: @hourly"]
        A3["DAG 3: Data Quality<br/>schedule: @daily"]
        A4["DAG 4: Mart Generation<br/>schedule: @hourly"]
        
        AS["Airflow Scheduler"]
        AW["Airflow Workers<br/>CeleryExecutor"]
        MW["Metabase/Airflow UI<br/>Monitoring"]
    end

    subgraph "Слой 3: Хранилище PostgreSQL"
        subgraph "Schema: raw"
            R1["stg_users<br/>Type: append-only<br/>Retention: 365d"]
            R2["stg_orders<br/>Type: append-only"]
            R3["stg_products<br/>Type: full refresh"]
            R4["stg_payments<br/>Type: incremental"]
        end
        
        subgraph "Schema: cleansed"
            C1["dim_users<br/>SCD Type 2<br/>Partitioned"]
            C2["dim_products<br/>SCD Type 1"]
            C3["dim_dates<br/>Static table"]
            C4["fact_orders<br/>Daily partitions"]
            C5["fact_payments<br/>Monthly partitions"]
        end
        
        subgraph "Schema: mart"
            M1["sales_mart<br/>Materialized views"]
            M2["customer_mart<br/>Aggregated tables"]
            M3["inventory_mart<br/>Denormalized data"]
            M4["kpi_dashboard<br/>Pre-calculated"]
        end
        
        subgraph "Schema: audit"
            AU1["etl_logs<br/>Pipeline execution"]
            AU2["data_quality<br/>Validation results"]
            AU3["lineage<br/>Data lineage tracking"]
        end
        
        subgraph "Schema: temp"
            T1["temp_staging<br/>Intermediate data"]
            T2["temp_transforms"]
            T3["temp_aggregations"]
        end
    end

    subgraph "Слой 4: Обслуживание"
        PG1["PostgreSQL Maintenance<br/>• Vacuum<br/>• Analyze<br/>• Index rebuild"]
        PG2["Partition Management<br/>• Create new<br/>• Drop old<br/>• Reindex"]
        PG3["Backup & Recovery<br/>• WAL archiving<br/>• Base backups<br/>• Point-in-time recovery"]
    end

    subgraph "Слой 5: Потребление (Consumption)"
        BI1["BI Tools<br/>Metabase, Tableau"]
        BI2["Data Science<br/>Jupyter, Python"]
        BI3["API Layer<br/>GraphQL, REST"]
        BI4["Reports<br/>PDF, Excel, Email"]
    end

    %% Connections
    S1 --> A1
    S2 --> A1
    S3 --> A1
    S4 --> A2
    S5 --> A3
    
    A1 --> R1
    A1 --> R2
    A1 --> R3
    A1 --> R4
    
    A2 --> R1
    A2 --> R2
    
    R1 --> C1
    R2 --> C4
    R3 --> C2
    R4 --> C5
    
    C1 --> M1
    C2 --> M1
    C3 --> M1
    C4 --> M1
    C5 --> M2
    
    M1 --> BI1
    M2 --> BI2
    M3 --> BI3
    M4 --> BI4
    
    AS --> A1
    AS --> A2
    AS --> A3
    AS --> A4
    
    AW --> AS
    
    A1 --> AU1
    A2 --> AU1
    A3 --> AU2
    A4 --> AU3
    
    PG1 --> C1
    PG2 --> C4
    PG3 --> C5
    
    MW --> AS
    MW --> AW
```

---

## Детальная схема PostgreSQL схем

```mermaid
erDiagram
    %% Raw Schema
    raw.stg_users {
        bigint id PK "Идентификатор записи"
        jsonb raw_data "Сырые данные"
        timestamp loaded_at "Время загрузки"
        varchar source_system "Источник"
        varchar load_id "Идентификатор загрузки"
    }
    
    raw.stg_orders {
        bigint id PK
        jsonb raw_data
        timestamp loaded_at
        varchar source_system
        varchar load_id
    }
    
    raw.stg_products {
        bigint id PK
        jsonb raw_data
        timestamp loaded_at
        varchar source_system
        varchar load_id
    }
    
    raw.stg_payments {
        bigint id PK
        jsonb raw_data
        timestamp loaded_at
        varchar source_system
        varchar load_id
    }
    
    %% Cleansed Schema - Dimension Tables
    cleansed.dim_users {
        bigint user_id PK
        varchar email
        varchar full_name
        date date_of_birth
        varchar country
        varchar subscription_tier
        date valid_from "SCD Type 2"
        date valid_to "SCD Type 2"
        boolean is_current "SCD Type 2"
        timestamp created_at
        timestamp updated_at
    }
    
    cleansed.dim_products {
        bigint product_id PK
        varchar sku
        varchar product_name
        varchar category
        decimal price
        varchar status
        timestamp created_at
        timestamp updated_at
    }
    
    cleansed.dim_dates {
        date date_id PK
        integer year
        integer quarter
        integer month
        integer week
        integer day_of_year
        integer day_of_month
        integer day_of_week
        boolean is_weekend
        boolean is_holiday
    }
    
    %% Cleansed Schema - Fact Tables
    cleansed.fact_orders {
        bigint order_id PK
        bigint user_id FK
        bigint product_id FK
        date order_date FK
        integer quantity
        decimal unit_price
        decimal total_amount
        varchar status
        timestamp created_at
        timestamp updated_at
    }
    
    cleansed.fact_payments {
        bigint payment_id PK
        bigint order_id FK
        date payment_date FK
        decimal amount
        varchar payment_method
        varchar status
        timestamp created_at
        timestamp processed_at
    }
    
    %% Mart Schema
    mart.sales_mart {
        date sale_date PK
        varchar product_category
        varchar user_country
        integer total_orders
        decimal total_revenue
        decimal avg_order_value
        integer unique_customers
        decimal revenue_per_customer
    }
    
    mart.customer_mart {
        bigint user_id PK
        date first_order_date
        date last_order_date
        integer total_orders
        decimal total_spent
        integer days_since_last_order
        varchar customer_segment
        decimal clv_30d
    }
    
    %% Relationships
    raw.stg_users ||--o{ cleansed.dim_users : "transforms_to"
    raw.stg_products ||--o{ cleansed.dim_products : "transforms_to"
    raw.stg_orders ||--o{ cleansed.fact_orders : "transforms_to"
    
    cleansed.dim_users ||--o{ cleansed.fact_orders : "references"
    cleansed.dim_products ||--o{ cleansed.fact_orders : "references"
    cleansed.dim_dates ||--o{ cleansed.fact_orders : "references"
    
    cleansed.fact_orders ||--o{ mart.sales_mart : "aggregates_to"
    cleansed.dim_users ||--o{ mart.customer_mart : "analyzes_to"
```

---

## Архитектура Airflow DAGs

```mermaid
flowchart TD
    subgraph "Airflow Infrastructure"
        SCH["Scheduler<br/>parsed_dags<br/>jobs<br/>executor"]
        WEB["Web Server<br/>UI/API<br/>RBAC<br/>Logs"]
        MET["Metadata DB<br/>PostgreSQL<br/>DAG runs<br/>Task states"]
        
        subgraph "Worker Pool"
            W1["Worker 1<br/>LocalExecutor/Celery"]
            W2["Worker 2<br/>K8sPodOperator"]
            W3["Worker 3<br/>DockerOperator"]
        end
        
        subgraph "External Services"
            SMTP["SMTP Server<br/>Alerts & Notifications"]
            S3["S3/MinIO<br/>DAG files<br/>Log storage"]
            VAULT["Vault<br/>Secrets management"]
        end
    end

    subgraph "DAG 1: Основной ETL Pipeline"
        D1_T1["start >>"]
        D1_T2["check_dependencies<br/>Sensor: ExternalTaskSensor"]
        D1_T3["extract_source_data<br/>PythonOperator/PgHook"]
        
        subgraph "Parallel Processing"
            D1_T4["transform_users<br/>SQLExecuteQueryOperator"]
            D1_T5["transform_products<br/>SQLExecuteQueryOperator"]
            D1_T6["transform_orders<br/>SQLExecuteQueryOperator"]
        end
        
        D1_T7["validate_data_quality<br/>GreatExpectationsOperator"]
        D1_T8["load_to_cleansed<br/>PostgresOperator"]
        D1_T9["generate_marts<br/>MaterializedViewOperator"]
        D1_T10["send_notifications<br/>EmailOperator/SlackOperator"]
        D1_T11["end >>"]
        
        D1_T1 --> D1_T2
        D1_T2 --> D1_T3
        D1_T3 --> D1_T4
        D1_T3 --> D1_T5
        D1_T3 --> D1_T6
        D1_T4 --> D1_T7
        D1_T5 --> D1_T7
        D1_T6 --> D1_T7
        D1_T7 --> D1_T8
        D1_T8 --> D1_T9
        D1_T9 --> D1_T10
        D1_T10 --> D1_T11
    end

    subgraph "DAG 2: CDC Replication"
        D2_T1["start >>"]
        D2_T2["capture_changes<br/>Debezium/Kafka"]
        D2_T3["apply_changes_raw<br/>PostgresOperator"]
        D2_T4["slowly_changing_dims<br/>SCD Type 2 Logic"]
        D2_T5["incremental_facts<br/>Merge/Upsert"]
        D2_T6["update_marts<br/>Refresh Materialized Views"]
        D2_T7["end >>"]
        
        D2_T1 --> D2_T2
        D2_T2 --> D2_T3
        D2_T3 --> D2_T4
        D2_T4 --> D2_T5
        D2_T5 --> D2_T6
        D2_T6 --> D2_T7
    end

    subgraph "DAG 3: Data Quality & Monitoring"
        D3_T1["start >>"]
        D3_T2["run_data_tests<br/>SQLCheckOperator"]
        D3_T3["freshness_checks<br/>DataFreshnessSensor"]
        D3_T4["volume_checks<br/>RowCountSensor"]
        D3_T5["anomaly_detection<br/>PythonOperator + ML"]
        D3_T6["report_generation<br/>JupyterNotebookOperator"]
        D3_T7["alert_on_failure<br/>PagerDutyOperator"]
        D3_T8["end >>"]
        
        D3_T1 --> D3_T2
        D3_T2 --> D3_T3
        D3_T3 --> D3_T4
        D3_T4 --> D3_T5
        D3_T5 --> D3_T6
        D3_T6 --> D3_T7
        D3_T7 --> D3_T8
    end

    subgraph "DAG 4: Maintenance & Optimization"
        D4_T1["start >>"]
        D4_T2["vacuum_tables<br/>PostgresOperator"]
        D4_T3["analyze_statistics<br/>PostgresOperator"]
        D4_T4["manage_partitions<br/>PythonOperator"]
        D4_T5["reindex_tables<br/>BashOperator"]
        D4_T6["backup_database<br/>PgDumpOperator"]
        D4_T7["cleanup_old_data<br/>SQLExecuteQueryOperator"]
        D4_T8["end >>"]
        
        D4_T1 --> D4_T2
        D4_T2 --> D4_T3
        D4_T3 --> D4_T4
        D4_T4 --> D4_T5
        D4_T5 --> D4_T6
        D4_T6 --> D4_T7
        D4_T7 --> D4_T8
    end

    %% Connections
    SCH --> D1_T1
    SCH --> D2_T1
    SCH --> D3_T1
    SCH --> D4_T1
    
    WEB --> MET
    SCH --> MET
    
    W1 --> D1_T4
    W2 --> D1_T5
    W3 --> D1_T6
    
    VAULT --> D1_T3
    S3 --> D3_T6
    SMTP --> D1_T10
```

---

## Детальная реализация DAG в Airflow

```python
"""
airflow/dags/analytical_warehouse.py
Полный ETL DAG для аналитического хранилища
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.operators.python import PythonOperator
from airflow.operators.email import EmailOperator
from airflow.operators.dummy import DummyOperator
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.utils.task_group import TaskGroup
import pandas as pd
import logging

default_args = {
    'owner': 'data_engineering',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2024, 1, 1),
    'postgres_conn_id': 'analytical_warehouse',
    'email': ['data-team@company.com']
}

def create_analytical_warehouse_dag():
    """Создает основной DAG для аналитического хранилища"""
    
    with DAG(
        dag_id='analytical_warehouse_etl',
        default_args=default_args,
        description='Полный ETL пайплайн для аналитического хранилища',
        schedule_interval='@daily',
        catchup=False,
        max_active_runs=1,
        tags=['data_warehouse', 'etl', 'postgres']
    ) as dag:
        
        # 1. Начало пайплайна
        start = DummyOperator(task_id='start')
        
        # 2. Ожидание зависимостей
        wait_for_source = ExternalTaskSensor(
            task_id='wait_for_source_systems',
            external_dag_id='source_systems_sync',
            external_task_id='end',
            mode='reschedule',
            timeout=3600,
            poke_interval=300
        )
        
        # 3. Извлечение данных
        with TaskGroup('extract_data', tooltip='Извлечение данных из источников') as extract_group:
            
            extract_users = PostgresOperator(
                task_id='extract_users',
                sql="""
                -- Копирование данных в raw схему
                INSERT INTO raw.stg_users (raw_data, loaded_at, source_system, load_id)
                SELECT 
                    row_to_json(t) as raw_data,
                    NOW() as loaded_at,
                    'source_db' as source_system,
                    '{{ ds }}' as load_id
                FROM source.users t
                WHERE updated_at >= '{{ prev_ds }}' 
                    AND updated_at < '{{ ds }}';
                """,
                autocommit=True
            )
            
            extract_orders = PostgresOperator(
                task_id='extract_orders',
                sql="""
                INSERT INTO raw.stg_orders (raw_data, loaded_at, source_system, load_id)
                SELECT 
                    row_to_json(t) as raw_data,
                    NOW() as loaded_at,
                    'source_db' as source_system,
                    '{{ ds }}' as load_id
                FROM source.orders t
                WHERE order_date = '{{ ds }}';
                """,
                autocommit=True
            )
            
            extract_products = PythonOperator(
                task_id='extract_products',
                python_callable=extract_products_func,
                op_kwargs={'execution_date': '{{ ds }}'}
            )
        
        # 4. Преобразование данных
        with TaskGroup('transform_data', tooltip='Преобразование и очистка данных') as transform_group:
            
            # Очистка пользователей
            transform_users = PostgresOperator(
                task_id='transform_users',
                sql="""
                -- Очистка и дедупликация пользователей
                WITH cleaned_users AS (
                    SELECT DISTINCT ON (user_id)
                        (raw_data->>'id')::bigint as user_id,
                        raw_data->>'email' as email,
                        raw_data->>'full_name' as full_name,
                        (raw_data->>'date_of_birth')::date as date_of_birth,
                        raw_data->>'country' as country,
                        raw_data->>'subscription_tier' as subscription_tier,
                        (raw_data->>'created_at')::timestamp as created_at,
                        (raw_data->>'updated_at')::timestamp as updated_at,
                        loaded_at
                    FROM raw.stg_users
                    WHERE load_id = '{{ ds }}'
                    ORDER BY user_id, loaded_at DESC
                )
                -- SCD Type 2 логика
                INSERT INTO cleansed.dim_users (
                    user_id, email, full_name, date_of_birth, 
                    country, subscription_tier, valid_from, valid_to, 
                    is_current, created_at, updated_at
                )
                SELECT 
                    cu.user_id,
                    cu.email,
                    cu.full_name,
                    cu.date_of_birth,
                    cu.country,
                    cu.subscription_tier,
                    '{{ ds }}'::date as valid_from,
                    '9999-12-31'::date as valid_to,
                    TRUE as is_current,
                    cu.created_at,
                    cu.updated_at
                FROM cleaned_users cu
                WHERE NOT EXISTS (
                    SELECT 1 FROM cleansed.dim_users du 
                    WHERE du.user_id = cu.user_id 
                    AND du.is_current = TRUE
                    AND du.email = cu.email
                    AND du.country = cu.country
                    AND du.subscription_tier = cu.subscription_tier
                );
                
                -- Обновление старых записей
                UPDATE cleansed.dim_users du
                SET valid_to = '{{ ds }}'::date - INTERVAL '1 day',
                    is_current = FALSE
                FROM cleaned_users cu
                WHERE du.user_id = cu.user_id
                    AND du.is_current = TRUE
                    AND EXISTS (
                        SELECT 1 FROM cleansed.dim_users 
                        WHERE user_id = cu.user_id 
                        AND is_current = TRUE
                        AND (
                            email != cu.email
                            OR country != cu.country
                            OR subscription_tier != cu.subscription_tier
                        )
                    );
                """,
                autocommit=True
            )
            
            # Очистка заказов
            transform_orders = PostgresOperator(
                task_id='transform_orders',
                sql="""
                -- Создание фактовой таблицы заказов
                INSERT INTO cleansed.fact_orders (
                    order_id, user_id, product_id, order_date,
                    quantity, unit_price, total_amount, status,
                    created_at, updated_at
                )
                SELECT 
                    (ro.raw_data->>'id')::bigint as order_id,
                    (ro.raw_data->>'user_id')::bigint as user_id,
                    (ro.raw_data->>'product_id')::bigint as product_id,
                    (ro.raw_data->>'order_date')::date as order_date,
                    (ro.raw_data->>'quantity')::integer as quantity,
                    (ro.raw_data->>'unit_price')::decimal as unit_price,
                    (ro.raw_data->>'total_amount')::decimal as total_amount,
                    ro.raw_data->>'status' as status,
                    (ro.raw_data->>'created_at')::timestamp as created_at,
                    (ro.raw_data->>'updated_at')::timestamp as updated_at
                FROM raw.stg_orders ro
                WHERE ro.load_id = '{{ ds }}'
                ON CONFLICT (order_id) DO UPDATE SET
                    quantity = EXCLUDED.quantity,
                    unit_price = EXCLUDED.unit_price,
                    total_amount = EXCLUDED.total_amount,
                    status = EXCLUDED.status,
                    updated_at = EXCLUDED.updated_at;
                """,
                autocommit=True
            )
            
            # Обогащение данных
            enrich_data = PythonOperator(
                task_id='enrich_data',
                python_callable=enrich_data_func,
                op_kwargs={'execution_date': '{{ ds }}'}
            )
        
        # 5. Проверка качества данных
        data_quality_checks = PostgresOperator(
            task_id='data_quality_checks',
            sql="""
            -- Проверки качества данных
            DO $$
            DECLARE
                v_user_count INTEGER;
                v_order_count INTEGER;
                v_duplicate_users INTEGER;
            BEGIN
                -- Проверка количества записей
                SELECT COUNT(*) INTO v_user_count 
                FROM cleansed.dim_users 
                WHERE valid_from = '{{ ds }}'::date;
                
                SELECT COUNT(*) INTO v_order_count 
                FROM cleansed.fact_orders 
                WHERE order_date = '{{ ds }}'::date;
                
                -- Проверка на дубликаты
                SELECT COUNT(*) INTO v_duplicate_users
                FROM (
                    SELECT user_id, COUNT(*) 
                    FROM cleansed.dim_users 
                    WHERE is_current = TRUE 
                    GROUP BY user_id 
                    HAVING COUNT(*) > 1
                ) dup;
                
                -- Логирование результатов
                INSERT INTO audit.data_quality (
                    check_date, check_name, 
                    expected_value, actual_value, status
                ) VALUES 
                ('{{ ds }}', 'user_count', '>0', v_user_count, 
                 CASE WHEN v_user_count > 0 THEN 'PASS' ELSE 'FAIL' END),
                ('{{ ds }}', 'order_count', '>0', v_order_count, 
                 CASE WHEN v_order_count > 0 THEN 'PASS' ELSE 'FAIL' END),
                ('{{ ds }}', 'duplicate_users', '0', v_duplicate_users,
                 CASE WHEN v_duplicate_users = 0 THEN 'PASS' ELSE 'FAIL' END);
                
                -- Вызов исключения при ошибках
                IF v_user_count = 0 OR v_order_count = 0 OR v_duplicate_users > 0 THEN
                    RAISE EXCEPTION 'Data quality check failed';
                END IF;
            END $$;
            """,
            autocommit=True
        )
        
        # 6. Генерация витрин данных
        with TaskGroup('generate_marts', tooltip='Создание витрин данных') as marts_group:
            
            # Витрина продаж
            sales_mart = PostgresOperator(
                task_id='sales_mart',
                sql="""
                -- Обновление витрины продаж
                INSERT INTO mart.sales_mart (
                    sale_date, product_category, user_country,
                    total_orders, total_revenue, avg_order_value,
                    unique_customers, revenue_per_customer
                )
                SELECT 
                    fo.order_date as sale_date,
                    dp.category as product_category,
                    du.country as user_country,
                    COUNT(DISTINCT fo.order_id) as total_orders,
                    SUM(fo.total_amount) as total_revenue,
                    AVG(fo.total_amount) as avg_order_value,
                    COUNT(DISTINCT fo.user_id) as unique_customers,
                    SUM(fo.total_amount) / NULLIF(COUNT(DISTINCT fo.user_id), 0) as revenue_per_customer
                FROM cleansed.fact_orders fo
                JOIN cleansed.dim_users du ON fo.user_id = du.user_id AND du.is_current = TRUE
                JOIN cleansed.dim_products dp ON fo.product_id = dp.product_id
                WHERE fo.order_date = '{{ ds }}'::date
                GROUP BY fo.order_date, dp.category, du.country
                ON CONFLICT (sale_date, product_category, user_country) DO UPDATE SET
                    total_orders = EXCLUDED.total_orders,
                    total_revenue = EXCLUDED.total_revenue,
                    avg_order_value = EXCLUDED.avg_order_value,
                    unique_customers = EXCLUDED.unique_customers,
                    revenue_per_customer = EXCLUDED.revenue_per_customer;
                """,
                autocommit=True
            )
            
            # Витрина клиентов
            customer_mart = PostgresOperator(
                task_id='customer_mart',
                sql="""
                -- Обновление витрины клиентов
                WITH customer_stats AS (
                    SELECT 
                        du.user_id,
                        MIN(fo.order_date) as first_order_date,
                        MAX(fo.order_date) as last_order_date,
                        COUNT(DISTINCT fo.order_id) as total_orders,
                        SUM(fo.total_amount) as total_spent,
                        '{{ ds }}'::date - MAX(fo.order_date) as days_since_last_order
                    FROM cleansed.dim_users du
                    LEFT JOIN cleansed.fact_orders fo ON du.user_id = fo.user_id
                    WHERE du.is_current = TRUE
                    GROUP BY du.user_id
                )
                INSERT INTO mart.customer_mart (
                    user_id, first_order_date, last_order_date,
                    total_orders, total_spent, days_since_last_order,
                    customer_segment, clv_30d
                )
                SELECT 
                    cs.user_id,
                    cs.first_order_date,
                    cs.last_order_date,
                    cs.total_orders,
                    cs.total_spent,
                    cs.days_since_last_order,
                    CASE 
                        WHEN cs.total_spent > 1000 THEN 'VIP'
                        WHEN cs.total_spent > 100 THEN 'Regular'
                        ELSE 'New'
                    END as customer_segment,
                    cs.total_spent / NULLIF(cs.total_orders, 0) * 12 as clv_30d
                FROM customer_stats cs
                ON CONFLICT (user_id) DO UPDATE SET
                    last_order_date = EXCLUDED.last_order_date,
                    total_orders = EXCLUDED.total_orders,
                    total_spent = EXCLUDED.total_spent,
                    days_since_last_order = EXCLUDED.days_since_last_order,
                    customer_segment = EXCLUDED.customer_segment,
                    clv_30d = EXCLUDED.clv_30d;
                """,
                autocommit=True
            )
            
            # Витрина инвентаря
            inventory_mart = PostgresOperator(
                task_id='inventory_mart',
                sql="""
                REFRESH MATERIALIZED VIEW CONCURRENTLY mart.inventory_mart;
                """,
                autocommit=True
            )
        
        # 7. Уведомления
        send_success_email = EmailOperator(
            task_id='send_success_email',
            to='data-team@company.com',
            subject='ETL Pipeline Completed Successfully - {{ ds }}',
            html_content="""
            <h3>ETL Pipeline Report - {{ ds }}</h3>
            <p>The analytical warehouse ETL pipeline has completed successfully.</p>
            <p>Execution time: {{ execution_date }}</p>
            <p><a href="{{ ti.log_url }}">View Logs</a></p>
            """
        )
        
        # 8. Конец пайплайна
        end = DummyOperator(task_id='end')
        
        # Определение зависимостей
        start >> wait_for_source >> extract_group
        extract_group >> transform_group >> data_quality_checks
        data_quality_checks >> marts_group >> send_success_email >> end
        
        return dag

# Вспомогательные функции
def extract_products_func(execution_date, **context):
    """Извлечение данных о продуктах из внешнего источника"""
    import requests
    from airflow.providers.postgres.hooks.postgres import PostgresHook
    
    hook = PostgresHook(postgres_conn_id='analytical_warehouse')
    
    # Пример: получение данных из API
    response = requests.get(
        'https://api.example.com/products',
        params={'updated_after': execution_date}
    )
    products = response.json()
    
    # Запись в raw схему
    for product in products:
        hook.run(
            """
            INSERT INTO raw.stg_products (raw_data, loaded_at, source_system, load_id)
            VALUES (%s, %s, %s, %s)
            """,
            parameters=(product, datetime.now(), 'products_api', execution_date)
        )
    
    logging.info(f"Extracted {len(products)} products")

def enrich_data_func(execution_date, **context):
    """Обогащение данных гео-информацией"""
    from airflow.providers.postgres.hooks.postgres import PostgresHook
    import geopandas as gpd
    
    hook = PostgresHook(postgres_conn_id='analytical_warehouse')
    
    # Пример: обогащение гео-данными
    conn = hook.get_conn()
    
    # Загрузка гео-данных
    world = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))
    
    # Обновление данных в PostgreSQL
    with conn.cursor() as cursor:
        cursor.execute("""
            UPDATE cleansed.dim_users du
            SET region = g.region
            FROM (
                SELECT country, continent as region 
                FROM temp.world_data
            ) g
            WHERE du.country = g.country;
        """)
    
    conn.commit()
    logging.info("Data enrichment completed")

# Создание DAG
analytical_warehouse_dag = create_analytical_warehouse_dag()
```

---

## Docker Compose для развертывания

```yaml
version: '3.8'

services:
  # PostgreSQL с несколькими базами данных
  postgres-warehouse:
    image: postgres:15-alpine
    container_name: postgres-analytical-warehouse
    environment:
      POSTGRES_MULTIPLE_DATABASES: "warehouse,airflow,metabase"
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: admin123
      POSTGRES_DB: warehouse
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./sql/init:/docker-entrypoint-initdb.d
      - ./sql/schemas:/schemas
    ports:
      - "5432:5432"
    networks:
      - data-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U admin -d warehouse"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Airflow Scheduler
  airflow-scheduler:
    image: apache/airflow:2.7.1
    container_name: airflow-scheduler
    environment:
      AIRFLOW__CORE__EXECUTOR: CeleryExecutor
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@postgres-airflow/airflow
      AIRFLOW__CELERY__RESULT_BACKEND: db+postgresql://airflow:airflow@postgres-airflow/airflow
      AIRFLOW__CELERY__BROKER_URL: redis://redis:6379/0
      AIRFLOW__CORE__LOAD_EXAMPLES: 'false'
      AIRFLOW__API__AUTH_BACKEND: 'airflow.api.auth.backend.basic_auth'
    volumes:
      - ./airflow/dags:/opt/airflow/dags
      - ./airflow/logs:/opt/airflow/logs
      - ./airflow/plugins:/opt/airflow/plugins
      - ./airflow/config:/opt/airflow/config
      - ./scripts:/opt/airflow/scripts
    command: scheduler
    depends_on:
      postgres-airflow:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - data-network

  # Airflow Webserver
  airflow-webserver:
    image: apache/airflow:2.7.1
    container_name: airflow-webserver
    environment:
      AIRFLOW__CORE__EXECUTOR: CeleryExecutor
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@postgres-airflow/airflow
      AIRFLOW__CELERY__RESULT_BACKEND: db+postgresql://airflow:airflow@postgres-airflow/airflow
      AIRFLOW__CELERY__BROKER_URL: redis://redis:6379/0
      AIRFLOW__WEBSERVER__SECRET_KEY: 'supersecretkey'
    volumes:
      - ./airflow/dags:/opt/airflow/dags
      - ./airflow/logs:/opt/airflow/logs
      - ./airflow/plugins:/opt/airflow/plugins
      - ./airflow/config:/opt/airflow/config
    ports:
      - "8080:8080"
    command: webserver
    depends_on:
      - airflow-scheduler
    networks:
      - data-network

  # Airflow Workers
  airflow-worker:
    image: apache/airflow:2.7.1
    container_name: airflow-worker
    environment:
      AIRFLOW__CORE__EXECUTOR: CeleryExecutor
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@postgres-airflow/airflow
      AIRFLOW__CELERY__RESULT_BACKEND: db+postgresql://airflow:airflow@postgres-airflow/airflow
      AIRFLOW__CELERY__BROKER_URL: redis://redis:6379/0
    volumes:
      - ./airflow/dags:/opt/airflow/dags
      - ./airflow/logs:/opt/airflow/logs
      - ./airflow/plugins:/opt/airflow/plugins
      - ./airflow/config:/opt/airflow/config
      - ./scripts:/opt/airflow/scripts
    command: celery worker
    depends_on:
      - airflow-scheduler
    networks:
      - data-network
    deploy:
      replicas: 2

  # Airflow Database
  postgres-airflow:
    image: postgres:15-alpine
    container_name: postgres-airflow
    environment:
      POSTGRES_USER: airflow
      POSTGRES_PASSWORD: airflow
      POSTGRES_DB: airflow
    volumes:
      - postgres_airflow_data:/var/lib/postgresql/data
    networks:
      - data-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U airflow"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Redis для Celery
  redis:
    image: redis:7-alpine
    container_name: redis
    ports:
      - "6379:6379"
    networks:
      - data-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Metabase для визуализации
  metabase:
    image: metabase/metabase:latest
    container_name: metabase
    environment:
      MB_DB_TYPE: postgres
      MB_DB_DBNAME: metabase
      MB_DB_PORT: 5432
      MB_DB_USER: admin
      MB_DB_PASS: admin123
      MB_DB_HOST: postgres-warehouse
    ports:
      - "3000:3000"
    depends_on:
      - postgres-warehouse
    networks:
      - data-network

  # pgAdmin для администрирования
  pgadmin:
    image: dpage/pgadmin4:latest
    container_name: pgadmin
    environment:
      PGADMIN_DEFAULT_EMAIL: admin@company.com
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
  postgres_airflow_data:
  pgadmin_data:

networks:
  data-network:
    driver: bridge
```

---

## SQL скрипты для инициализации схем

```sql
-- sql/init/01_create_databases.sql
CREATE DATABASE warehouse;
CREATE DATABASE airflow;
CREATE DATABASE metabase;

-- sql/schemas/01_raw_schema.sql
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE raw.stg_users (
    id BIGSERIAL PRIMARY KEY,
    raw_data JSONB NOT NULL,
    loaded_at TIMESTAMP NOT NULL DEFAULT NOW(),
    source_system VARCHAR(50) NOT NULL,
    load_id VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE raw.stg_orders (
    id BIGSERIAL PRIMARY KEY,
    raw_data JSONB NOT NULL,
    loaded_at TIMESTAMP NOT NULL DEFAULT NOW(),
    source_system VARCHAR(50) NOT NULL,
    load_id VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE raw.stg_products (
    id BIGSERIAL PRIMARY KEY,
    raw_data JSONB NOT NULL,
    loaded_at TIMESTAMP NOT NULL DEFAULT NOW(),
    source_system VARCHAR(50) NOT NULL,
    load_id VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_stg_users_load_id ON raw.stg_users(load_id);
CREATE INDEX idx_stg_orders_load_id ON raw.stg_orders(load_id);
CREATE INDEX idx_stg_products_load_id ON raw.stg_products(load_id);

-- sql/schemas/02_cleansed_schema.sql
CREATE SCHEMA IF NOT EXISTS cleansed;

-- Таблица пользователей (SCD Type 2)
CREATE TABLE cleansed.dim_users (
    user_id BIGINT PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    date_of_birth DATE,
    country VARCHAR(100),
    subscription_tier VARCHAR(50),
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL DEFAULT '9999-12-31',
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Таблица продуктов
CREATE TABLE cleansed.dim_products (
    product_id BIGINT PRIMARY KEY,
    sku VARCHAR(100) UNIQUE NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    price DECIMAL(10,2) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Таблица дат
CREATE TABLE cleansed.dim_dates (
    date_id DATE PRIMARY KEY,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    month INTEGER NOT NULL,
    week INTEGER NOT NULL,
    day_of_year INTEGER NOT NULL,
    day_of_month INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    is_weekend BOOLEAN NOT NULL DEFAULT FALSE,
    is_holiday BOOLEAN NOT NULL DEFAULT FALSE
);

-- Фактовая таблица заказов (партиционированная)
CREATE TABLE cleansed.fact_orders (
    order_id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES cleansed.dim_users(user_id),
    product_id BIGINT NOT NULL REFERENCES cleansed.dim_products(product_id),
    order_date DATE NOT NULL REFERENCES cleansed.dim_dates(date_id),
    quantity INTEGER NOT NULL DEFAULT 1,
    unit_price DECIMAL(10,2) NOT NULL,
    total_amount DECIMAL(10,2) NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (order_date);

-- Создание партиций
CREATE TABLE cleansed.fact_orders_2024_01 PARTITION OF cleansed.fact_orders
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE cleansed.fact_orders_2024_02 PARTITION OF cleansed.fact_orders
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');

-- Индексы
CREATE INDEX idx_dim_users_current ON cleansed.dim_users(is_current);
CREATE INDEX idx_fact_orders_date ON cleansed.fact_orders(order_date);
CREATE INDEX idx_fact_orders_user ON cleansed.fact_orders(user_id);

-- sql/schemas/03_mart_schema.sql
CREATE SCHEMA IF NOT EXISTS mart;

-- Витрина продаж
CREATE TABLE mart.sales_mart (
    sale_date DATE NOT NULL,
    product_category VARCHAR(100) NOT NULL,
    user_country VARCHAR(100) NOT NULL,
    total_orders INTEGER NOT NULL DEFAULT 0,
    total_revenue DECIMAL(15,2) NOT NULL DEFAULT 0,
    avg_order_value DECIMAL(10,2) NOT NULL DEFAULT 0,
    unique_customers INTEGER NOT NULL DEFAULT 0,
    revenue_per_customer DECIMAL(10,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (sale_date, product_category, user_country)
);

-- Витрина клиентов
CREATE TABLE mart.customer_mart (
    user_id BIGINT PRIMARY KEY,
    first_order_date DATE,
    last_order_date DATE,
    total_orders INTEGER NOT NULL DEFAULT 0,
    total_spent DECIMAL(15,2) NOT NULL DEFAULT 0,
    days_since_last_order INTEGER,
    customer_segment VARCHAR(50) NOT NULL,
    clv_30d DECIMAL(10,2),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Материализованное представление для инвентаря
CREATE MATERIALIZED VIEW mart.inventory_mart AS
SELECT 
    dp.product_id,
    dp.sku,
    dp.product_name,
    dp.category,
    dp.price,
    dp.status,
    COUNT(fo.order_id) as total_orders,
    SUM(fo.quantity) as total_quantity_sold,
    SUM(fo.total_amount) as total_revenue,
    AVG(fo.total_amount) as avg_order_value
FROM cleansed.dim_products dp
LEFT JOIN cleansed.fact_orders fo ON dp.product_id = fo.product_id
GROUP BY dp.product_id, dp.sku, dp.product_name, dp.category, dp.price, dp.status
WITH DATA;

CREATE UNIQUE INDEX idx_inventory_mart_product ON mart.inventory_mart(product_id);

-- sql/schemas/04_audit_schema.sql
CREATE SCHEMA IF NOT EXISTS audit;

-- Логи ETL
CREATE TABLE audit.etl_logs (
    log_id BIGSERIAL PRIMARY KEY,
    dag_id VARCHAR(255) NOT NULL,
    task_id VARCHAR(255) NOT NULL,
    execution_date TIMESTAMP NOT NULL,
    status VARCHAR(50) NOT NULL,
    records_processed INTEGER,
    duration_seconds INTEGER,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Качество данных
CREATE TABLE audit.data_quality (
    check_id BIGSERIAL PRIMARY KEY,
    check_date DATE NOT NULL,
    check_name VARCHAR(100) NOT NULL,
    expected_value VARCHAR(255),
    actual_value VARCHAR(255),
    status VARCHAR(50) NOT NULL,
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Линейность данных
CREATE TABLE audit.data_lineage (
    lineage_id BIGSERIAL PRIMARY KEY,
    source_table VARCHAR(255) NOT NULL,
    source_column VARCHAR(255) NOT NULL,
    target_table VARCHAR(255) NOT NULL,
    target_column VARCHAR(255) NOT NULL,
    transformation_type VARCHAR(100),
    transformation_logic TEXT,
    last_updated TIMESTAMP NOT NULL DEFAULT NOW()
);
```

---

## Мониторинг и метрики

```yaml
# monitoring/prometheus.yml
scrape_configs:
  - job_name: 'postgres-warehouse'
    static_configs:
      - targets: ['postgres-warehouse:9187']
    params:
      dsn: ['postgresql://admin:admin123@postgres-warehouse:5432/warehouse?sslmode=disable']

  - job_name: 'airflow'
    static_configs:
      - targets: ['airflow-webserver:8080']
    metrics_path: '/metrics'

  - job_name: 'application'
    static_configs:
      - targets: ['metabase:3000']

# monitoring/grafana/dashboards/postgres-warehouse.json
dashboard_config:
  title: "Analytical Warehouse Dashboard"
  panels:
    - title: "ETL Pipeline Performance"
      metrics:
        - "postgres_table_size_bytes{table=~'cleansed.*'}"
        - "postgres_rows_inserted_per_second"
        - "postgres_queries_per_second"
      
    - title: "Data Quality Metrics"
      metrics:
        - "data_quality_check_failures_total"
        - "data_freshness_seconds"
        - "data_completeness_percentage"
      
    - title: "Airflow DAG Status"
      metrics:
        - "airflow_dag_run_duration_seconds"
        - "airflow_task_failure_count"
        - "airflow_dag_run_state{dag_id='analytical_warehouse_etl'}"
```

---

## Ключевые принципы архитектуры

### 1. **Слоистость данных:**
- **Raw:** Сырые, неизменные данные из источников
- **Cleansed:** Очищенные, типизированные, историзированные данные
- **Mart:** Агрегированные, денормализованные витрины
- **Audit:** Метаданные, логи, мониторинг

### 2. **Использование Airflow:**
- **Оркестрация:** Управление зависимостями задач
- **Мониторинг:** Отслеживание выполнения пайплайнов
- **Повторяемость:** Идемпотентные операции
- **Масштабируемость:** Распределенные воркеры

### 3. **Оптимизации PostgreSQL:**
- **Партиционирование:** По датам для фактовых таблиц
- **Индексы:** Составные индексы для частых запросов
- **Материализованные представления:** Для сложных агрегаций
- **Vacuum/Analyze:** Регулярное обслуживание

### 4. **Качество данных:**
- **Валидация:** Проверки на каждом этапе
- **Мониторинг:** Отслеживание свежести и полноты
- **Алертинг:** Уведомления о проблемах
- **Линейность:** Отслеживание происхождения данных

### 5. **Масштабирование:**
- **Горизонтальное:** Добавление воркеров Airflow
- **Вертикальное:** Увеличение ресурсов PostgreSQL
- **Шардирование:** Разделение данных по бизнес-юнитам
- **Кэширование:** Redis для промежуточных результатов