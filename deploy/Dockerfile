FROM python:3.9-slim

RUN useradd -m -u 1001 appuser

RUN python -c "import urllib.request; urllib.request.urlretrieve('http://artifacts.aurora-bank.example/vendor/libfx-1.4.tar.gz', '/tmp/libfx.tar.gz')"

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

USER 1001

CMD ["uvicorn", "services.core.main:app", "--host", "127.0.0.1", "--port", "8000"]
