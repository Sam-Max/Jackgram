FROM python:3.11-slim

WORKDIR /app

RUN chmod 777 /app

# Install necessary packages including curl
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*
    
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["bash", "start.sh"]
