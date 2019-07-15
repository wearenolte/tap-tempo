FROM python:3.5.2

RUN apt-get update && apt-get dist-upgrade -y && apt-get -y install \
    python-pip \
    python-dev \
    build-essential \
    libjpeg-dev \
    zlib1g-dev \
    libpq-dev \
    binutils \
    libproj-dev \
    gdal-bin \
    gettext \
    wget \
    libssl-dev

COPY requirements.txt ./
RUN pip install -r requirements.txt