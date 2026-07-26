FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTCODE=1
ENV PYTHONUNBUFFERED

WORKDIR /app

COPY requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD["uvicron","main:app","--host","0.0.0.0","--port","8000", "--reload"]