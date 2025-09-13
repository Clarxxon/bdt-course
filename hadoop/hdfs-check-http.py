import requests
import json
import pandas as pd
from typing import List, Dict, Optional

class WebHDFSClient:
    def __init__(self, host: str = 'localhost', port: int = 9870, user: str = 'root'):
        self.base_url = f"http://{host}:{port}/webhdfs/v1"
        self.user = user
        self.session = requests.Session()
        self.session.timeout = 30
    
    def create_file(self, hdfs_path: str, content: str) -> bool:
        """Создание файла в HDFS"""
        url = f"{self.base_url}{hdfs_path}?op=CREATE&user.name={self.user}&overwrite=true"
        
        try:
            # Первый запрос - получаем URL для перенаправления
            response = self.session.put(url, allow_redirects=False)
            
            if response.status_code == 307:  # Redirect to DataNode
                redirect_url = response.headers['Location']
                # Второй запрос - записываем данные
                put_response = self.session.put(
                    redirect_url, 
                    data=content.encode('utf-8'),
                    headers={'Content-Type': 'application/octet-stream'}
                )
                
                if put_response.status_code in [200, 201]:
                    print(f"✅ Файл создан: {hdfs_path}")
                    return True
                else:
                    print(f"❌ Ошибка записи: {put_response.status_code}")
                    return False
            else:
                print(f"❌ Ошибка создания: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")
            return False
    
    def read_file(self, hdfs_path: str) -> Optional[str]:
        """Чтение файла из HDFS"""
        url = f"{self.base_url}{hdfs_path}?op=OPEN&user.name={self.user}"
        
        try:
            response = self.session.get(url)
            if response.status_code == 200:
                return response.text
            else:
                print(f"❌ Ошибка чтения: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")
            return None
    
    def list_directory(self, hdfs_path: str = '/') -> List[Dict]:
        """Список файлов в директории"""
        url = f"{self.base_url}{hdfs_path}?op=LISTSTATUS&user.name={self.user}"
        
        try:
            response = self.session.get(url)
            if response.status_code == 200:
                data = response.json()
                return data['FileStatuses']['FileStatus']
            else:
                print(f"❌ Ошибка списка: {response.status_code}")
                return []
        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")
            return []
    
    def make_directory(self, hdfs_path: str) -> bool:
        """Создание директории"""
        url = f"{self.base_url}{hdfs_path}?op=MKDIRS&user.name={self.user}"
        
        try:
            response = self.session.put(url)
            if response.status_code == 200:
                data = response.json()
                if data['boolean']:
                    print(f"✅ Директория создана: {hdfs_path}")
                    return True
                else:
                    print(f"❌ Не удалось создать директорию: {hdfs_path}")
                    return False
            else:
                print(f"❌ Ошибка создания директории: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")
            return False

def main():
    # Создаем клиент
    client = WebHDFSClient(host='localhost', port=9870)
    
    # Проверяем доступность HDFS
    print("🔗 Проверка подключения к HDFS...")
    try:
        test_response = requests.get('http://localhost:9870', timeout=10)
        if test_response.status_code == 200:
            print("✅ HDFS WebUI доступен")
        else:
            print("❌ HDFS недоступен")
            return
    except Exception as e:
        print(f"❌ Не удалось подключиться к HDFS: {e}")
        return
    
    # Создаем директорию
    test_dir = '/test_data'
    client.make_directory(test_dir)
    
    # Генерируем тестовые данные
    sample_data = [
        {"id": 1, "name": "Иван", "age": 25, "city": "Москва", "salary": 50000},
        {"id": 2, "name": "Мария", "age": 30, "city": "СПб", "salary": 60000},
        {"id": 3, "name": "Петр", "age": 35, "city": "Казань", "salary": 55000}
    ]
    
    json_content = json.dumps(sample_data, indent=2, ensure_ascii=False)
    
    # Записываем в HDFS
    file_path = f'{test_dir}/employees.json'
    if client.create_file(file_path, json_content):
        # Выводим список файлов
        print(f"\n📁 Содержимое {test_dir}:")
        items = client.list_directory(test_dir)
        for item in items:
            item_type = "📁 DIR" if item['type'] == 'DIRECTORY' else "📄 FILE"
            print(f"{item_type} {item['length']:>8} bytes {item['pathSuffix']}")
        
        # Читаем файл
        print(f"\n📖 Чтение файла {file_path}:")
        content = client.read_file(file_path)
        if content:
            try:
                data = json.loads(content)
                print(f"📊 Прочитано {len(data)} записей")
                for item in data:
                    print(f"   👤 {item['name']} - {item['city']}")
            except json.JSONDecodeError:
                print("Содержимое файла:")
                print(content)

if __name__ == "__main__":
    main()