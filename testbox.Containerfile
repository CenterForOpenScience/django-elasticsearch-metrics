FROM python:3.13-slim as testbox

RUN pip install poetry==2.3.2

RUN mkdir -p /code
WORKDIR /code

COPY pyproject.toml poetry.lock ./
RUN poetry install --compile --no-root --with=dev --extras=elastic6 --extras=elastic8 --extras=anydjango
COPY ./ ./
RUN poetry install --only-root

CMD ["poetry", "run", "python", "-m", "elasticsearch_metrics.tests"]
