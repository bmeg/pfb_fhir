import os

from pfb_fhir import initialize_model
from pfb_fhir.cli import process_files
from pfb_fhir.emitter import inspect_pfb, pfb
from tests import cleanup_emitter



def test_fixture(kids_first_resources):
    for file_path in kids_first_resources:
        assert file_path.is_file()



def test_emitter(config_path, kids_first_resources, output_path, pfb_path):
    """Test Input Files vs emitted PFB ."""
    model = initialize_model(config_path)

    with pfb(output_path, pfb_path, model) as pfb_:
        for context in process_files(model, kids_first_resources):
            pfb_.emit(context)

    assert os.path.isfile(pfb_path)
    results = inspect_pfb(pfb_path)
    assert len(results.errors) == 0, results.errors
    assert len(results.warnings) == 0, results.warnings

    cleanup_emitter(output_path, pfb_path)