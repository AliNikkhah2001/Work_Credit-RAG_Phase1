FROM python:3.11-slim
WORKDIR /app
ENV PIP_DEFAULT_TIMEOUT=120
# Optional host-prefetched wheels (CI copies into build context when PyPI is flaky)
COPY wheels/ /wheels/
RUN if ls /wheels/*.whl >/dev/null 2>&1; then \
      pip install --no-cache-dir --no-index --find-links=/wheels fastapi uvicorn ; \
    else \
      pip install --no-cache-dir --retries 10 --default-timeout=120 fastapi uvicorn ; \
    fi
COPY app.py observe.py eval_store.py dashboard_api.py __init__.py ./
ENV TRACE_JSONL=/data/langfuse_traces.jsonl
EXPOSE 3000
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "3000"]
