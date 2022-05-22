"""Test fixtures."""
import json

from _pytest.fixtures import fixture
from pathlib import Path
import os
import requests
from urllib.parse import urlparse, urlunparse


@fixture
def data_path():
    """Fixture where to read data."""
    return './tests/fixtures/kf/examples'


@fixture
def output_path():
    """Fixture where to write data."""
    return './tests/fixtures/kf/output'


@fixture
def pfb_path():
    """Fixture where to write data."""
    return './tests/fixtures/kf/output/kf.pfb.avro'


@fixture
def input_paths():
    """File paths."""
    file_names = """
    Organization.json
    Practitioner.json
    PractitionerRole.json
    Patient.json
    ResearchStudy.ndjson
    ResearchSubject.json
    Specimen.json
    DocumentReference.json
    Observation.json
    """.split()
    return [f"tests/fixtures/kf/examples/{file_name}" for file_name in file_names]


@fixture
def config_path():
    """Fixture where to read config."""
    return 'tests/fixtures/kf/config.yaml'


@fixture
def kids_first_cookie():
    """AWSELBAuthSessionCookie cookie captured from https://kf-api-fhir-service.kidsfirstdrc.org browser"""
    assert 'KIDS_FIRST_COOKIE' in os.environ
    assert os.environ['KIDS_FIRST_COOKIE'].startswith('AWSELBAuthSessionCookie')
    return os.environ['KIDS_FIRST_COOKIE']


@fixture
def kids_first_api_base():
    """Endpoint."""
    return 'https://kf-api-fhir-service.kidsfirstdrc.org'


@fixture
def kids_first_resource_urls():
    """Endpoint."""
    return 'https://kf-api-fhir-service.kidsfirstdrc.org'


@fixture
def kids_first_resource_urls():
    """List of tuples, each with url and file path."""
    return [
        ('https://kf-api-fhir-service.kidsfirstdrc.org/ResearchStudy/100031', 'ResearchStudy.ndjson'),
        ('https://kf-api-fhir-service.kidsfirstdrc.org/PractitionerRole/96500', 'PractitionerRole.ndjson'),
        ('https://kf-api-fhir-service.kidsfirstdrc.org/Practitioner/96498', 'Practitioner.ndjson'),
        ('https://kf-api-fhir-service.kidsfirstdrc.org/Organization/96499', 'Organization.ndjson'),
        ('https://kf-api-fhir-service.kidsfirstdrc.org/ResearchSubject?_tag=SD_DYPMEHHF&_count=1000',
         'ResearchSubject.ndjson'),
        ('https://kf-api-fhir-service.kidsfirstdrc.org/Patient?_tag=SD_DYPMEHHF&_count=1000', 'Patient.ndjson'),
        ('https://kf-api-fhir-service.kidsfirstdrc.org/Specimen?_tag=SD_DYPMEHHF&_count=1000', 'Specimen.ndjson'),
        ('https://kf-api-fhir-service.kidsfirstdrc.org/DocumentReference?_tag=SD_DYPMEHHF&_count=1000',
         'DocumentReference.ndjson'),
        ('https://kf-api-fhir-service.kidsfirstdrc.org/Observation?_tag=SD_DYPMEHHF&_count=1000', 'Observation.ndjson'),
    ]


@fixture
def kids_first_resources(data_path, kids_first_resource_urls, kids_first_cookie):
    """If file path does not exist, fetch data"""
    file_paths = []
    for kids_first_resource_url in kids_first_resource_urls:
        file_path = Path(data_path, kids_first_resource_url[1])
        file_paths.append(file_path)
        if file_path.is_file():
            continue
        print(kids_first_resource_url[0])
        response = requests.get(kids_first_resource_url[0], headers={'cookie': kids_first_cookie})
        kids_first_netloc = urlparse(kids_first_resource_url[0]).netloc
        response.raise_for_status()
        resource = response.json()
        with open(file_path, "w") as fp:
            if resource['resourceType'] == 'Bundle':
                while True:
                    for entry in resource['entry']:
                        json.dump(entry['resource'], fp)
                        fp.write("\n")
                    next_url = next(iter([link['url'] for link in resource['link'] if link['relation'] == 'next']),
                                    None)
                    if not next_url:
                        break
                    if 'localhost' in next_url:
                        url_parts = urlparse(next_url)
                        next_url = url_parts._replace(netloc=kids_first_netloc + '/', scheme='https').geturl()
                    print(next_url)
                    response = requests.get(next_url, headers={'cookie': kids_first_cookie})
                    response.raise_for_status()
                    resource = response.json()
            else:
                json.dump(resource, fp)
                fp.write("\n")

    return file_paths
