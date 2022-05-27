import os
from collections import defaultdict
from copy import copy, deepcopy
from typing import Dict

from pfb_fhir import initialize_model
from pfb_fhir.cli import process_files
from pfb_fhir.emitter import pfb, inspect_pfb
from pfb_fhir.model import Property

import logging

from pfb_fhir.simplifier import ContextSimplifier
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
            expected_keys = {'resourceType', 'id', 'text.status', 'text.div', 'name.use', 'name.text', 'name.family', 'name.given.0',
             'name.given.1', 'telecom.system', 'telecom.value', 'telecom.use', 'telecom.rank', 'gender', 'address.use',
             'address.type', 'address.text', 'address.line', 'address.city', 'address.state', 'address.postalCode',
             'contact.relationship.text', 'contact.name.use', 'contact.name.text', 'contact.name.family',
             'contact.name.given.0', 'contact.name.given.1', 'contact.telecom.system', 'contact.telecom.value',
             'contact.telecom.use', 'contact.telecom.rank', 'contact.address.use', 'contact.address.type',
             'contact.address.text', 'contact.address.line', 'contact.address.city', 'contact.address.state',
             'contact.address.postalCode', 'contact.gender', 'contact.relationship.v2-0131',
             'contact.relationship.v2-0131.display', 'us-core-race.ombCategory', 'us-core-race.detailed',
             'us-core-race.text', 'us-core-ethnicity.ombCategory', 'us-core-ethnicity.text'}
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
            _to_tsv(context.properties)
            simplified_properties = ContextSimplifier._group_by_root(context)
            assert len(simplified_properties['Patient.extension']) == 26
            assert len(simplified_properties['Patient.address']) == 10
            simplified_properties = ContextSimplifier._extensions(simplified_properties)
            assert len(simplified_properties['Patient.extension']) == 4, "Should simplify root extensions"
            logger.warning("TODO - expected error.  Improve ContextSimplifier.")
            assert len(simplified_properties['Patient.address']) < 10, f"Should simplify property extensions {[p.flattened_key for p in simplified_properties['Patient.address'] if 'extension' in p.flattened_key]}"
            simplified_properties = ContextSimplifier._single_item_lists(simplified_properties)
            simplified_properties = ContextSimplifier._codings(simplified_properties)

            # only first record
            break
        #
        # for context in process_files(model, file, simplify=True):
        #     assert context
        #     assert isinstance(context.properties, dict)
        #     actual_keys = set([k for k in context.properties])
        #     expected_keys = {'TODO'}
        #     assert expected_keys == actual_keys
        #     _to_tsv(context.properties)
        #     print(len(context.properties))
        #     # only first record
        #     break


def test_flattened_ncpi_patient_emitter(config_path, input_ncpi_patient_paths, output_path, pfb_path):
    """Borrows fixtures from ncpi fhir resources."""
    model = initialize_model(config_path)

    with pfb(output_path, pfb_path, model) as pfb_:
        for context in process_files(model, input_ncpi_patient_paths):
            pfb_.emit(context)

    assert os.path.isfile(pfb_path)
    results = inspect_pfb(pfb_path)
    assert len(results.errors) == 0, results.errors
    assert len(results.warnings) == 1 and results.warnings == ['No records have relationships.'], results.warnings

    cleanup_emitter(output_path, pfb_path)