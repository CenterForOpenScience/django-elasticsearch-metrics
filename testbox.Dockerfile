FROM python:3.7-slim as testbox

RUN pip install -U tox

RUN mkdir -p /code
WORKDIR /code
COPY ./ /code

CMD ["tox"]
