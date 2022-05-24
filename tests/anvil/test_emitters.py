"""Tests emitters."""
import glob
import json
import os.path

import yaml

from pfb_fhir import initialize_model
from pfb_fhir.cli import process_files
from pfb_fhir.emitter import pfb
import logging

from tests import cleanup_emitter

logger = logging.getLogger(__name__)


def test_research_study(config_path, data_path, output_path):
    """Validate emitter output."""
    model = initialize_model(config_path)
    my_pfb = f"{output_path}/my.pfb.avro"

    with pfb(output_path, my_pfb, model) as pfb_:
        for context in process_files(model, f"{data_path}/public/ResearchStudy.ndjson"):
            pfb_.emit(context)
            assert os.path.isdir(output_path), f"{output_path} must exist"
            for emitter in pfb_.emitters:
                assert os.path.isdir(emitter.work_dir), f"{type(emitter)} {emitter.work_dir} must exist"
                assert len(glob.glob(f"{emitter.work_dir}/ResearchStudy.*")) > 0, f"{type(emitter)} {emitter.work_dir}/ResearchStudy.* must exist"

    cleanup_emitter(output_path, my_pfb)


def test_public_resources(config_path, data_path, output_path):
    """Process all files in public dir."""
    model = initialize_model(config_path)
    my_pfb = f"{output_path}/my.pfb.avro"
    schema_work_dir = f"{output_path}/gen3"

    with pfb(output_path, my_pfb, model) as pfb_:
        for context in process_files(model, f"{data_path}/public/*.ndjson"):
            pfb_.emit(context)
    for path in glob.glob(f"{schema_work_dir}/*.yaml"):
        if _is_gen3_fixture(path):
            continue
        _assert_valid_schema(path)

    assert os.path.isfile(my_pfb), f"{my_pfb} must exist"
    cleanup_emitter(output_path, my_pfb)


def test_protected_resources(config_path, data_path, output_path):
    """Process all files in public dir."""
    model = initialize_model(config_path)
    my_pfb = f"{output_path}/my.pfb.avro"
    schema_work_dir = f"{output_path}/gen3"

    with pfb(output_path, my_pfb, model) as pfb_:
        for context in process_files(model, f"{data_path}/protected/*.ndjson"):
            pfb_.emit(context)
    for path in glob.glob(f"{schema_work_dir}/*.yaml"):
        if _is_gen3_fixture(path):
            continue
        _assert_valid_schema(path)

    assert os.path.isfile(my_pfb), f"{my_pfb} must exist"
    cleanup_emitter(output_path, my_pfb)


def test_research_study_observation(config_path, data_path, output_path):
    """Validate emitter output."""
    model = initialize_model(config_path)
    my_pfb = f"{output_path}/my.pfb.avro"
    schema_work_dir = f"{output_path}/gen3"

    with pfb(output_path, my_pfb, model) as pfb_:
        for context in process_files(model, f"{data_path}/public/ResearchStudyObservationSummary.ndjson"):
            pfb_.emit(context)
            assert os.path.isdir(output_path), f"{output_path} must exist"
            for emitter in pfb_.emitters:
                assert os.path.isdir(emitter.work_dir), f"{type(emitter)} {emitter.work_dir} must exist"
                assert len(glob.glob(f"{emitter.work_dir}/*.*")) > 0, f"{type(emitter)} {emitter.work_dir}/*.* must exist"

    for path in glob.glob(f"{schema_work_dir}/*.yaml"):
        if _is_gen3_fixture(path):
            continue
        _assert_valid_schema(path)

    assert os.path.isfile(my_pfb), f"{my_pfb} must exist"
    cleanup_emitter(output_path, my_pfb)


def _assert_aggregated_schema(expected_keys, aggregated_schema_path):
    """Check the schema for entity keys and property names."""
    assert os.path.isfile(aggregated_schema_path), f"{aggregated_schema_path} must exist"
    schema = json.load(open(aggregated_schema_path))
    for k in expected_keys:
        assert k in schema.keys()
        assert schema[k], f"{k} Should not be null"
    for entity in schema:
        for properties in schema[entity]:
            for name in properties:
                assert '.' not in name


def _assert_valid_schema(path):
    """Check a valid schema for entity."""
    schema = yaml.safe_load(open(path))
    assert schema['id'] != 'TODO'
    assert schema['title'] != 'TODO'
    assert schema['category'] != 'TODO'
    assert schema['description'] != 'TODO'
    assert schema['links'] is not None and isinstance(schema['links'], list)
    assert schema['required'] is not None and isinstance(schema['required'], list)
    assert 'TODO' not in [property_name for property_name in schema['required']]
    for k in ['submitter_id', 'type']:
        assert k in schema['required']

    assert len(schema['required']) > 0, f"{path} has no required"

    if len(schema['links']) == 0:
        logger.warning(f"{path} has no links")

    minimum_properties = set(
        ['type', 'id', 'state', 'submitter_id', 'project_id', 'created_datetime', 'updated_datetime'])
    actual_properties = set(schema['properties'].keys())

    # assert actual_properties > minimum_properties
    if len(actual_properties) < len(minimum_properties):
        logger.warning(f"{path} only has minimum properties")

    return True


def _is_gen3_fixture(path_):
    """Gen3 boilerplate."""
    gen3_fixtures = ['_definitions.yaml', '_settings.yaml', '_terms.yaml']
    for gen3_fixture in gen3_fixtures:
        if gen3_fixture in path_:
            return True
    return False
