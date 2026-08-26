FROM python:3.10-slim

RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
RUN rm -rf /usr/local/lib/python3.10/ensurepip/_bundled

COPY app.py .

RUN useradd --create-home appuser
USER appuser

EXPOSE 5000

CMD ["python", "app.py"]