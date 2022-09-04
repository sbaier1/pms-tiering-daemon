FROM python:3

WORKDIR /usr/src/app

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY pms_tiering_daemon ./pms_tiering_daemon

RUN pip install --no-cache-dir .

CMD ["python", "pms_tiering_daemon/main.py"]