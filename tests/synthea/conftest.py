"""Test fixtures."""
from _pytest.fixtures import fixture


@fixture
def data_path():
    """Fixture where to read data."""
    return './tests/fixtures/synthea/filtered'


@fixture
def output_path():
    """Fixture where to write data."""
    return './tests/fixtures/synthea/output'


@fixture
def pfb_path():
    """Fixture where to write data."""
    return './tests/fixtures/synthea/output/synthea.pfb.avro'


@fixture
def input_paths():
    """File paths."""
    return """
        tests/fixtures/synthea/filtered/HospitalInformation.json
        tests/fixtures/synthea/filtered/DocumentReference.ndjson
        tests/fixtures/synthea/filtered/DiagnosticReport.ndjson
        tests/fixtures/synthea/filtered/Procedure.ndjson
        tests/fixtures/synthea/filtered/PractitionerInformation.json
        tests/fixtures/synthea/filtered/Observation.ndjson
        tests/fixtures/synthea/filtered/Condition.ndjson
        tests/fixtures/synthea/filtered/Encounter.ndjson
        tests/fixtures/synthea/filtered/Immunization.ndjson
        tests/fixtures/synthea/filtered/Patient.ndjson
    """.strip().split()


@fixture
def config_path():
    """Fixture where to read config."""
    return 'tests/fixtures/synthea/config.yaml'
