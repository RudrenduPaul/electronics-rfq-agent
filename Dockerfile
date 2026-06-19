FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml ./
COPY src/ ./src/

RUN uv pip install --system -e .

COPY . .

ENV OPENQUOTE_USE_MOCK=true
ENV PYTHONUNBUFFERED=1

CMD ["python", "-c", "from openquote import QuoteAgent; print('openquote ready')"]
