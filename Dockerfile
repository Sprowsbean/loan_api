# 1. Start from an official, small Python image
FROM python:3.12-slim

# 2. Print logs immediately and do not write .pyc files
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# 3. All following commands run in /app inside the image
WORKDIR /app

# 4. Install dependencies FIRST: this layer is reused until requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Train the model inside the image (reused until train.py or requirements change)
COPY train.py .
RUN python train.py

# 6. Copy the rest of the code LAST: it changes most often, so only this layer rebuilds
COPY . .

# 7. Document the port and set the command that starts the API
EXPOSE 8000
CMD ["fastapi", "run", "main.py", "--port", "8000"]