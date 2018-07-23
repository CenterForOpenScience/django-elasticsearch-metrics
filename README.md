# django-elasticsearch-metrics

[![Build Status](https://travis-ci.org/sloria/django-elasticsearch-metrics.svg?branch=master)](https://travis-ci.org/sloria/django-elasticsearch-metrics)

Django app for storing time-series metrics in Elasticsearch.

**Work in progress**


## Development

* Create and activate a new virtual environment
  * NOTE: You'll need both the `python2.7` and
      `python3.6` interpreters installed. 
      You can do this with pyenv and pyenv-virtualenv using the following steps:

```console
# Install python2.7 and python3.6
pyenv install 2.7.15
pyenv install 3.6.5

# Create a new Python 3.6 virtualenv with pyenv-virtualenv
pyenv virtualenv django-elasticsearch-metrics 3.6.5

# Allow usage of your virtualenv, python2.7 and python3.6 simultaneously
echo "django-elasticsearch-metrics\n2.7.15\n3.6.5" > .python-version
```

* `pip install -r dev-requirements.txt`
* (Optional, for integration tests) Run elasticsearch: `docker-compose up`
* To run tests: `tox`

## License

MIT Licensed.
