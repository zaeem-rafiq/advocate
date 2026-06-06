# Cloud Run image for the Advocate ADK agent.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080 \
    # ADK reads these to route Gemini through Vertex AI (no API keys in source).
    GOOGLE_GENAI_USE_VERTEXAI=TRUE

WORKDIR /app

# Install deps first for layer caching.
COPY pyproject.toml README.md ./
RUN pip install --upgrade pip && pip install .

# App code, agent packages, and the seeded/connected CSVs.
COPY advocate ./advocate
COPY agent_apps ./agent_apps
COPY demo_target_companies.csv demo_alumni_contacts.csv ./

EXPOSE 8080
CMD ["python", "-m", "advocate.app"]
