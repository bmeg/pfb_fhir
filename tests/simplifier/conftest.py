
from _pytest.fixtures import fixture


@fixture
def input_ncpi_patient_paths():
    """File paths."""
    return [
        'tests/fixtures/ncpi/examples/Patient-patient-example-3.json'
        ]


@fixture
def input_ncpi_specimen_paths():
    """File paths."""
    return [
        'tests/fixtures/ncpi/examples/Specimen-specimen-example-1.json',
        ]


@fixture
def input_synthea_patient_paths():
    """File paths."""
    return [
        'tests/fixtures/synthea/filtered/Patient.ndjson'
        ]


@fixture
def input_synthea_observation_paths():
    """File paths."""
    return [
        'tests/fixtures/synthea/filtered/Observation.ndjson'
        ]


@fixture
def config_path():
    """Fixture where to read config."""
    return 'tests/fixtures/ncpi/config.yaml'


@fixture
def output_path():
    """Fixture where to write data."""
    return './tests/fixtures/ncpi/output'


@fixture
def pfb_path():
    """Fixture where to write data."""
    return './tests/fixtures/ncpi/output/ncpi.pfb.avro'

