FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY app ./app
COPY static ./static
COPY assets ./assets

RUN mkdir -p /data /uploads/records /uploads/roasters

EXPOSE 3000

CMD ["python", "app/server.py"]
