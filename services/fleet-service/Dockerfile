FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /srv

COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements.txt

COPY app ./app

# --- test stage: `docker build --target test .` runs the suite inside the image
FROM base AS test
RUN pip install -r requirements-dev.txt
COPY tests ./tests
RUN python -m pytest -q

# --- runtime stage
FROM base AS runtime
RUN useradd --create-home --uid 10001 appuser
USER appuser
EXPOSE 8001
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8001/health', timeout=2).status == 200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
