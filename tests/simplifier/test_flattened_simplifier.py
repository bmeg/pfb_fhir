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
                             'text.status',
                             'extension_us-core-ethnicity_ombCategory_valueCoding_urn:oid:2.16.840.1.113883.6.238',
                             'extension_us-core-ethnicity_text_valueString',
                             'extension_us-core-race_detailed_valueCoding_urn:oid:2.16.840.1.113883.6.238',
                             'extension_us-core-race_ombCategory_valueCoding_urn:oid:2.16.840.1.113883.6.238',
                             'extension_us-core-race_text_valueString',
                             }
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

            assert len([p for p in context.properties.values() if p.is_extension]) == 13, context.properties.keys()
            assert len([p for p in context.properties.values() if
                        p.is_extension and p.docstring]) == 13, context.properties.keys()

            assert len([p for p in context.properties if p.startswith('address')]) == 7, context.properties.keys()
            assert len(['address.geolocation_latitude', 'address.geolocation_longitude']) == 2, context.properties.keys()
            assert context.properties['address.geolocation_latitude'].typ == 'float'
            assert context.properties['address.geolocation_longitude'].typ == 'float'
            assert context.properties['disability_adjusted_life_years'].typ == 'float'
            assert context.properties['quality_adjusted_life_years'].typ == 'float'

            # only first record
            break

        for context in process_files(model, file, simplify=True):
            assert context
            assert isinstance(context.properties, dict)
            context.properties['id'].value == '9e74daad-30a9-e313-cd29-917f4c258ff8', "First record id unexpected"
            actual_keys = set([k for k in context.properties])
            expected_keys = {'identifier_SS', 'patient_birthPlace.country', 'address.line', 'text.div',
                             'us_core_birthsex', 'text.status', 'meta.profile', 'name.0.family', 'gender',
                             'address.state', 'name.1.use', 'birthDate', 'id', 'telecom.use', 'identifier_DL',
                             'communication.language.coding_urn:ietf:bcp:47', 'patient_birthPlace.state',
                             'maritalStatus.coding_v3-MaritalStatus', 'address.geolocation_latitude', 'address.country',
                             'name.1.family', 'name.1.given', 'us_core_ethnicity_ombCategory', 'us_core_race_text',
                             'identifier_synthea', 'us_core_race_ombCategory',
                             'patient_mothersMaidenName', 'address.postalCode', 'name.1.prefix',
                             'disability_adjusted_life_years', 'resourceType', 'patient_birthPlace.city',
                             'address.city', 'address.geolocation_longitude', 'name.0.use', 'name.0.prefix',
                             'multipleBirthBoolean', 'name.0.given', 'telecom.system', 'telecom.value',
                             'us_core_ethnicity_text', 'maritalStatus.text', 'identifier_PPN', 'identifier_MR',
                             'communication.language.text', 'quality_adjusted_life_years'}

            assert actual_keys == expected_keys

            assert context.properties['us_core_race_ombCategory'].enum,  "Should have an enum set"

            # only first record
            break


def test_flattened_synthea_patient_emitter(config_path, input_synthea_patient_paths, output_path, pfb_path):
    """Borrows fixtures from synthea fhir resources."""
    model = initialize_model(config_path)

    for file in input_synthea_patient_paths:

        with pfb(output_path, pfb_path, model) as pfb_:
            for context in process_files(model, file, simplify=True):
                pfb_.emit(context)
                # only first record
                break

        assert os.path.isfile(pfb_path)
        results = inspect_pfb(pfb_path)
        assert len(results.errors) == 0, results.errors
        assert len(results.warnings) == 1 and results.warnings == ['No records have relationships.'], results.warnings

        cleanup_emitter(output_path, pfb_path)


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
