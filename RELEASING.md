# Releasing

1. Bump the version in `elasticsearch_metrics/__init__.py` and update
   CHANGELOG.md.
2. Commit: `git commit -m "Bump version and update changelog"`
3. Tag the commit: `git tag x.y.z`
4. Push the tag: `git push --tags origin master`

Travis will take care of releasing to PyPI.
