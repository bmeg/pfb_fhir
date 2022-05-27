"""Test NCPI."""
import json
import os
from collections import defaultdict

from pfb_fhir import initialize_model
from pfb_fhir.cli import process_files
from pfb_fhir.emitter import pfb, inspect_pfb
from tests import cleanup_emitter


def test_model(config_path, input_ncpi_patient_paths):
    """Test all ncpi fhir resources."""
    model = initialize_model(config_path)
    resource_properties = defaultdict(set)

    for file in input_ncpi_patient_paths:
        for context in process_files(model, file):
            assert context
            for k in ['model', 'properties', 'resource', 'entity']:
                assert getattr(context, k), f"{k} was empty"
            properties = context.properties
            resource = context.resource
            assert resource['id'] and resource['resourceType']
            assert properties['id']
            resource_properties[resource['resourceType']].update(properties.keys())

    assert set(resource_properties['DocumentReference']) == {'content.0.attachment.url', 'context.related.0.reference', 'custodian.reference', 'id', 'meta.profile.0', 'resourceType', 'status', 'subject.reference', 'text.div', 'text.status'}
    expected_patient_key_sets = [
        {'address.0.city', 'address.0.line.0', 'address.0.postalCode', 'address.0.state', 'address.0.text', 'address.0.type', 'address.0.use', 'birthDate', 'contact.0.address.city', 'contact.0.address.line.0', 'contact.0.address.postalCode', 'contact.0.address.state', 'contact.0.address.text', 'contact.0.address.type', 'contact.0.address.use', 'contact.0.gender', 'contact.0.name.family', 'contact.0.name.given.0', 'contact.0.name.given.1', 'contact.0.name.text', 'contact.0.name.use', 'contact.0.relationship.0.coding.0.code', 'contact.0.relationship.0.coding.0.display', 'contact.0.relationship.0.coding.0.system', 'contact.0.relationship.0.text', 'contact.0.telecom.0.rank', 'contact.0.telecom.0.system', 'contact.0.telecom.0.use', 'contact.0.telecom.0.value', 'contact.1.address.city', 'contact.1.address.line.0', 'contact.1.address.postalCode', 'contact.1.address.state', 'contact.1.address.text', 'contact.1.address.type', 'contact.1.address.use', 'contact.1.gender', 'contact.1.name.family', 'contact.1.name.given.0', 'contact.1.name.given.1', 'contact.1.name.text', 'contact.1.name.use', 'contact.1.relationship.0.coding.0.code', 'contact.1.relationship.0.coding.0.display', 'contact.1.relationship.0.coding.0.system', 'contact.1.relationship.0.text', 'contact.1.telecom.0.rank', 'contact.1.telecom.0.system', 'contact.1.telecom.0.use', 'contact.1.telecom.0.value', 'extension.0.extension.0.url', 'extension.0.extension.0.valueCoding.code', 'extension.0.extension.0.valueCoding.display', 'extension.0.extension.0.valueCoding.system', 'extension.0.extension.1.url', 'extension.0.extension.1.valueCoding.code', 'extension.0.extension.1.valueCoding.display', 'extension.0.extension.1.valueCoding.system', 'extension.0.extension.2.url', 'extension.0.extension.2.valueString', 'extension.0.url', 'extension.1.extension.0.url', 'extension.1.extension.0.valueCoding.code', 'extension.1.extension.0.valueCoding.display', 'extension.1.extension.0.valueCoding.system', 'extension.1.extension.1.url', 'extension.1.extension.1.valueCoding.code', 'extension.1.extension.1.valueCoding.display', 'extension.1.extension.1.valueCoding.system', 'extension.1.extension.1.valueString', 'extension.1.extension.2.url', 'extension.1.extension.2.valueString', 'extension.1.url', 'gender', 'id', 'name.0.family', 'name.0.given.0', 'name.0.given.1', 'name.0.text', 'name.0.use', 'resourceType', 'telecom.0.rank', 'telecom.0.system', 'telecom.0.use', 'telecom.0.value', 'text.div', 'text.status'},
        {'address.0.city', 'address.0.line.0', 'address.0.postalCode', 'address.0.state', 'address.0.text', 'address.0.type', 'address.0.use', 'contact.0.address.city', 'contact.0.address.line.0', 'contact.0.address.postalCode', 'contact.0.address.state', 'contact.0.address.text', 'contact.0.address.type', 'contact.0.address.use', 'contact.0.gender', 'contact.0.name.family', 'contact.0.name.given.0', 'contact.0.name.given.1', 'contact.0.name.text', 'contact.0.name.use', 'contact.0.relationship.0.coding.0.code', 'contact.0.relationship.0.coding.0.display', 'contact.0.relationship.0.coding.0.system', 'contact.0.relationship.0.text', 'contact.0.telecom.0.rank', 'contact.0.telecom.0.system', 'contact.0.telecom.0.use', 'contact.0.telecom.0.value', 'extension.0.extension.0.url', 'extension.0.extension.0.valueCoding.code', 'extension.0.extension.0.valueCoding.display', 'extension.0.extension.0.valueCoding.system', 'extension.0.extension.1.url', 'extension.0.extension.1.valueCoding.code', 'extension.0.extension.1.valueCoding.display', 'extension.0.extension.1.valueCoding.system', 'extension.0.extension.2.url', 'extension.0.extension.2.valueString', 'extension.0.url', 'extension.1.extension.0.url', 'extension.1.extension.0.valueCoding.code', 'extension.1.extension.0.valueCoding.display', 'extension.1.extension.0.valueCoding.system', 'extension.1.extension.1.url', 'extension.1.extension.1.valueString', 'extension.1.url', 'gender', 'id', 'name.0.family', 'name.0.given.0', 'name.0.given.1', 'name.0.text', 'name.0.use', 'resourceType', 'telecom.0.rank', 'telecom.0.system', 'telecom.0.use', 'telecom.0.value', 'text.div', 'text.status'}
    ]
    _ok = False
    actual_key_set = set(resource_properties['Patient'])
    for expected_patient_key_set in expected_patient_key_sets:
        if actual_key_set == expected_patient_key_set:
            _ok = True
    assert _ok, f"Unexpected key set: {actual_key_set}"


def test_emitter(config_path, input_ncpi_patient_paths, output_path, pfb_path):
    """Test Input Files vs emitted PFB ."""
    model = initialize_model(config_path)

    with pfb(output_path, pfb_path, model) as pfb_:
        for context in process_files(model, input_ncpi_patient_paths):
            pfb_.emit(context)

    assert os.path.isfile(pfb_path)
    results = inspect_pfb(pfb_path)
    assert len(results.errors) == 0, results.errors
    assert len(results.warnings) == 0, results.warnings

    cleanup_emitter(output_path, pfb_path)


def test_patient_emitter(config_path, patient_input_path, output_path, pfb_path):
    """Test all patient term_def."""
    model = initialize_model(config_path)
    with pfb(output_path, pfb_path, model) as pfb_:
        for context in process_files(model, patient_input_path):
            pfb_.emit(context)
    dump_path = f"{output_path}/dump-ordered.json"
    schema = json.load(open(dump_path))
    assert schema
    assert 'Patient.yaml' in schema
    patient_schema = schema['Patient.yaml']
    properties_with_term_def = [k for k, p in patient_schema['properties'].items() if 'term' in p]
    assert set(properties_with_term_def) == {'contact_0_relationship_0_coding_0_code', 'contact_1_address_use', 'contact_1_gender', 'address_0_use', 'gender', 'text_status', 'address_0_type', 'name_0_use', 'contact_0_address_use', 'contact_1_name_use', 'contact_0_address_type', 'contact_0_name_use', 'contact_0_telecom_0_system', 'contact_0_gender', 'contact_1_address_type', 'contact_1_telecom_0_use', 'contact_1_telecom_0_system', 'telecom_0_system', 'contact_0_telecom_0_use', 'telecom_0_use', 'contact_1_relationship_0_coding_0_code'}

    from pprint import pprint
    properties_with_term_def_but_no_enum = []
    for k in properties_with_term_def:
        if 'enum' not in patient_schema['properties'][k]:
            pprint(patient_schema['properties'][k])
            properties_with_term_def_but_no_enum.append(k)
    assert set(properties_with_term_def_but_no_enum) == {
        'contact_1_relationship_0_coding_0_code',
        'contact_0_relationship_0_coding_0_code'
    }

    cleanup_emitter(output_path, pfb_path)
