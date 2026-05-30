"""Root conftest — makes the flat-layout top-level modules importable in tests.

pytest prepends the directory containing the first conftest.py onto sys.path, so
``import config_loader``, ``import state``, ``import data.alpaca_client`` etc. all
resolve from the repo root without an installed package.
"""
