"""Test model setup and processing."""

import logging
from collections import defaultdict
from typing import List

from pfb_fhir import initialize_model
from pfb_fhir.cli import process_files
from pfb_fhir.model import fhir_profile_retriever

logger = logging.getLogger(__name__)


def test_model_setup(config_path):
    """Test all expected entities."""
    model = initialize_model(config_path)
    assert ",".join(sorted(entity.id for entity in
                           model.entities.values())) == 'DocumentReference,FamilyRelationship,Observation,Organization,Patient,Practitioner,PractitionerRole,Questionnaire,QuestionnaireResponse,ResearchStudy,ResearchSubject,Specimen,Task'
    assert fhir_profile_retriever.primitives == [], "All profiles were not found."


def _property_definition(property_):
    """Create definition from parent and property definition."""
    if property_.parent_definition['short'] != property_.definition['short']:
        return f"{property_.parent_definition['short']}. {property_.definition['short']}"
    return property_.definition['short']


def test_model_research_study(config_path, data_path, ):
    """Test all expected properties."""
    model = initialize_model(config_path)
    context = next(iter(process_files(model, f"{data_path}/public/ResearchStudy.ndjson")), None)
    assert context
    properties = context.properties
    assert 'id' in properties
    for i in range(2):
        assert f'identifier.{i}.system' in properties, properties.keys()
        assert f'identifier.{i}.value' in properties
    assert 'sponsor.reference' in properties
    assert 'status' in properties


def test_model_public(config_path, data_path, observation_expected_properties, organization_expected_properties,
                      practitioner_role_expected_properties, research_study_expected_properties):
    """Check consistent flattened properties for each resource type."""
    model = initialize_model(config_path)
    resource_properties = defaultdict(set)
    for context in process_files(model, f"{data_path}/public/*.ndjson"):
        assert context
        for k in ['properties', 'resource', 'entity']:
            assert getattr(context, k), f"{k} was empty"

        properties = context.properties
        resource = context.resource

        assert resource.id and resource.resource_type
        assert properties['id']
        resource_properties[resource.resource_type].update(properties.keys())
    # check consistent properties for each resource type.
    assert set(resource_properties.keys()) == {'Observation', 'Organization', 'Practitioner', 'PractitionerRole',
                                               'ResearchStudy'}
    assert set(resource_properties['Practitioner']) == {'resourceType', 'id'}

    assert set(resource_properties['Observation']) == observation_expected_properties
    assert set(resource_properties['Organization']) == organization_expected_properties
    assert set(resource_properties['PractitionerRole']) == practitioner_role_expected_properties
    assert set(resource_properties['ResearchStudy']) == research_study_expected_properties


def test_model_research_study_observation(config_path, data_path, observation_expected_properties):
    """Test all expected properties."""
    model = initialize_model(config_path)
    resource_properties = defaultdict(set)
    properties = None
    for context in process_files(model, f"{data_path}/public/ResearchStudyObservationSummary.ndjson"):
        assert context
        for k in ['properties', 'resource', 'entity']:
            assert getattr(context, k), f"{k} was empty"
        properties = context.properties
        resource = context.resource
        assert resource.id and resource.resource_type
        assert properties['id']
        resource_properties[resource.resource_type].update(properties.keys())

    assert set(resource_properties['Observation']) == observation_expected_properties


def test_model_document_reference(config_path, data_path, document_reference_expected_properties):
    """Test all expected properties."""
    model = initialize_model(config_path)
    resource_properties = defaultdict(set)
    properties = None
    for context in process_files(model, f"{data_path}/protected/DocumentReference.ndjson"):
        assert context
        for k in ['properties', 'resource', 'entity']:
            assert getattr(context, k), f"{k} was empty"
        properties = context.properties
        resource = context.resource
        assert resource.id and resource.resource_type
        assert properties['id']
        resource_properties[resource.resource_type].update(properties.keys())

    assert set(resource_properties['DocumentReference']) == document_reference_expected_properties


def description(property_) -> List[str]:
    """Concatenates descriptions (utility)."""
    descriptions = [property_.root_element['short']]
    for leaf_element in property_.leaf_elements:
        if leaf_element['short'] not in descriptions:
            descriptions.append(leaf_element['short'])
    return descriptions
