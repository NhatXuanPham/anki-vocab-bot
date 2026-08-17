FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

RUN python -c "import nltk; \
nltk.download('wordnet'); \
nltk.download('omw-1.4')"

COPY . .

CMD ["python", "bot.py"]