FROM python:3.9-slim as testbox

RUN mkdir -p /code
WORKDIR /code
COPY ./ /code

RUN pip install .[dev]
RUN pip install Django==3.2.15

ENV TOXENV py39-django32-es7
CMD ["tox"]
