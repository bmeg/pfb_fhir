"""Test fixtures."""
from _pytest.fixtures import fixture


@fixture
def data_path():
    """Fixture where to read data."""
    return './tests/demo/ncpi/examples'


@fixture
def output_path():
    """Fixture where to write data."""
    return './tests/fixtures/ncpi/output'


@fixture
def pfb_path():
    """Fixture where to write data."""
    return './tests/fixtures/ncpi/output/ncpi.pfb.avro'


@fixture
def patient_input_path():
    """Single patient."""
    return 'tests/fixtures/ncpi/examples/Patient-patient-example-1.json'


@fixture
def input_ncpi_patient_paths():
    """File paths."""
    return [
        'tests/fixtures/ncpi/examples/Practitioner-practitioner-example-1.json',
        'tests/fixtures/ncpi/examples/Organization-organization-example-1.json',
        'tests/fixtures/ncpi/examples/PractitionerRole-practitioner-role-example-1.json',
        'tests/fixtures/ncpi/examples/ResearchStudy-research-study-example-1.json',
        'tests/fixtures/ncpi/examples/Patient-patient-example-3.json',
        'tests/fixtures/ncpi/examples/Patient-patient-example-1.json',
        'tests/fixtures/ncpi/examples/ResearchSubject-research-subject-example-3.json',
        'tests/fixtures/ncpi/examples/Specimen-specimen-example-1.json',
        'tests/fixtures/ncpi/examples/Observation-family-relationship-example-4.json',
        'tests/fixtures/ncpi/examples/DocumentReference-research-document-reference-example-1.json',
        'tests/fixtures/ncpi/examples/Task-task-example-2.json',
    ]


@fixture
def config_path():
    """Fixture where to read config."""
    return 'tests/fixtures/ncpi/config.yaml'


@fixture
def observation_expected_properties():
    """Fixture of flattened properties names."""
    return {
        'code.coding.0.code', 'code.coding.0.display', 'code.coding.0.system', 'component.0.code.coding.0.code', 'component.0.code.coding.0.display', 'component.0.code.coding.0.system', 'component.0.valueInteger',
        'component.1.code.coding.0.code', 'component.1.code.coding.0.display', 'component.1.code.coding.0.system', 'component.1.valueInteger',
        'component.2.code.coding.0.code', 'component.2.code.coding.0.display', 'component.2.code.coding.0.system', 'component.2.valueQuantity.code', 'component.2.valueQuantity.system', 'component.2.valueQuantity.value',
        'component.3.code.coding.0.code', 'component.3.code.coding.0.display', 'component.3.code.coding.0.system', 'component.3.valueString',
        'component.4.code.coding.0.code', 'component.4.code.coding.0.display', 'component.4.code.coding.0.system',
        'component.5.code.coding.0.code', 'component.5.code.coding.0.display', 'component.5.code.coding.0.system', 'component.5.valueString',
        'component.6.code.coding.0.code', 'component.6.code.coding.0.display', 'component.6.code.coding.0.system', 'component.6.valueString', 'component.7.code.coding.0.code', 'component.7.code.coding.0.display', 'component.7.code.coding.0.system', 'component.7.valueString',
        'focus.0.reference',
        'id',
        'resourceType',
        'status'
    }


@fixture
def organization_expected_properties():
    """Fixture of flattened properties names."""
    return {'id', 'identifier.0.system', 'identifier.0.value', 'partOf.reference', 'resourceType'}


@fixture
def practitioner_role_expected_properties():
    """Fixture of flattened properties names."""
    return {'id', 'identifier.0.system', 'identifier.0.value', 'organization.reference', 'practitioner.reference', 'resourceType'}


@fixture
def research_study_expected_properties():
    """Fixture of flattened properties names."""
    return {'id', 'identifier.0.system', 'identifier.0.value', 'identifier.1.system', 'identifier.1.value', 'identifier.2.system', 'identifier.2.value', 'resourceType', 'sponsor.reference', 'status'}


@fixture
def document_reference_expected_properties():
    """Fixture of flattened properties names."""
    return {'id', 'identifier.0.value', 'subject.reference', 'identifier.0.system', 'resourceType', 'status', 'content.0.attachment.url'}
