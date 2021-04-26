FROM gorialis/discord.py:master

WORKDIR /app
COPY . /app

EXPOSE 8880

RUN pip install -U -r requirements.txt

CMD ["python", "app.py"]