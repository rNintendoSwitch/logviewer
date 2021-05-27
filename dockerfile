FROM python:3.7-slim

WORKDIR /app
COPY . /app

EXPOSE 8880

RUN pip install -U -r requirements.txt

CMD ["python", "app.py"]