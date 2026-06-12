# Contributing
(TODO: expand)

## code conventions

### naming

### docstrings

### type annotations

### ...

## setting up local devloop

### get a copy of the code
for example:
```
git clone https://github.com/CenterForOpenScience/django-elasticsearch-metrics.git djelme
cd djelme
```

### be in a fitting environment
create and activate a [python virtual environment](https://docs.python.org/3.14/tutorial/venv.html)
with python version 3.10+ and [`poetry` for python package management](https://python-poetry.org) -- there are many ways to do this (including with `poetry` itself); you may already have your own way.

(if you'd rather work with containers and `docker-compose`-likes, see `using docker-style container tools`, below)

here's an example using `venv` (in python's standard lib) to create the virtual environment in a `.venv` directory, with bash:
```
python -m venv .venv && source .venv/bin/activate
```

install [poetry](https://python-poetry.org):
```
pip install poetry
```

install the current project (in editable mode) and dependencies (with the `dev` dependency group and the extras `elastic6`, `elastic8`, `anydjango`):
```
poetry install --with=dev --extras=elastic6 --extras=elastic8 --extras=anydjango
```

### run tests and checks

these expect elasticsearches to be running and configured in `elasticsearch_metrics/tests/settings.py` (or set environment variables `ELASTICSEARCH6_URL` and `ELASTICSEARCH8_URL`) -- see `using docker-style container tools`, below, for one way to do that

running the python module `elasticsearch_metrics.tests` will run tests and linting checks
-- any code merged to `main` should pass for all supported python and django combinations

```
python -m elasticsearch_metrics.tests
```
without args, equivalent to `--test --lint`

optional args:
- `--test`: run tests and display code coverage report
- `--lint`: run linting checks
- `--autofix`: autofix linting errors; autoformat code
- `--no-coverage`: skip gathering and reporting code coverage

any additional args are passed thru to [django-admin test](https://docs.djangoproject.com/en/5.2/ref/django-admin/#test)

example devloop:
```
python -m elasticsearch_metrics.tests --failfast --pdb
```
see `elasticsearch_metrics/tests/__main__.py` for more details

### Run the shell with:

```
konch allow
konch
```

### (Optional) Run tests in tox

To run tests against the full environment matrix (all supported Python
and Django versions), we use `tox`.

NOTE: will skip Python versions not found in this environment
-- to run all python versions, need to install them

Run the tests with tox:

```
tox
```

### (optional) using docker-style container tools
see `testbox.Containerfile` and `docker-compose.yml` for a local setup -- running `testbox` runs `python -m elasticsearch_metrics.tests`

(note: examples use `pc` aliased to a `docker-compose` equivalent)

start elasticsearches in the background
```
pc up -d elasticsearch6 elasticsearch8
```

run tests and lint
```
pc up testbox
```

example devloop -- build with current code, lint and run tests with debugger on error, stop on failure
```
pc run --build --rm --no-deps testbox poetry run python -m elasticsearch_metrics.tests --failfast --pdb
```
