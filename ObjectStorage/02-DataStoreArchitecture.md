# Архитектура распределенного объектного хранилища: узлы, репликация, балансировка

```mermaid
flowchart TD
    subgraph "Слой балансировки нагрузки"
        LB[Load Balancer<br/>HAProxy/Nginx]
        DNS[GeoDNS<br/>Round Robin]
    end

    subgraph "Регион 1 (us-east-1)"
        subgraph "Зона доступности A"
            VM1["ВМ 1<br/>MinIO Node<br/>CPU: 4, RAM: 16GB<br/>Storage: 4x500GB SSD"]
            VM2["ВМ 2<br/>MinIO Node<br/>CPU: 4, RAM: 16GB<br/>Storage: 4x500GB SSD"]
        end
        
        subgraph "Зона доступности B"
            VM3["ВМ 3<br/>MinIO Node<br/>CPU: 4, RAM: 16GB<br/>Storage: 4x500GB SSD"]
            VM4["ВМ 4<br/>MinIO Node<br/>CPU: 4, RAM: 16GB<br/>Storage: 4x500GB SSD"]
        end
        
        subgraph "Зона доступности C"
            VM5["ВМ 5<br/>Gateway/Load Balancer<br/>CPU: 2, RAM: 8GB"]
            VM6["ВМ 6<br/>Консоль/Мониторинг<br/>CPU: 2, RAM: 8GB"]
        end
    end

    subgraph "Регион 2 (eu-west-1)"
        subgraph "Зона доступности X"
            VM7["ВМ 7<br/>MinIO Node<br/>CPU: 4, RAM: 16GB"]
            VM8["ВМ 8<br/>MinIO Node<br/>CPU: 4, RAM: 16GB"]
        end
        
        subgraph "Зона доступности Y"
            VM9["ВМ 9<br/>MinIO Node<br/>CPU: 4, RAM: 16GB"]
            VM10["ВМ 10<br/>MinIO Node<br/>CPU: 4, RAM: 16GB"]
        end
    end

    DNS --> LB
    LB --> VM5
    
    VM5 --> VM1
    VM5 --> VM2
    VM5 --> VM3
    VM5 --> VM4
    
    VM6 --> VM1
    VM6 --> VM2
    
    %% Внутренняя сеть региона 1
    VM1 -- "Сеть: 10.0.1.0/24<br/>Порт: 9000" --> VM2
    VM2 -- "Сеть: 10.0.1.0/24" --> VM3
    VM3 -- "Сеть: 10.0.2.0/24" --> VM4
    VM4 -- "Сеть: 10.0.2.0/24" --> VM1
    
    %% Межрегиональная репликация
    VM1 -. "Межрегиональная репликация<br/>WAN оптимизация" .-> VM7
    VM2 -. "Асинхронная репликация<br/>500ms RTT" .-> VM8
    VM3 -. "Bucket-level replication" .-> VM9
    VM4 -. "Active-Active" .-> VM10
```

---

## Детальная схема репликации данных

```mermaid
flowchart TD
    subgraph "Логическая организация данных"
        B1["Bucket: user-photos<br/>Versioning: Enabled"]
        B2["Bucket: app-logs<br/>Lifecycle: 30d → GLACIER"]
        B3["Bucket: backups<br/>Replication: Cross-Region"]
    end

    subgraph "Физическое распределение - Erasure Coding"
        P1["Партия 1<br/>Data: D1, D2, D3<br/>Parity: P1, P2"]
        P2["Партия 2<br/>Data: D4, D5, D6<br/>Parity: P3, P4"]
        P3["Партия 3<br/>Data: D7, D8, D9<br/>Parity: P5, P6"]
    end

    subgraph "Распределение по узлам (4+2 схема)"
        N1["Узел 1<br/>D1, D4, P5"]
        N2["Узел 2<br/>D2, D5, P6"]
        N3["Узел 3<br/>D3, P3, D7"]
        N4["Узел 4<br/>P1, D6, D8"]
        N5["Узел 5<br/>P2, P4, D9"]
    end

    subgraph "Репликация между зонами доступности"
        AZ1["Зона A<br/>Узлы: 1, 2, 3"]
        AZ2["Зона B<br/>Узлы: 4, 5, 6"]
        
        AZ1 -- "Синхронная репликация<br/>&lt; 100ms задержка" --> AZ2
        AZ2 -- "Кворум: 3 из 5 узлов" --> AZ1
    end

    B1 --> P1
    B1 --> P2
    B2 --> P3
    
    P1 --> N1
    P1 --> N2
    P1 --> N3
    P1 --> N4
    P1 --> N5
    
    P2 --> N1
    P2 --> N2
    P2 --> N3
    P2 --> N4
    
    N1 --> AZ1
    N2 --> AZ1
    N3 --> AZ1
    N4 --> AZ2
    N5 --> AZ2
```

---

## Схема сетевой архитектуры и балансировки

```mermaid
flowchart TD
    subgraph "Клиентские подключения"
        C1[Web Application]
        C2[Mobile App]
        C3[Batch Processing]
        C4[CLI Tools]
    end

    subgraph "Публичный слой"
        ELB["Elastic Load Balancer<br/>SSL Termination<br/>Health Checks"]
        WAF["WAF Rules<br/>Rate Limiting<br/>DDoS Protection"]
        CDN["CDN Edge<br/>Cache Static Content"]
    end

    subgraph "Слой шлюзов (Gateway)"
        GW1["API Gateway 1<br/>S3 Protocol<br/>Authentication"]
        GW2["API Gateway 2<br/>Load Balancing<br/>Request Routing"]
        GW3["API Gateway 3<br/>Metrics Collection<br/>Audit Logs"]
    end

    subgraph "Сеть кластера"
        subgraph "Pod 1 (Rack A)"
            N1["minio-rack-a-1<br/>eth0: 10.10.1.10<br/>eth1: 192.168.1.10"]
            N2["minio-rack-a-2<br/>eth0: 10.10.1.11<br/>eth1: 192.168.1.11"]
        end
        
        subgraph "Pod 2 (Rack B)"
            N3["minio-rack-b-1<br/>eth0: 10.10.2.10<br/>eth1: 192.168.2.10"]
            N4["minio-rack-b-2<br/>eth0: 10.10.2.11<br/>eth1: 192.168.2.11"]
        end
        
        subgraph "Pod 3 (Rack C)"
            N5["minio-rack-c-1<br/>eth0: 10.10.3.10<br/>eth1: 192.168.3.10"]
            N6["minio-rack-c-2<br/>eth0: 10.10.3.11<br/>eth1: 192.168.3.11"]
        end
    end

    subgraph "Сервисы управления"
        ETCD["etcd Cluster<br/>Configuration<br/>Service Discovery"]
        PROM["Prometheus<br/>Metrics Collection"]
        GRAF["Grafana<br/>Monitoring Dashboard"]
        LOKI["Loki<br/>Log Aggregation"]
    end

    C1 --> CDN
    C2 --> WAF
    C3 --> ELB
    C4 --> ELB
    
    CDN --> ELB
    WAF --> ELB
    
    ELB --> GW1
    ELB --> GW2
    ELB --> GW3
    
    GW1 --> N1
    GW1 --> N3
    GW1 --> N5
    
    GW2 --> N2
    GW2 --> N4
    GW2 --> N6
    
    %% Внутренние сети
    N1 -- "Публичная сеть<br/>10.10.0.0/16" --> N3
    N3 -- "Внешний трафик" --> N5
    
    N1 -- "Приватная сеть репликации<br/>192.168.0.0/16" --> N2
    N2 -- "Высокая пропускная способность" --> N4
    N4 -- "Репликация данных" --> N6
    
    %% Сервисы управления
    N1 --> PROM
    N2 --> PROM
    N3 --> PROM
    N4 --> PROM
    
    PROM --> GRAF
    PROM --> LOKI
    
    N1 --> ETCD
    N3 --> ETCD
    N5 --> ETCD
```

---

## Схема процессов чтения/записи

```mermaid
sequenceDiagram
    participant Client as Клиент
    participant Gateway as API Gateway
    participant Meta as Metadata Service
    participant Storage as Storage Nodes
    participant Quorum as Кворум (3/5)
    participant Replication as Репликация

    Note over Client,Replication: ПРОЦЕСС ЗАПИСИ (PUT OBJECT)
    
    Client->>Gateway: PUT /bucket/key (10MB file)
    Gateway->>Meta: Запрос метаданных
    Meta-->>Gateway: Распределение: nodes [1,3,5,7,9]
    
    Gateway->>Storage: Начало multipart upload
    Storage-->>Gateway: Upload ID
    
    par Параллельная запись частей
        Gateway->>Storage Node 1: Часть 1 (5MB)
        Gateway->>Storage Node 3: Часть 2 (5MB)
    end
    
    Storage Node 1->>Quorum: Запись данных + parity
    Quorum-->>Storage Node 1: Подтверждение (3/5)
    
    Storage Node 3->>Quorum: Запись данных + parity
    Quorum-->>Storage Node 3: Подтверждение (3/5)
    
    Gateway->>Storage: Complete multipart upload
    Storage->>Meta: Обновление метаданных
    Meta->>Replication: Асинхронная репликация
    Replication-->>Meta: Репликация завершена
    
    Gateway-->>Client: 200 OK (ETag, VersionId)
    
    Note over Client,Replication: ПРОЦЕСС ЧТЕНИЯ (GET OBJECT)
    
    Client->>Gateway: GET /bucket/key
    Gateway->>Meta: Запрос расположения
    Meta-->>Gateway: Читать с nodes [1,5,9]
    
    par Параллельное чтение
        Gateway->>Storage Node 1: Запрос части 1
        Gateway->>Storage Node 5: Запрос части 2
    end
    
    Storage Node 1-->>Gateway: Данные части 1
    Storage Node 5-->>Gateway: Данные части 2
    
    Gateway->>Gateway: Сборка объекта
    Gateway-->>Client: 200 OK (файл)
    
    Note over Client,Replication: ОБРАБОТКА СБОЯ УЗЛА
    
    Gateway->>Storage Node 1: Запрос (узел недоступен)
    Gateway->>Quorum: Запрос восстановления
    Quorum->>Storage Node 3: Восстановление с parity
    Storage Node 3-->>Gateway: Данные восстановлены
    Gateway-->>Client: Прозрачное восстановление
```

---

## Физическая схема развертывания на ВМ/БМ

```mermaid
graph TB
    subgraph "Стойка 1 (Rack A)"
        subgraph "ВМ 1: minio-node-1"
            C1["CPU: 8 cores Intel Xeon"]
            M1["RAM: 32GB DDR4"]
            D1["Диски:<br/>• /dev/sda: 500GB NVMe (OS)<br/>• /dev/sdb: 2TB SSD (data1)<br/>• /dev/sdc: 2TB SSD (data2)<br/>• /dev/sdd: 2TB SSD (data3)"]
            N1["Сетевые интерфейсы:<br/>• eth0: 10GbE public<br/>• eth1: 25GbE storage<br/>• eth2: 1GbE management"]
        end
        
        subgraph "ВМ 2: minio-node-2"
            C2["CPU: 8 cores"]
            M2["RAM: 32GB"]
            D2["Диски: 3x2TB SSD"]
            N2["Сети: 10GbE/25GbE/1GbE"]
        end
        
        SW1["Торговый коммутатор<br/>Spine Switch<br/>100GbE uplink"]
    end

    subgraph "Стойка 2 (Rack B)"
        subgraph "ВМ 3: minio-node-3"
            C3["CPU: 8 cores"]
            M3["RAM: 32GB"]
            D3["Диски: 3x2TB SSD"]
            N3["Сети: 10GbE/25GbE/1GbE"]
        end
        
        subgraph "ВМ 4: minio-node-4"
            C4["CPU: 8 cores"]
            M4["RAM: 32GB"]
            D4["Диски: 3x2TB SSD"]
            N4["Сети: 10GbE/25GbE/1GbE"]
        end
        
        SW2["Торговый коммутатор<br/>Spine Switch<br/>100GbE uplink"]
    end

    subgraph "Стойка 3 (Management)"
        subgraph "ВМ 5: gateway-1"
            GW1["API Gateway<br/>HAProxy<br/>SSL Termination"]
            C5["CPU: 4 cores"]
            M5["RAM: 16GB"]
        end
        
        subgraph "ВМ 6: monitoring"
            MON["Monitoring Stack<br/>Prometheus + Grafana"]
            C6["CPU: 4 cores"]
            M6["RAM: 16GB"]
        end
        
        subgraph "ВМ 7: etcd"
            ETCD["etcd Cluster<br/>3 nodes"]
            C7["CPU: 2 cores"]
            M7["RAM: 8GB"]
        end
        
        SW3["Management Switch<br/>10GbE"]
    end

    %% Подключения внутри стойки
    N1 -- "25GbE storage" --> SW1
    N2 -- "25GbE storage" --> SW1
    
    N3 -- "25GbE storage" --> SW2
    N4 -- "25GbE storage" --> SW2
    
    %% Межстоечные подключения
    SW1 -- "100GbE" --> SW2
    SW1 -- "100GbE" --> SW3
    SW2 -- "100GbE" --> SW3
    
    %% Публичные подключения
    GW1 -- "10GbE public" --> SW3
    SW3 -- "Internet uplink" --> ISP["Internet Gateway"]
    
    %% Подключения к сервисам
    N1 -- "1GbE mgmt" --> SW3
    N2 -- "1GbE mgmt" --> SW3
    N3 -- "1GbE mgmt" --> SW3
    N4 -- "1GbE mgmt" --> SW3
    
    %% Мониторинг
    N1 --> MON
    N2 --> MON
    N3 --> MON
    N4 --> MON
    
    %% Конфигурация
    N1 --> ETCD
    N2 --> ETCD
    N3 --> ETCD
```

---

## Схема архитектуры репликации и консистентности

```mermaid
flowchart TD
    subgraph "Консистентность и кворум"
        Q1["Кворумная система<br/>Write: N/2 + 1<br/>Read: N/2 + 1"]
        Q2["Пример: 12 узлов<br/>Write: 7/12 подтверждений<br/>Read: 7/12 доступны"]
        Q3["Репликационный фактор<br/>RF=3: данные на 3 узлах<br/>RF=5: данные на 5 узлах"]
    end

    subgraph "Типы репликации"
        R1["Синхронная (локальная)<br/>• Write-ahead log<br/>• Immediate consistency<br/>• Высокая задержка"]
        
        R2["Асинхронная (межрегион)<br/>• Eventual consistency<br/>• Низкая задержка записи<br/>• Конфликты при обновлениях"]
        
        R3["Полусинхронная<br/>• Primary-Secondary<br/>• RPO ≈ 0<br/>• RTO &lt; 5 мин"]
    end

    subgraph "Стратегии размещения"
        P1["Равномерное распределение<br/>• Round-robin по узлам<br/>• Балансировка нагрузки<br/>• Равномерное использование дисков"]
        
        P2["Зональное размещение<br/>• Данные в разных AZ<br/>• Выживаемость при сбое AZ<br/>• Повышенная стоимость трафика"]
        
        P3["Аффинитет к данным<br/>• Часто используемые данные ближе<br/>• Hot/cold разделение<br/>• Кэширование на edge"]
    end

    subgraph "Механизмы восстановления"
        H1["Erasure Coding<br/>• k+m схема (пример: 8+4)<br/>• Выдерживает m отказов<br/>• Эффективность: k/(k+m)"]
        
        H2["Хэширование<br/>• Consistent hashing<br/>• Минимальная перебалансировка<br/>• Виртуальные узлы (vnodes)"]
        
        H3["Перебалансировка<br/>• Автоматическая при добавлении узлов<br/>• Фоновая миграция<br/>• Throttling нагрузки"]
    end

    Q1 --> R1
    Q2 --> R2
    Q3 --> R3
    
    R1 --> P1
    R2 --> P2
    R3 --> P3
    
    P1 --> H1
    P2 --> H2
    P3 --> H3
    
    %% Пример работы
    subgraph "Пример: Запись объекта 100MB"
        EX1["1. Разделение на 4 части по 25MB"]
        EX2["2. Расчет 2 parity блоков (erasure coding)"]
        EX3["3. Распределение по 6 узлам (4+2)"]
        EX4["4. Запись подтверждается при 4/6 успеха"]
        EX5["5. Асинхронная репликация в другой регион"]
    end
    
    H1 --> EX1
    EX1 --> EX2
    EX2 --> EX3
    EX3 --> EX4
    EX4 --> EX5
```

---

## Ключевые моменты архитектуры

### 1. **Размещение узлов на отдельных ВМ:**
- Каждая ВМ имеет выделенные CPU, RAM, диски
- Разделение сетей: public, storage, management
- Размещение в разных стойках/зонах доступности

### 2. **Репликация:**
- **Erasure Coding** для эффективности хранения
- **Кворумные операции** для консистентности
- **Многоуровневая репликация**: синхронная (внутри AZ), асинхронная (между регионами)

### 3. **Балансировка:**
- **L4/L7 балансировщики** на входе
- **Consistent hashing** для распределения данных
- **Health checks** и автоматическое исключение нерабочих узлов

### 4. **Отказоустойчивость:**
- Выдерживает отказ до `m` узлов (зависит от схемы erasure coding)
- Автоматическое восстановление данных с parity блоков
- Минимальное время простоя при отказе узла

### 5. **Масштабирование:**
- Горизонтальное масштабирование добавлением узлов
- Автоматическая перебалансировка данных
- Линейный рост производительности с добавлением узлов