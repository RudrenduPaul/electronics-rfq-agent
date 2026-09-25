FROM python:3.12-slim@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.12.19@sha256:04d046b13e60d6bcec73cbc5e1cad25d680dea90c8573340950a0ac2d1aef424 /uv /usr/local/bin/uv

COPY pyproject.toml ./
COPY src/ ./src/

RUN uv pip install --system -e .

COPY . .

ENV ERFA_USE_MOCK=true
ENV PYTHONUNBUFFERED=1

CMD ["python", "-c", "from electronics_rfq_agent import QuoteAgent; print('electronics-rfq-agent ready')"]
