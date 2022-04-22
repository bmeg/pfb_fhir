"""Tests dbgap."""
import os
from collections import defaultdict

from pfb_fhir import initialize_model
from pfb_fhir.cli import process_files
from pfb_fhir.emitter import pfb, inspect_pfb
from tests import cleanup_emitter


def test_model(config_path, input_paths, expected_results):
    """Test Input Files vs expected keys."""
    model = initialize_model(config_path)
    resource_properties = defaultdict(set)

    for file in input_paths:
        for context in process_files(model, file):
            assert context
            for k in ['model', 'properties', 'resource', 'entity']:
                assert getattr(context, k), f"{k} was empty"
            properties = context.properties
            resource = context.resource
            assert resource['id'] and resource['resourceType']
            assert properties['id']
            resource_properties[resource['resourceType']].update(properties.keys())

    for key in expected_results:
        assert expected_results[key] == resource_properties[key]


def test_emitter(config_path, input_paths, output_path, pfb_path):
    """Test Input Files vs emitted PFB ."""
    model = initialize_model(config_path)

    with pfb(output_path, pfb_path, model) as pfb_:
        for context in process_files(model, input_paths):
            pfb_.emit(context)

    assert os.path.isfile(pfb_path)
    results = inspect_pfb(pfb_path)
    assert len(results.errors) == 0, results.errors
    assert len(results.warnings) == 0, results.warnings

    cleanup_emitter(output_path, pfb_path)
