FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 libgomp1 && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir ".[paddle]" && useradd --create-home ocr && mkdir /models && chown ocr:ocr /models
ENV OBSCURA_OCR_MODEL_HOME=/models
USER ocr
EXPOSE 18083
CMD ["obscura-ocr", "serve", "--host", "0.0.0.0", "--port", "18083"]
