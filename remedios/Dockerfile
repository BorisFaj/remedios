FROM onerahmet/ffmpeg:n7.1 AS ffmpeg
FROM nvidia/cuda:12.6.3-base-ubuntu22.04

ENV PYTHON_VERSION=3.10
ENV POETRY_VENV=/remedios/.venv

RUN export DEBIAN_FRONTEND=noninteractive \
    && apt-get -qq update \
    && apt-get -qq install --no-install-recommends \
    python${PYTHON_VERSION} \
    python${PYTHON_VERSION}-venv \
    python3-pip \
    libcudnn8 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN ln -s -f /usr/bin/python${PYTHON_VERSION} /usr/bin/python3 && \
    ln -s -f /usr/bin/python${PYTHON_VERSION} /usr/bin/python && \
    ln -s -f /usr/bin/pip3 /usr/bin/pip

RUN python3 -m venv $POETRY_VENV \
    && $POETRY_VENV/bin/pip install -U pip setuptools \
    && $POETRY_VENV/bin/pip install poetry==2.1.1

ENV PATH="${PATH}:${POETRY_VENV}/bin"

COPY . /remedios
WORKDIR /remedios/

RUN poetry config virtualenvs.in-project true

COPY --from=ffmpeg /usr/local/bin/ffmpeg /usr/local/bin/ffmpeg

# Dependencias remedios ANTES que torch
RUN $POETRY_VENV/bin/pip install transformers==4.49.0 accelerate==0.27.2
RUN $POETRY_VENV/bin/pip install confluent_kafka accelerate bark scipy pydub dotenv
RUN $POETRY_VENV/bin/pip install torch==2.6.0+cu126 torchaudio==2.6.0+cu126 --index-url https://download.pytorch.org/whl/cu126

CMD ["/remedios/.venv/bin/python", "-m", "consumer"]
