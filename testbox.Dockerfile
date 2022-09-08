FROM python:3.9-slim as testbox

RUN mkdir -p /code
WORKDIR /code
COPY ./ /code

RUN pip install .[dev]

CMD ["tox"]
