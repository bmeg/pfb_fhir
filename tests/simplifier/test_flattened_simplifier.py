import os

import logging
from pfb_fhir import initialize_model
from pfb_fhir.cli import process_files
from pfb_fhir.emitter import pfb, inspect_pfb
from pfb_fhir.context_simplifier import ContextSimplifier
from tests import cleanup_emitter
logger = logging.getLogger(__name__)


def _to_tsv(properties):
    """Print tsv."""
    print()
    print("\t".join([flattened_key for flattened_key in properties]))
    print("\t".join([str(p.value) for p in properties.values()]))


def test_flattened_ncpi_patient_model(config_path, input_ncpi_patient_paths):
    """Borrows fixtures from ncpi fhir resources."""
    model = initialize_model(config_path)

    for file in input_ncpi_patient_paths:
        for context in process_files(model, file, simplify=False):
            assert context
            assert isinstance(context.properties, dict)
            _to_tsv(context.properties)
            print(len(context.properties))

        for context in process_files(model, file, simplify=True):
            assert context
            assert isinstance(context.properties, dict)
            actual_keys = set([k for k in context.properties])
            expected_keys = {'address.city',
                             'address.line',
                             'address.postalCode',
                             'address.state',
                             'address.text',
                             'address.type',
                             'address.use',
                             'contact.address.city',
                             'contact.address.line',
                             'contact.address.postalCode',
                             'contact.address.state',
                             'contact.address.text',
                             'contact.address.type',
                             'contact.address.use',
                             'contact.gender',
                             'contact.name.family',
                             'contact.name.given.0',
                             'contact.name.given.1',
                             'contact.name.text',
                             'contact.name.use',
                             'contact.relationship.coding_v2-0131',
                             'contact.relationship.text',
                             'contact.telecom.rank',
                             'contact.telecom.system',
                             'contact.telecom.use',
                             'contact.telecom.value',
                             'extension_us-core-ethnicity_valueCoding_urn:oid:2.16.840.1.113883.6.238',
                             'extension_us-core-ethnicity_valueString',
                             'extension_us-core-race_valueCoding_urn:oid:2.16.840.1.113883.6.238',
                             'extension_us-core-race_valueString',
                             'gender',
                             'id',
                             'name.family',
                             'name.given.0',
                             'name.given.1',
                             'name.text',
                             'name.use',
                             'resourceType',
                             'telecom.rank',
                             'telecom.system',
                             'telecom.use',
                             'telecom.value',
                             'text.div',
                             'text.status'}
            assert expected_keys == actual_keys
            _to_tsv(context.properties)
            print(len(context.properties))


def test_flattened_synthea_patient_model(config_path, input_synthea_patient_paths):
    """Borrows fixtures from synthea fhir resources."""
    model = initialize_model(config_path)

    for file in input_synthea_patient_paths:
        for context in process_files(model, file, simplify=False):
            assert context
            assert isinstance(context.properties, dict)
            context.properties['id'].value == '9e74daad-30a9-e313-cd29-917f4c258ff8', "First record id unexpected"

            assert context.resource.name
            assert len(context.resource.name) > 1
            assert 'name.0.given.0' in context.properties, "Should have multi_item_lists"
            assert 'name.1.given.0' in context.properties, "Should have multi_item_lists"
            # only first record
            break

    for file in input_synthea_patient_paths:
        for context in process_files(model, file, simplify=True):

            assert 'name.0.given' in context.properties, "Should have multi_item_lists"
            assert 'name.1.given' in context.properties, "Should have multi_item_lists"

            assert len([p for p in context.properties if p.startswith('extension_')]) == 11, context.properties.keys()

            assert len([p for p in context.properties if p.startswith('address')]) == 6, context.properties.keys()
            assert len([p for p in context.properties if p == 'address.extension_geolocation_valueDecimal']) == 1, context.properties.keys()

            #
            # assert len(simplified_properties['Patient.address']) == 10
            # simplified_properties = ContextSimplifier._extensions(simplified_properties)
            # assert len(simplified_properties['Patient.extension']) == 4, "Should simplify root extensions"
            # assert len(simplified_properties['Patient.address']) == 7, f"Should simplify property extensions {[p.flattened_key for p in simplified_properties['Patient.address'] if 'extension' in p.flattened_key]}"
            # address_keys = [p.flattened_key for p in simplified_properties['Patient.address']]
            # assert 'address.0.geolocation.latitude' in address_keys, "Should simplify geolocation"
            # assert 'address.0.geolocation.longitude' in address_keys, "Should simplify geolocation"
            # name_keys = [p.flattened_key for p in simplified_properties['Patient.name']]
            # assert 'name.0.given.0' in name_keys, "Should have multi_item_lists"
            # assert 'name.1.given.0' in name_keys, "Should have multi_item_lists"
            # simplified_properties = ContextSimplifier._single_item_lists(simplified_properties)
            # address_keys = [p.flattened_key for p in simplified_properties['Patient.address']]
            # assert 'address.geolocation.latitude' in address_keys, "Should simplify single_item_lists"
            # assert 'address.geolocation.longitude' in address_keys, "Should simplify single_item_lists"
            # name_keys = [p.flattened_key for p in simplified_properties['Patient.name']]
            # assert 'name.0.given' in name_keys, "Should maintain multi_item_lists"
            # assert 'name.1.given' in name_keys, "Should maintain multi_item_lists"
            #
            # simplified_properties = ContextSimplifier._codings(simplified_properties)
            # marital_status_keys = [p.flattened_key for p in simplified_properties['Patient.maritalStatus']]
            # communication_keys = [p.flattened_key for p in simplified_properties['Patient.communication']]
            # assert set(marital_status_keys) == {'maritalStatus.text', 'maritalStatus.v3-MaritalStatus'}, "Should simplify codings"
            # assert set(communication_keys) == {'communication.language.text', 'communication.language.urn:ietf:bcp:47'}, "Should simplify codings"
            # simplified_properties = ContextSimplifier._identifiers(simplified_properties)
            # identifier_keys = [p.flattened_key for p in simplified_properties['Patient.identifier']]
            # assert set(identifier_keys) == {'identifier.0.synthea', 'identifier.1.MR', 'identifier.2.SS',
            #                                 'identifier.3.DL', 'identifier.4.PPN'}, "Should simplify identifiers"
            # only first record
            break

        for context in process_files(model, file, simplify=True):
            assert context
            assert isinstance(context.properties, dict)
            context.properties['id'].value == '9e74daad-30a9-e313-cd29-917f4c258ff8', "First record id unexpected"
            actual_keys = set([k for k in context.properties])
            expected_keys = {'identifier_SS', 'address.country', 'extension_us-core-race_valueString', 'birthDate',
                             'text.div', 'name.0.use',
                             'extension_us-core-race_valueCoding_urn:oid:2.16.840.1.113883.6.238',
                             'extension_us-core-birthsex', 'name.1.given', 'extension_patient-birthPlace.state',
                             'name.0.family', 'telecom.use', 'address.postalCode', 'name.1.prefix',
                             'extension_us-core-ethnicity_valueCoding_urn:oid:2.16.840.1.113883.6.238',
                             'address.extension_geolocation_valueDecimal', 'address.line', 'name.1.family',
                             'text.status', 'extension_patient-mothersMaidenName', 'meta.profile', 'identifier_DL',
                             'gender', 'identifier_PPN', 'extension_us-core-ethnicity_valueString',
                             'identifier_https://github.com/synthetichealth/synthea', 'maritalStatus.text',
                             'extension_patient-birthPlace.city', 'extension_quality-adjusted-life-years',
                             'communication.language.coding_urn:ietf:bcp:47', 'extension_patient-birthPlace.country',
                             'address.city', 'name.0.prefix', 'address.state', 'name.1.use', 'identifier_MR',
                             'name.0.given', 'maritalStatus.coding_v3-MaritalStatus', 'telecom.system', 'telecom.value',
                             'multipleBirthBoolean', 'extension_disability-adjusted-life-years',
                             'communication.language.text', 'id', 'resourceType'}

            assert expected_keys == actual_keys
            _to_tsv(context.properties)
            print(len(context.properties))
            # only first record
            break


def test_flattened_ncpi_patient_emitter(config_path, input_ncpi_patient_paths, output_path, pfb_path):
    """Borrows fixtures from ncpi fhir resources."""
    model = initialize_model(config_path)

    with pfb(output_path, pfb_path, model) as pfb_:
        for context in process_files(model, input_ncpi_patient_paths, simplify=True):
            pfb_.emit(context)

    assert os.path.isfile(pfb_path)
    results = inspect_pfb(pfb_path)
    assert len(results.errors) == 0, results.errors
    assert len(results.warnings) == 1 and results.warnings == ['No records have relationships.'], results.warnings

    cleanup_emitter(output_path, pfb_path)


def test_flattened_ncpi_specimen_model(config_path, input_ncpi_specimen_paths, output_path, pfb_path):
    """Borrows fixtures from ncpi fhir resources."""
    model = initialize_model(config_path)
    for file in input_ncpi_specimen_paths:
        for context in process_files(model, file, simplify=True):
            actual_keys = set([k for k in context.properties])
            assert '_receivedTime.extension.0.extension.0.url' not in actual_keys
            print(actual_keys)
            break


def test_flattened_synthea_observation_model(config_path, input_synthea_observation_paths):
    """Borrows fixtures from synthea fhir resources."""
    model = initialize_model(config_path)

    for file in input_synthea_observation_paths:
        for context in process_files(model, file, simplify=True):
            actual_keys = set([k for k in context.properties])
            assert actual_keys == {'category.coding_observation-category', 'code.text', 'effectiveDateTime',
                                   'valueQuantity.unit', 'resourceType',
                                   'meta.profile.1', 'id', 'subject.reference', 'status',
                                   'meta.profile.0', 'valueQuantity.value', 'encounter.reference', 'issued',
                                   'valueQuantity.code', 'code.coding_loinc.org', 'valueQuantity.system'}
            break
