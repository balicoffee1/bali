FROM python:3.10-slim

RUN pip install --upgrade pip

RUN apt-get update && \
    apt-get install -y libpq-dev gcc # чтобы работал psycopg2

RUN mkdir /app

COPY requirements.txt /app

RUN pip3 install -r /app/requirements.txt --no-cache-dir

COPY . /app

WORKDIR /app

CMD ["gunicorn", "island_bali.wsgi:application", "--bind", "0:8000" ]

