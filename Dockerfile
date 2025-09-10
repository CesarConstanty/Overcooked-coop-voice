<<<<<<< HEAD
FROM python:3.11

WORKDIR /overcooked

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY . .

EXPOSE 5000
ENV FLASK_ENV=production

CMD [ "python", "app.py" ]

# docker build -t overcooked:dev .
# docker run -it --rm -p 5000:5000 overcooked:dev
=======
FROM python:3.11

WORKDIR /overcooked

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY . .

EXPOSE 5000
ENV FLASK_ENV=production

CMD [ "python", "app.py" ]

# docker build --no-cache -t overcooked:xp1 .
# docker run -it --rm -p 5000:5000 overcooked:xp1
# docker save overcooked:xp1 | gzip > overcooked_xp1.tar.gz
# sha256sum overcooked_xp1.tar.gz > overcooked_xp1.tar.gz.sha256
>>>>>>> toward_experiement_1
