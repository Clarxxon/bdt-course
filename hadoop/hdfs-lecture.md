# Использование HDFS и Apache Spark (PySpark)


1. Коротко: что такое HDFS и Spark и почему их вместе используют
	•	HDFS (Hadoop Distributed File System) — распределённая файловая система для больших объёмов данных: хранит файлы, разбивает их на блоки и распределяет по DataNode. Метаданные хранит NameNode.
Даёт надёжное и масштабируемое хранилище для аналитики.
(для деталей: WebHDFS / конфигурация см. официальную документацию).
	•	Apache Spark — вычислительная платформа для распределённой обработки данных (параллельные трансформации, SQL, стриминг, ML).
Spark может читать/писать данные прямо из HDFS и выполнять вычисления над ними.
Предоставляет несколько API:
	•	RDD (низкоуровневое)
	•	DataFrame / SQL (табличное, оптимизируемое)
	•	Dataset (в Scala/Java)

📌 Почему вместе?
HDFS — место хранения, Spark — движок обработки.
HDFS гарантирует репликацию и отказоустойчивость, Spark — быстрое in-memory/дисковое выполнение.

⸻

2. Краткая терминология
	•	RDD (Resilient Distributed Dataset) — фундамент Spark: иммутабельная распределённая коллекция элементов.
	•	Ленивые трансформации и действия.
	•	Даёт полный контроль, но без автоматических оптимизаций.
	•	DataFrame (Табличные данные) — структура с именованными колонками, как таблица в БД.
	•	Использует оптимизатор Catalyst и Tungsten (столбцовая память, кодогенерация).
	•	Удобен для SQL и аналитики.
	•	Трансформации — ленивые операции (map, filter, select, join, groupBy) — выполняются при вызове действия.
	•	Действия — запускают вычисления (count, collect, save, write).

⸻

3. Подготовка окружения
	1.	Совместимость версий: Spark ↔ Hadoop/HDFS (проверяйте матрицу).
	2.	Конфиги Hadoop: core-site.xml, hdfs-site.xml → должны быть доступны Spark.
Частая ошибка: Spark не видит HDFS и работает с локальной FS.
	3.	Kerberos/Безопасность: kinit, keytab, настройка WebHDFS (SPNEGO).
	4.	Путь доступа: hdfs://<namenode>:<port>/path/... или fs.defaultFS.
	5.	Запуск:
	•	Разработка: local[*], pyspark в ноутбуке.
	•	Прод: spark-submit --master yarn / --master spark://....

⸻

4. Подключение PySpark к HDFS — пример

```
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, IntegerType

spark = SparkSession.builder \
    .appName("hdfs-pyspark-example") \
    .getOrCreate()

schema = StructType([
    StructField("user_id", IntegerType(), True),
    StructField("event_ts", StringType(), True),
    StructField("event_type", StringType(), True)
])

df = spark.read.schema(schema) \
    .option("header", "true") \
    .csv("hdfs://namenode:9000/data/events.csv")

from pyspark.sql import functions as F
df = df.withColumn("event_ts", F.to_timestamp("event_ts", "yyyy-MM-dd HH:mm:ss"))
df.show(5)

# Запись в Parquet с партиционированием
df = df.withColumn("year", F.year("event_ts")) \
       .withColumn("month", F.month("event_ts"))

df.write.mode("overwrite").partitionBy("year", "month") \
    .parquet("hdfs://namenode:9000/data/parquet/events")
```


⸻

5. RDD — что это, пример WordCount

Используется для низкоуровневого контроля или специфических операций.
```
from pyspark.sql import SparkSession

spark = SparkSession.builder.appName("rdd-wordcount").getOrCreate()
sc = spark.sparkContext

rdd = sc.textFile("hdfs://namenode:9000/data/input.txt")
words = rdd.flatMap(lambda line: line.split())
pairs = words.map(lambda w: (w.lower(), 1))
counts = pairs.reduceByKey(lambda a, b: a + b)

# Сохраняем результат в HDFS
counts.map(lambda kv: f"{kv[0]}\t{kv[1]}").saveAsTextFile(
    "hdfs://namenode:9000/data/output_wordcount"
)
```
📌 У RDD есть lineage — цепочка преобразований, которая помогает восстановиться при сбое.

⸻

6. DataFrame (ТД) — преимущества и пример
	•	Использует оптимизации Catalyst + Tungsten.
	•	Поддерживает SQL, удобен для ETL.
	•	Форматы: Parquet/ORC (рекомендуются), Avro, CSV, JSON.
```
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count

spark = SparkSession.builder.appName("df-example").getOrCreate()

df = spark.read.parquet("hdfs://namenode:9000/data/parquet/events")

res = df.filter(col("event_type") == "purchase") \
        .groupBy("user_id") \
        .agg(count("*").alias("purchases"))

res.write.mode("overwrite").parquet(
    "hdfs://namenode:9000/data/parquet/purchase_per_user"
)
```


⸻

7. Лучшие практики работы с данными

a) Форматы
	•	Parquet / ORC — для аналитики.
	•	JSON/Avro — для логов и стриминга.

b) Партиционирование
	•	Партиционируйте по колонкам с частыми фильтрами (например, date).
	•	Избегайте small files problem — используйте repartition или coalesce.

c) Минимизация shuffle
	•	Используйте broadcast join для маленьких таблиц.
	•	Настраивайте spark.sql.shuffle.partitions.

d) Кэширование
	•	df.cache() / df.persist() — только для часто используемых.
	•	Для длинной lineage используйте checkpoint.

e) PySpark-особенности
	•	Обычные Python UDF медленные → используйте pandas UDF + Arrow.
	•	Для внешних соединений используйте mapPartitions.

f) Сжатие
	•	Обычно Parquet со Snappy.

g) Схема
	•	Задавайте явно (.schema(...)), особенно для CSV/JSON.

h) Ресурсы
	•	Тюньте --executor-memory, --executor-cores.

⸻

8. Тонкости Spark ↔ HDFS
	•	Проверяйте наличие Hadoop jars и $HADOOP_CONF_DIR.
	•	Для secure-кластера: kinit, keytab, SPNEGO для WebHDFS.
	•	Маленькие lookup-таблицы → broadcast, а не sc.textFile.

⸻

9. Продвинутые примеры

9.1 Broadcast join
```
from pyspark.sql.functions import broadcast

big = spark.read.parquet("hdfs://namenode:9000/big_table")
small = spark.read.parquet("hdfs://namenode:9000/small_ref")

joined = big.join(broadcast(small), on="key", how="left")
```
9.2 mapPartitions
```
def process_partition(iter_rows):
    conn = open_db_connection()
    for row in iter_rows:
        yield process_row_with_conn(row, conn)
    conn.close()

rdd = sc.textFile("hdfs://...").mapPartitions(process_partition)
```
9.3 Pandas UDF
```
import pandas as pd
from pyspark.sql.functions import pandas_udf
from pyspark.sql.types import DoubleType

@pandas_udf(DoubleType())
def my_vec_udf(s: pd.Series) -> pd.Series:
    return s * 2.0

df = df.withColumn("x2", my_vec_udf(df["x"]))
spark.conf.set("spark.sql.execution.arrow.pyspark.enabled", "true")
```


⸻

10. Стриминг: запись в HDFS

Structured Streaming может писать в HDFS (например, в Parquet).
⚠️ Проблема: создаёт много маленьких файлов → используйте партиционирование и compact.

⸻

11. Отладка и мониторинг
	•	Spark UI (driver:4040) — DAG, shuffle, стадии.
	•	History Server — анализ выполненных задач.
	•	Логи executors, GC, OOM.

⸻

12. Общие ошибки
	•	Permission denied → Kerberos / права.
	•	Много маленьких файлов → repartition.
	•	Медленный join → broadcast / salting / настройка shuffle.
	•	Медленные UDF → заменить на SQL-функции или pandas UDF.
	•	Некорректная схема → задавать явно.

⸻

13. Пример ETL (CSV → Parquet)
```
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

clean.cache()

agg = clean.filter(col("event_type") == "purchase") \
           .groupBy("year","month","user_id") \
           .agg({"amount":"sum"}) \
           .withColumnRenamed("sum(amount)","total_amount")

spark.conf.set("spark.sql.parquet.compression.codec", "snappy")

agg.write.mode("overwrite").partitionBy("year","month") \
       .parquet("hdfs://namenode:9000/warehouse/purchases")

```

⸻

14. Шпаргалка
	•	В Python используйте DataFrame API.
	•	Храните данные в Parquet/ORC с партиционированием.
	•	Контролируйте число файлов (repartition).
	•	Минимизируйте shuffle (broadcast, repartition).
	•	Настройте доступ к HDFS (конфиги, Kerberos).

⸻

15. Ресурсы
	•	Spark SQL, DataFrames and Datasets Guide
	•	RDD Programming Guide
	•	Databricks: сравнение RDD vs DataFrame vs Dataset
	•	WebHDFS и Kerberos — официальная документация Hadoop

⸻

Хочешь, я сделаю ещё схему-иллюстрацию (например, Spark ↔ HDFS с DataFrame/RDD) в виде картинки? Это можно вставить в твой .md как диаграмму.