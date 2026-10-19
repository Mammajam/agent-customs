# Dashboard image: evaluation numbers and the try-a-package box. Stdlib only, no build step.
FROM python:3.12-slim

WORKDIR /app
COPY customs ./customs
COPY evaluation ./evaluation

ENV HOST=0.0.0.0 \
    PORT=8000 \
    PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["python", "-m", "customs.web"]
