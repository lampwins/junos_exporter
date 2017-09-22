FROM python:3.6-alpine
LABEL authors="John Anderson <lampwins@gmail.com>"

# Environment
ENV TZ="America/New_York"

# System Prep
RUN apk add --update \
            make \
            gcc \
            libc-dev \
            libffi-dev \
            libxml2 \
            libxslt-dev \
            libffi-dev \
            cmake \
            openssl \
            openssl-dev \
  && echo EST5EDT > /etc/TZ

# Don't reinstall everytime a change is made
COPY requirements.txt .
RUN pip3 install --upgrade pip \
  && pip3 install -r requirements.txt

COPY gunicorn.conf /gunicorn.conf

COPY app.py .
COPY junos_exporter.yaml .

#EXPOSE 9665

#ENTRYPOINT ["/usr/local/bin/gunicorn", "--config", "/gunicorn.conf", "--log-config", "/logging.conf", "-b", ":9665", "app:app"]