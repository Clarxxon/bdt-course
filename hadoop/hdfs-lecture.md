# Использование HDFS и Apache Spark (PySpark).
￼
⸻

1. Коротко: что такое HDFS и Spark и почему их вместе используют
	•	HDFS (Hadoop Distributed File System) — распределённая файловая система для больших объёмов данных: хранит файлы, разбивает их на блоки и распределяет по DataNode; у неё есть NameNode (метаданные). HDFS даёт надёжное, масштабируемое хранилище для аналитики. (для деталей WebHDFS / конфигурации см. официальную документацию).  ￼
	•	Apache Spark — вычислительная платформа для распределённой обработки данных (параллельные трансформации, SQL, стриминг, ML). Spark может читать/писать данные прямо из HDFS и выполнять вычисления над ними. Spark предоставляет несколько API: RDD (низкоуровневое), DataFrame/SQL (табличное, оптимизируемое), Dataset (в Scala/Java).  ￼

Почему вместе? HDFS — место хранения, Spark — движок обработки. HDFS гарантирует репликацию и отказоустойчивость, Spark — быстрое in-memory/дисковое выполнение.

⸻

2. Краткая терминология (важно понять перед примерами)
	•	RDD (Resilient Distributed Dataset) — фундамент Spark: иммутабельная распределённая коллекция элементов, с ленивыми трансформациями и действиями; даёт контроль, но не даёт автоматических оптимизаций (Catalyst).  ￼
	•	DataFrame (табличные данные / ТД) — структура, организованная в именованные колонки, аналог таблицы в БД; DataFrame использует оптимизатор (Catalyst), столбечный формат памяти (Tungsten), позволяет SQL и оптимизации. Для Python/практики рекомендуется DataFrame API; RDD — для очень низкоуровневых задач.  ￼
	•	Трансформации — ленивые операции (map, filter, select, join, groupBy) — выполняются при вызове действия.
	•	Действия — операции, которые materialize результат (count, collect, save, write).

⸻

3. Подготовка окружения — что нужно настроить
	1.	Совместимость версий: Spark должен быть совместим с установленным Hadoop/HDFS (пакеты, бинарники). Проверяйте матрицу совместимости в документации дистрибутива.
	2.	Конфиги Hadoop: core-site.xml, hdfs-site.xml — либо их копии должны быть доступны Spark (через $HADOOP_CONF_DIR или spark.hadoop.* параметры). Частая ошибка — Spark не видит конфигурацию HDFS и пытается обращаться к локальной FS.  ￼
	3.	kerberos / безопасность: если кластер защищён Kerberos, нужно выполнить kinit, и/или настроить keytab principal, и/или настроить WebHDFS параметры (HTTP SPNEGO). Ошибки аутентификации — частая причина.  ￼
	4.	Путь доступа: используйте hdfs://<namenode>:<port>/path/... либо настроенный fs.defaultFS.
	5.	Запуск: при разработке — local[*] или pyspark на ноутбуке; в проде — spark-submit --master yarn / --master spark:// и т.д.

⸻

4. Подключение PySpark к HDFS — базовые примеры

Простейший PySpark-скрипт, читающий CSV из HDFS и записывающий в Parquet:

from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, TimestampType

spark = SparkSession.builder \
    .appName("hdfs-pyspark-example") \
    .getOrCreate()

# Явно указываем схему (рекомендуется для CSV)
schema = StructType([
    StructField("user_id", IntegerType(), True),
    StructField("event_ts", StringType(), True),
    StructField("event_type", StringType(), True)
])

df = spark.read.schema(schema) \
    .option("header", "true") \
    .csv("hdfs://namenode:9000/data/events.csv")    # <- путь в HDFS

df = df.withColumn("event_ts", spark.sql.functions.to_timestamp("event_ts", "yyyy-MM-dd HH:mm:ss"))
df.show(5)

# Запись в паркет, с партицированием по году/месяцу
df = df.withColumn("year", spark.sql.functions.year("event_ts")) \
       .withColumn("month", spark.sql.functions.month("event_ts"))

df.write.mode("overwrite").partitionBy("year", "month") \
    .parquet("hdfs://namenode:9000/data/parquet/events")

Чтение/запись из HDFS через SparkSession — стандартный путь. Практические примеры чтения/записи в HDFS показаны в руководствах и туториалах.  ￼

⸻

5. RDD — что это, когда использовать, пример (wordcount)

Когда RDD? Если вам нужен очень низкоуровневый контроль над распределением/параллелизмом или вы используете операции, отсутствующие в DataFrame API. Для большинства ETL и аналитики в Python лучше DataFrame.  ￼

Пример wordcount на RDD, где вход в HDFS:

from pyspark.sql import SparkSession

spark = SparkSession.builder.appName("rdd-wordcount").getOrCreate()
sc = spark.sparkContext

rdd = sc.textFile("hdfs://namenode:9000/data/input.txt")
words = rdd.flatMap(lambda line: line.split())
pairs = words.map(lambda w: (w.lower(), 1))
counts = pairs.reduceByKey(lambda a, b: a + b)

# Сохраняем результат в HDFS как текст
counts.map(lambda kv: f"{kv[0]}\t{kv[1]}").saveAsTextFile("hdfs://namenode:9000/data/output_wordcount")

Важно про RDD: у них есть lineage (цепочка транформаций) — это помогает восстановиться при сбое; трансформации бывают narrow (map, filter — не требуют перетасовки) и wide (reduceByKey, groupByKey — требуют shuffle).

Источник по RDD — официальное руководство Spark.  ￼

⸻

6. DataFrame (ТД) — основные преимущества и примеры
	•	Оптимизации: DataFrame использует оптимизатор запросов Catalyst и оптимизации выполнения (столбцовая память, кодогенерация). Это даёт существенно лучшие скорости по сравнению с классическими RDD-ми для выраженных SQL/табличных задач.  ￼
	•	API: декларативный (select/filter/groupBy/join), удобный для ETL и аналитики.
	•	Чтение форматов: Parquet/ORC (рекомендуются), Avro, CSV, JSON, JDBC. Parquet — столбцовый формат с поддержкой predicate pushdown и партиционирования.

Пример: чтение Parquet, агрегация, запись:

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count

spark = SparkSession.builder.appName("df-example").getOrCreate()

df = spark.read.parquet("hdfs://namenode:9000/data/parquet/events")
res = df.filter(col("event_type") == "purchase") \
        .groupBy("user_id").agg(count("*").alias("purchases"))

res.write.mode("overwrite").parquet("hdfs://namenode:9000/data/parquet/purchase_per_user")



⸻

7. Лучшие практики работы с данными в HDFS + Spark

a) Выбор формата хранения
	•	Parquet / ORC — приоритет: столбцовый, поддерживает сжатие и predicate pushdown — меньше IO при выборочных колонках.
	•	Для логов/stream — JSON/Avro в зависимости от структуры; для аналитики — Parquet.

b) Партиционирование и файлообразование
	•	Партиционируйте данные по колонкам, по которым часто фильтруете (date, country).
	•	Но не создавайте слишком много маленьких файлов — «small files problem» в HDFS: большое количество маленьких файлов замедляет работу. Перед записью используйте repartition(n) или coalesce(n) чтобы контролировать число выходных файлов.
	•	Используйте df.write.partitionBy("col") для партиционирования на уровне файловой структуры.

c) Минимизируйте shuffle
	•	Joins и groupBy могут вызвать shuffle — дорого. Используйте:
	•	broadcast join для маленькой таблицы (broadcast(small_df)), чтобы избежать shuffle.
	•	Ручное repartition по ключу перед join, если нужно.
	•	Настройте spark.sql.shuffle.partitions под ваш кластер (по умолчанию значение может быть большим для dev-среды — проверьте).

d) Кэширование и persist
	•	Кэшируйте часто используемые промежуточные DataFrame/RDD (df.cache() / df.persist(StorageLevel.MEMORY_AND_DISK)), но не весь кластер — контролируйте память.
	•	Для длинных вычислительных цепочек используйте checkpointing (для прерывания очень длинной lineage).

e) Производительность Python (PySpark) — особенности
	•	Python UDF (обычные) медленные: избегайте их, если есть встроенные функции Spark SQL.
	•	Для сложной логики используйте pandas UDF (vectorized UDF) + Apache Arrow — они дают большой прирост.
	•	Предпочтительнее mapPartitions и foreachPartition для операций, которые инициализируют внешние соединения (экономия на создании соединений).

f) Сжатие
	•	Parquet обычно сжат Snappy (быстро и эффективно). Подбирайте компромисс скорость/размер.

g) Структура схемы/валидность данных
	•	Явно задавайте схему при чтении CSV/JSON — это быстрее и безопаснее.
	•	Работайте с nullable-колонками аккуратно; проверяйте грязные строки (badRecordsPath или mode="DROPMALFORMED").

h) Управление ресурсами и настройка
	•	Тестируйте настройки executor/driver, memory/cores. Следите за GC.
	•	Для продовых задач используйте spark-submit со --conf spark.executor.memory=... и т.д.

⸻

8. Тонкости соединения Spark <-> HDFS (практические советы)
	•	Если Spark не видит hdfs://..., убедитесь, что у Spark в classpath есть Hadoop client jars и что $HADOOP_CONF_DIR указывает на директорию с core-site.xml/hdfs-site.xml.
	•	Для secured кластера: перед запуском kinit либо настройка keytab/principal; при использовании WebHDFS — настройка SPNEGO (см. WebHDFS docs).  ￼
	•	Читайте небольшие lookup-файлы не через sc.textFile (распределённое чтение) — используйте SparkFiles или загрузите их на драйвер и broadcast, если это lookup таблицы.

⸻

9. Примеры «продвинутого» кода и сценариев

9.1 Broadcast join (уменьшаем shuffle)

from pyspark.sql.functions import broadcast

big = spark.read.parquet("hdfs://namenode:9000/big_table")
small = spark.read.parquet("hdfs://namenode:9000/small_ref")

joined = big.join(broadcast(small), on="key", how="left")

9.2 Пример mapPartitions (эффективно для Python)

def process_partition(iter_rows):
    # инициализация внешнего ресурса раз на партицию
    conn = open_db_connection()
    for row in iter_rows:
        yield process_row_with_conn(row, conn)
    conn.close()

rdd = sc.textFile("hdfs://...").mapPartitions(process_partition)

9.3 Pandas UDF (vectorized)

import pandas as pd
from pyspark.sql.functions import pandas_udf
from pyspark.sql.types import DoubleType

@pandas_udf(DoubleType())
def my_vec_udf(s: pd.Series) -> pd.Series:
    return s * 2.0  # пример

df = df.withColumn("x2", my_vec_udf(df["x"]))
# включаем Arrow (лучше в конфиге перед созданием SparkSession)
spark.conf.set("spark.sql.execution.arrow.pyspark.enabled", "true")



⸻

10. Стриминг: запись в HDFS (коротко)

Structured Streaming поддерживает файловый sink: можно писать микропартиции в HDFS/Parquet. Но учтите: файловый sink создаёт множество маленьких файлов — продумайте партиционирование и компактирование. Пример стрима -> HDFS: (см. туториалы по Structured Streaming).  ￼

⸻

11. Отладка и мониторинг
	•	Spark UI (driver:4040) — стадии, задачи, DAG, shuffle.
	•	Spark History Server — постфактная аналитика выполнения.
	•	Сохраняйте логи executors, контролируйте GC и OOM.

⸻

12. Общие ошибки и «чаевые»
	•	Ошибка: Permission denied / Authentication failed — проверьте Kerberos / права HDFS.  ￼
	•	Много маленьких файлов — используйте repartition перед write или объединяйте файлы оффлайн.
	•	Плохая производительность при join — попробуйте broadcast, salting (для skew), либо увеличить shuffle partitions.
	•	UDFы медленные — замените на SQL-функции или pandas UDF.
	•	Неправильная схема — задавайте схему при чтении CSV/JSON.

⸻

13. Пример полного ETL — кусочек кода (чтение CSV -> очистка -> write Parquet partitioned)

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, to_timestamp, year, month

spark = SparkSession.builder.appName("etl-example").getOrCreate()

schema = "user_id INT, event_ts STRING, event_type STRING, amount DOUBLE"

df = spark.read.schema(schema).option("header","true") \
         .csv("hdfs://namenode:9000/raw/events/*.csv")

clean = (df.filter(col("user_id").isNotNull())
           .withColumn("event_ts", to_timestamp(col("event_ts"), "yyyy-MM-dd HH:mm:ss"))
           .withColumn("year", year("event_ts"))
           .withColumn("month", month("event_ts")))

# кэшируем если делаем несколько действий
clean.cache()

# агрегация
agg = clean.filter(col("event_type") == "purchase") \
           .groupBy("year","month","user_id") \
           .agg({"amount":"sum"}) \
           .withColumnRenamed("sum(amount)","total_amount")

# записываем паркетом, сжатие Snappy
spark.conf.set("spark.sql.parquet.compression.codec", "snappy")
agg.write.mode("overwrite").partitionBy("year","month") \
       .parquet("hdfs://namenode:9000/warehouse/purchases")



⸻

14. Резюме рекомендаций (шпаргалка)
	•	Для Python: DataFrame — основной инструмент; RDD — экстренный инструмент при особых требованиях.  ￼
	•	Храните аналитические данные в Parquet/ORC, с партиционированием по колонкам, по которым часто фильтруете.
	•	Контролируйте число выходных файлов (repartition/coalesce).
	•	Избегайте shuffle там, где можно (broadcast joins, предварительное репартиционирование по ключу).
	•	Настройте доступ к HDFS (конфиги, Kerberos) — это обычно первая проблема на практике.  ￼

⸻

15. Ресурсы и ссылки (читаемые, official/relevant)
	•	Spark SQL, DataFrames and Datasets guide — официальная документация Spark (DataFrame/SQL).  ￼
	•	RDD Programming Guide — официальное руководство по RDD.  ￼
	•	Databricks — сравнение RDD, DataFrame и Dataset (рекомендации).  ￼
	•	Примеры чтения/записи из HDFS (how-to / tutorials).  ￼
	•	WebHDFS / Kerberos — официальная документация Hadoop WebHDFS (аутентификация).  ￼