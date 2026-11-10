FROM python:3.11-slim
WORKDIR /app
ENV PIP_DEFAULT_TIMEOUT=120
RUN pip install --no-cache-dir --default-timeout=120 fastapi uvicorn
COPY app.py observe.py eval_store.py dashboard_api.py __init__.py ./
ENV TRACE_JSONL=/data/langfuse_traces.jsonl
EXPOSE 3000
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "3000"]
