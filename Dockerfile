FROM python:3

WORKDIR /usr/src/app

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

