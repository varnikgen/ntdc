# Сборка: если в vendor/py311-linux лежат .whl — pip без сети.
# Иначе нужен выход в pypi.org. У Podman rootless часто Errno 101 —
# тогда: podman build --network=host  ИЛИ скачать колёса на Windows.
FROM python:3.11-slim

WORKDIR /app

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=60 \
    PYTHONDONTWRITEBYTECODE=1

RUN useradd --create-home --uid 1000 ntdc

COPY requirements.txt .
COPY vendor/ ./vendor/

RUN set -e; \
    if ls vendor/py311-linux/*.whl >/dev/null 2>&1; then \
        echo "Installing from vendor/py311-linux (offline)"; \
        pip install --no-cache-dir --no-index --find-links vendor/py311-linux -r requirements.txt; \
    else \
        echo "No vendor wheels; installing from PyPI"; \
        pip install --no-cache-dir \
            --trusted-host pypi.org \
            --trusted-host files.pythonhosted.org \
            --retries 10 \
            -r requirements.txt; \
    fi

COPY . .
RUN mkdir -p /app/data /app/app/static \
    && chown -R ntdc:ntdc /app

USER ntdc

ENV DATABASE_URL=sqlite:///./data/ntdc.db \
    HOST=0.0.0.0 \
    PORT=8000

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
