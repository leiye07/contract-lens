FROM python:3.12.12-slim-bookworm AS build
WORKDIR /build
COPY requirements.lock .
RUN pip wheel --require-hashes --wheel-dir /wheels -r requirements.lock
FROM python:3.12.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN useradd --uid 10002 --create-home contractlens
WORKDIR /app
COPY --from=build /wheels /wheels
COPY requirements.lock .
RUN pip install --no-index --find-links=/wheels --require-hashes -r requirements.lock && rm -rf /wheels
COPY --chown=contractlens:contractlens contractlens ./contractlens
USER contractlens
CMD ["uvicorn","contractlens.api:app","--host","0.0.0.0","--port","8020","--no-access-log"]
