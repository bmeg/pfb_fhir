from pprint import pprint

import requests


def test_family_member(value_sets):
    """We should have pedigree codes."""
    family_member = value_sets.resource('http://terminology.hl7.org/ValueSet/v3-FamilyMember')
    assert family_member
    codes = value_sets.codes('http://terminology.hl7.org/ValueSet/v3-FamilyMember')
    pprint(codes)
    assert len(codes) > 150


def test_body_site(value_sets):
    """We don't have snomed codes."""
    body_site_codes = value_sets.codes("http://hl7.org/fhir/ValueSet/body-site")
    assert not body_site_codes


def test_task_code(value_sets):
    """We have tasks codes."""
    actual_task_codes = set(value_sets.codes('http://hl7.org/fhir/ValueSet/task-code'))
    assert actual_task_codes
    expected_task_codes = set(['approve', 'fulfill', 'instantiate', 'abort', 'replace', 'change', 'suspend', 'resume'])
    pprint(actual_task_codes)
    assert expected_task_codes == actual_task_codes


def test_specimen_codes(value_sets):
    """We have tasks codes."""
    codes = value_sets.codes('http://terminology.hl7.org/ValueSet/v2-0487')
    pprint(codes)
    assert len(codes) > 0


def test_research_study_status_codes(value_sets):
    research_study_status_codes = value_sets.codes('http://hl7.org/fhir/ValueSet/research-study-status|4.0.1')
    pprint(research_study_status_codes)
    assert 'research-study-arm-type' not in research_study_status_codes


def test_contact_relationship_codes(value_sets):
    contact_relationship_codes = value_sets.codes('http://hl7.org/fhir/ValueSet/patient-contactrelationship')
    assert contact_relationship_codes
    pprint(contact_relationship_codes)


def test_marital_status(value_sets):
    marital_status_codes = value_sets.codes('http://hl7.org/fhir/ValueSet/marital-status')
    assert marital_status_codes
    pprint(marital_status_codes)
    marital_status = value_sets.resource('http://hl7.org/fhir/ValueSet/marital-status')
    assert marital_status
    pprint(marital_status)

    marital_status_code_system = value_sets.resource('https://terminology.hl7.org/3.1.0/CodeSystem-v3-MaritalStatus')
    # assert marital_status_code_system
    # pprint(marital_status_code_system)

    response = requests.get("http://terminology.hl7.org/CodeSystem/v3-MaritalStatus", headers={"Content-Type": "application/json"})
    print("?")


def test_extras(value_sets):
    """We have task & specimen codes."""
    # # sourced from base
    # task_codes = value_sets.codes('http://hl7.org/fhir/ValueSet/task-code')
    # # sourced from extras
    # specimen = value_sets.codes('http://terminology.hl7.org/ValueSet/v2-0487')
    # assert len(task_codes) == 8
    # assert len(specimen) == 315

    task_intent = value_sets.resource('http://hl7.org/fhir/ValueSet/task-intent')
    pprint(task_intent)

    task_intent_codes = value_sets.codes('http://hl7.org/fhir/ValueSet/task-intent')
    pprint(task_intent_codes)

