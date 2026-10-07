# Gece Nöbeti · Hugging Face Space (Docker). Yalnızca Streamlit paneli çalışır (DEMO_MODE=1):
# skorlama panelin içinde yapılır, FastAPI servisi bu imajda yoktur.
FROM python:3.12-slim

# LightGBM'in OpenMP çalışma kitaplığı
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Root olmayan kullanıcı (Spaces uid 1000 bekler)
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEMO_MODE=1 \
    CARD_FRAUD_ROOT=/home/user/app \
    OMP_NUM_THREADS=1
WORKDIR /home/user/app

# Sabitlenmiş bağımlılıklar (space/requirements.txt, `make space-lock` ile üretilir)
COPY --chown=user requirements.txt .
RUN pip install --user -r requirements.txt

COPY --chown=user pyproject.toml README.md LICENSE ./
COPY --chown=user src ./src
RUN pip install --user --no-deps .

COPY --chown=user .streamlit ./.streamlit
COPY --chown=user models ./models
COPY --chown=user data ./data

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health', timeout=4)"
CMD ["streamlit", "run", "src/card_fraud_detection/ui/app.py", \
     "--server.port=8501", "--server.address=0.0.0.0"]
