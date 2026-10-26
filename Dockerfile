FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg nodejs && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir 'yt-dlp[default]'
WORKDIR /app
COPY . .
EXPOSE 3000
CMD ["python", "server.py"]
