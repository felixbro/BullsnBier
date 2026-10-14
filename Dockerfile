# Bulls'n'Bier – Demo/Simulator im Container (ohne Kameras)
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 SIM=1 DATA_DIR=/data VOICES_DIR=/app/voices
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements-voice.txt ./
RUN pip install -r requirements.txt -r requirements-voice.txt
COPY . .
# Natürliche Stimme gleich ins Image (beim Bauen ~100 MB Download). Ohne: --build-arg VOICES=""
ARG VOICES="de_DE-thorsten-high"
RUN if [ -n "$VOICES" ]; then python run.py --get-voice $VOICES; fi
VOLUME /data
EXPOSE 8080
CMD ["python", "run.py", "--sim", "--host", "0.0.0.0", "--port", "8080", "--data", "/data"]
