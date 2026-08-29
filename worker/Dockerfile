FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./

FROM base AS dev
RUN pip install -r requirements-dev.txt
COPY . .
EXPOSE 9100
CMD ["python", "main.py"]

FROM base AS production
RUN pip install -r requirements.txt
COPY . .
EXPOSE 9100
CMD ["python", "main.py"]
