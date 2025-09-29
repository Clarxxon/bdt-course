## Инструкции по запуску:

1. **Создайте необходимые файлы:**
   - Сохраните Docker Compose файл как `docker-compose.yml`
   - Создайте файл конфигурации `superset_config.py`

2. **Настройте секретный ключ:**
   - Замените `your-secret-key-here` на случайную строку в обоих файлах
   - Можно сгенерировать ключ командой: `openssl rand -base64 42`

3. **Запустите приложение:**
   ```bash
   docker-compose up -d
   ```

4. **Создайте администратора (опционально):**
   ```bash
   docker-compose exec superset superset fab create-admin \
     --username admin \
     --firstname Admin \
     --lastname User \
     --email admin@example.com \
     --password admin
   ```

5. **Примените миграции и инициализируйте Superset:**
   ```bash
   docker-compose exec superset superset db upgrade
   docker-compose exec superset superset init
   ```

6. **Доступ к приложению:**
   - Superset будет доступен по адресу: `http://localhost:8088`

## Важные замечания:

- Для продакшн-среды обязательно измените пароли БД и секретный ключ
- Настройте правильные volume для персистентности данных
- Рассмотрите использование внешней БД вместо контейнера для продакшна
- Настройте SSL/TLS для безопасного доступа