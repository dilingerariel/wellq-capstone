FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt && useradd --uid 10001 --create-home integration
COPY app ./app
COPY scripts ./scripts
COPY integration ./integration
USER 10001:10001
ENTRYPOINT ["python", "-B", "-m", "integration.bootstrap"]
