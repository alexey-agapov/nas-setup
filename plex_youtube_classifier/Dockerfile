FROM python:3.11-slim

# Install ffmpeg and system deps
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

# Set working dir
WORKDIR /app

# Copy dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your source code
COPY . .

# Run your bot
CMD ["python", "bot_main.py"]
