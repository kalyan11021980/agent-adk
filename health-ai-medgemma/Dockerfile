FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/
COPY agent_card.json .

RUN pip install --no-cache-dir .

EXPOSE 8001

CMD ["python", "-m", "health_ai_medgemma.server"]
