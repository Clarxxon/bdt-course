from hdfs import InsecureClient
import json

# Подключение напрямую к NameNode через WebHDFS порт
client = InsecureClient('http://localhost:9870', user='root')

# Генерация тестовых данных
data = [
    {"name": "Alice", "age": 25, "city": "Moscow"},
    {"name": "Bob", "age": 30, "city": "SPb"},
    {"name": "Charlie", "age": 35, "city": "Kazan"}
]

try:
    # Создаем директорию
    client.makedirs('/test', permission='755')
    
    # Записываем файл
    with client.write('/test/simple_data.json', encoding='utf-8', overwrite=True) as writer:
        writer.write(json.dumps(data, indent=2))
    
    print("✅ Файл успешно записан в HDFS")
    
    # Читаем список файлов
    print("\n📁 Содержимое корневой директории:")
    for item in client.list('/', status=True):
        name = item[0]
        item_type = "📁 DIR" if item[1]['type'] == 'directory' else "📄 FILE"
        size = item[1]['length']
        print(f"{item_type}\t{size:>8} bytes\t/{name}")
    
    # Читаем файл обратно
    print("\n📖 Содержимое файла:")
    with client.read('/test/simple_data.json', encoding='utf-8') as reader:
        content = reader.read()
        print(content)

except Exception as e:
    print(f"❌ Ошибка: {e}")
    print("Проверьте:")
    print("1. Запущен ли HDFS: docker-compose ps")
    print("2. Доступен ли WebUI: http://localhost:9870")
    print("3. Правильный ли порт NameNode")