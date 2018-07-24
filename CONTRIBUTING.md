# Contributing Guidelines

## Setting up for development

* Create and activate a new virtual environment
* `pip install -r dev-requirements.txt`
* (Optional, for integration tests) Run elasticsearch: `docker-compose up`
* Run tests using the following commands:

```
# Run all tests (requires elasticsearch to be running)
pytest

# Skip tests that require elasticsearch to be running
pytest -m "not es"

# Check syntax
flake8
```

### (Optional) Run tests in tox

To run tests against the full environment matrix (all supported Python
and Django versions), we use `tox`.

NOTE: You'll need both the `python2.7` and `python3.6` interpreters installed.
You can do this with pyenv and pyenv-virtualenv using the following steps:

```
# Install python2.7 and python3.6
pyenv install 2.7.15
pyenv install 3.6.5

# Create a new Python 3.6 virtualenv with pyenv-virtualenv
pyenv virtualenv django-elasticsearch-metrics 3.6.5

# Allow usage of your virtualenv, python2.7 and python3.6 simultaneously
echo "django-elasticsearch-metrics\n2.7.15\n3.6.5" > .python-version
```

Then run the tests with tox:

```
tox
```
