# syntax=docker/dockerfile:1
FROM python:3.9

# Dockerfile to verify minimum development requirements

# setup virtual env
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# setup app
WORKDIR /app

RUN pip install pfb_fhir

# build
# docker build -t pfb_fhir .
# typical run command
# docker run -v $(pwd)/cache:/app/pfb_fhir/cache -v $(pwd)/DEMO:/app/pfb_fhir/DEMO pfb_fhir demo ncpi
ENTRYPOINT ["pfb_fhir"]