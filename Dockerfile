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
