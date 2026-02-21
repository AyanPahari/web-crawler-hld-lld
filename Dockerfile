FROM python:3.11-slim

WORKDIR /app

# system deps for lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libxml2-dev libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# download nltk stopwords corpus at build time so runtime doesn't need internet
RUN python -c "import nltk; nltk.download('stopwords'); nltk.download('punkt')"

COPY . .

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
