# Example 3: Self-hosted with Docker Compose

No cloud services required except the Anthropic API.

```bash
git clone https://github.com/RudrenduPaul/openquote-ai
cd openquote-ai
cp .env.example .env
# Edit .env: add your ANTHROPIC_API_KEY
docker compose up -d
docker compose exec openquote python examples/01-basic-quote/basic_quote.py
```

Your quote data never leaves your environment.
