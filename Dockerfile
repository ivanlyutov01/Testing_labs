# Базовый образ — лёгкий Python 3.12
FROM python:3.12-slim

# Рабочая директория внутри контейнера
WORKDIR /app

# Копируем файл зависимостей и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код проекта
COPY KPI_report_generator.py .
COPY test_kpi.py .

# По умолчанию — запуск тестов
CMD ["python", "-m", "pytest", "test_kpi.py", "-v"]
