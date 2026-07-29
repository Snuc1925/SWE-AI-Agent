# FROM python:3.11-slim

# WORKDIR /app

# COPY services/agent_orchestrator/requirements.txt /app/requirements.txt
# RUN pip install --no-cache-dir -r /app/requirements.txt
# COPY services/agent_orchestrator/ /app/services/agent_orchestrator/

# # (Tùy chọn) có thư mục "shared" dùng chung cho các service, copy nốt vào
# # COPY shared/ /app/shared/

# CMD ["uvicorn", "services.agent_orchestrator.main:app", "--host", "0.0.0.0", "--port", "8000"]


FROM python:3.10-slim
WORKDIR /app


# Copy file requirements trước để tận dụng cache của Docker
COPY services/skill_testing/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
# RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY . /app

ENV PYTHONPATH=/app

CMD ["uvicorn", "services.skill_testing.main:app", "--host", "0.0.0.0", "--port", "8003", "--workers", "1"]