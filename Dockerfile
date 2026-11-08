# Web image preparation only; Docker is unavailable locally, so build unverified.
# Resolve an approved immutable base-image digest before deployment.
FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements-runtime.txt ./
RUN pip install --no-cache-dir -r requirements-runtime.txt
COPY paper_pms ./paper_pms
USER 65532:65532
EXPOSE 8080
CMD ["gunicorn", "--no-control-socket", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "2", "--timeout", "30", "paper_pms.web:application"]
