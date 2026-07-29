FROM python:3.11-slim

WORKDIR /app

# Install system deps for psycopg2
# (Removed apt-get update as psycopg2-binary comes with pre-compiled wheels)

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app

# Default CMD — overridden per service in docker-compose
CMD ["uvicorn", "services.skill_management.main:app", "--host", "0.0.0.0", "--port", "8001"]
