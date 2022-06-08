"""Test fixtures."""
from _pytest.fixtures import fixture


@fixture
def config_paths():
    """Fixture where to read configs."""
    return [
        'tests/fixtures/synthea/config.yaml',
        'tests/fixtures/ncpi/config.yaml',
        'tests/fixtures/kf/config.yaml',
        'tests/fixtures/genomics-reporting/config.yaml',
        'tests/fixtures/dbgap/config.yaml',
        'tests/fixtures/anvil/config.yaml',
    ]
