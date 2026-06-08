# Cloud Run image for the Advocate ADK agent.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080 \
    # ADK reads these to route Gemini through Vertex AI (no API keys in source).
    GOOGLE_GENAI_USE_VERTEXAI=TRUE

WORKDIR /app

# Copy source before install so hatchling can build the advocate wheel, then install the
# `agent` extra (google-adk + Cloud Trace exporter). adk lives in an extra now because it
# is dependency-incompatible with the gradio `ui` extra (see pyproject.toml).
COPY pyproject.toml README.md ./
COPY advocate ./advocate
COPY agent_apps ./agent_apps
COPY demo_target_companies.csv demo_alumni_contacts.csv ./
RUN pip install --upgrade pip && pip install ".[agent]"

EXPOSE 8080
CMD ["python", "-m", "advocate.app"]
