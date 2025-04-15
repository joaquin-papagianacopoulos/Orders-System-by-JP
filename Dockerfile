FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-setuptools \
    python3-wheel \
    build-essential \
    git \
    wget \
    unzip \
    openjdk-8-jdk \
    zlib1g-dev \
    libncurses5-dev \
    libncursesw5-dev \
    libtinfo5 \
    cmake \
    libffi-dev \
    libssl-dev \
    autoconf \
    automake \
    libtool \
    pkg-config

RUN pip3 install --upgrade pip
RUN pip3 install Cython==0.29.33
RUN pip3 install buildozer==1.4.0

WORKDIR /app

ENTRYPOINT ["buildozer"]