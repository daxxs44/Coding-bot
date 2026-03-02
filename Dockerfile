FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY code_helper_bot.py .

CMD ["python", "code_helper_bot.py"]
