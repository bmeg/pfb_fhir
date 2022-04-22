# syntax=docker/dockerfile:1
FROM python:3.9

# Dockerfile to verify minimum development requirements

# setup virtual env
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# setup app
WORKDIR /app

RUN git clone --branch 0.0.0 https://github.com/bmeg/pfb_fhir /app/pfb_fhir
WORKDIR /app/pfb_fhir

RUN pip install -e .

ENTRYPOINT ["pfb_fhir"]