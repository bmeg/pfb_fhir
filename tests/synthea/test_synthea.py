"""Test synthetic data."""
import json
import os
from collections import defaultdict

from pfb_fhir import initialize_model  # , start_profiler, stop_profiler
from pfb_fhir.cli import process_files
from pfb_fhir.emitter import pfb, inspect_pfb
from tests import cleanup_emitter

import logging
logger = logging.getLogger(__name__)


def test_model(config_path):
    """Test Patient and document-reference."""
    model = initialize_model(config_path)
    resource_properties = defaultdict(set)

    for file in ['tests/fixtures/synthea/filtered/Patient.ndjson']:
        for context in process_files(model, file):
            assert context
            if not context.properties:
                continue
            for k in ['properties', 'resource', 'entity']:
                assert getattr(context, k, None), f"{k} was empty"
            properties = context.properties
            resource = context.resource
            assert resource.id and resource.resource_type
            assert properties['id']
            resource_properties[resource.resource_type].update(properties.keys())

    assert 'multipleBirthBoolean' in resource_properties['Patient']
    assert 'deceasedDateTime' in resource_properties['Patient']
    expected_suffixes = ['valueCoding', 'valueString', 'valueCode', 'valueDecimal']
    for suffix in expected_suffixes:
        found = False
        for p in resource_properties['Patient']:
            if suffix in p:
                found = True
                break
        if not found:
            assert found, f"{suffix} not found"


def test_emitter(config_path, input_paths, output_path, pfb_path):
    """Test Input Files vs emitted PFB ."""
    model = initialize_model(config_path)

    # start_profiler()
    with pfb(output_path, pfb_path, model) as pfb_:
        for context in process_files(model, input_paths):
            if not context.properties:
                continue
            pfb_.emit(context)
    # stop_profiler()
    assert os.path.isfile(pfb_path)
    results = inspect_pfb(pfb_path)
    assert len(results.errors) == 0, results.errors
    assert len(results.warnings) == 0, results.warnings

    with open(f"{output_path}/pfb/Patient.ndjson") as fp:
        patient = json.loads(fp.readline())
        properties = patient['object']
        assert properties['id']
        assert properties['submitter_id']
        assert properties['id'] != properties['submitter_id']
        logger.info(f"check custom submitter id:{properties['id']} submitter_id:{properties['submitter_id']}")

    cleanup_emitter(output_path, pfb_path)
