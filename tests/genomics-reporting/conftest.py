"""Test fixtures."""
from _pytest.fixtures import fixture


@fixture
def data_path():
    """Fixture where to read data."""
    return './tests/demo/genomics-reporting/examples'


@fixture
def output_path():
    """Fixture where to write data."""
    return './tests/fixtures/genomics-reporting/output'


@fixture
def pfb_path():
    """Fixture where to write data."""
    return './tests/fixtures/genomics-reporting/output/genomics-reporting.pfb.avro'


@fixture
def input_paths():
    """File paths."""
    return [
        'tests/fixtures/genomics-reporting/examples/Bundle-bundle-oncologyexamples-r4.normalized.json',
    ]


@fixture
def config_path():
    """Fixture where to read config."""
    return 'tests/fixtures/genomics-reporting/config.yaml'

