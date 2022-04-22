"""Simplify flattened json to be more data frame friendly."""

from _pytest.fixtures import fixture
import json
import logging

from tests.data_frame import PropertySimplifier, ResourceSimplifier

logger = logging.getLogger(__name__)


@fixture
def patient():
    """Test patient."""
    return json.loads(
        '''
            {"resourceType":"Patient","id":"2878a2e6-80cc-96c0-0596-00c411d5afd7","meta":{"profile":["http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"]}, "text":{"status":"generated","div":"Foo"} ,"extension":[{"url":"http://hl7.org/fhir/us/core/StructureDefinition/us-core-race","extension":[{"url":"ombCategory","valueCoding":{"system":"urn:oid:2.16.840.1.113883.6.238","code":"2106-3","display":"White"}},{"url":"text","valueString":"White"}]},{"url":"http://hl7.org/fhir/us/core/StructureDefinition/us-core-ethnicity","extension":[{"url":"ombCategory","valueCoding":{"system":"urn:oid:2.16.840.1.113883.6.238","code":"2186-5","display":"Not Hispanic or Latino"}},{"url":"text","valueString":"Not Hispanic or Latino"}]},{"url":"http://hl7.org/fhir/StructureDefinition/patient-mothersMaidenName","valueString":"Vernita491 Johns824"},{"url":"http://hl7.org/fhir/us/core/StructureDefinition/us-core-birthsex","valueCode":"F"},{"url":"http://hl7.org/fhir/StructureDefinition/patient-birthPlace","valueAddress":{"city":"Beverly","state":"Massachusetts","country":"US"}},{"url":"http://synthetichealth.github.io/synthea/disability-adjusted-life-years","valueDecimal":0.7390654047820436},{"url":"http://synthetichealth.github.io/synthea/quality-adjusted-life-years","valueDecimal":17.260934595217957}],"identifier":[{"system":"https://github.com/synthetichealth/synthea","value":"2878a2e6-80cc-96c0-0596-00c411d5afd7"},{"type":{"coding":[{"system":"http://terminology.hl7.org/CodeSystem/v2-0203","code":"MR","display":"Medical Record Number"}],"text":"Medical Record Number"},"system":"http://hospital.smarthealthit.org","value":"2878a2e6-80cc-96c0-0596-00c411d5afd7"},{"type":{"coding":[{"system":"http://terminology.hl7.org/CodeSystem/v2-0203","code":"SS","display":"Social Security Number"}],"text":"Social Security Number"},"system":"http://hl7.org/fhir/sid/us-ssn","value":"999-66-8413"},{"type":{"coding":[{"system":"http://terminology.hl7.org/CodeSystem/v2-0203","code":"DL","display":"Driver's License"}],"text":"Driver's License"},"system":"urn:oid:2.16.840.1.113883.4.3.25","value":"S99936922"}],"name":[{"use":"official","family":"Hills818","given":["Na515"],"prefix":["Ms."]}],"telecom":[{"system":"phone","value":"555-458-3651","use":"home"}],"gender":"female","birthDate":"2003-08-28","address":[{"extension":[{"url":"http://hl7.org/fhir/StructureDefinition/geolocation","extension":[{"url":"latitude","valueDecimal":42.19412841033493},{"url":"longitude","valueDecimal":-71.55550846382376}]}],"line":["123 Considine Corner Unit 51"],"city":"Hopkinton","state":"MA","country":"US"}],"maritalStatus":{"coding":[{"system":"http://terminology.hl7.org/CodeSystem/v3-MaritalStatus","code":"S","display":"Never Married"}],"text":"Never Married"},"multipleBirthBoolean":false,"communication":[{"language":{"coding":[{"system":"urn:ietf:bcp:47","code":"en-US","display":"English"}],"text":"English"}}]}
        '''
    )


def test_address(patient):
    """Derive friendly names."""
    property_ = PropertySimplifier(name='address', value=patient['address'])
    assert not isinstance(property_.value, list)
    assert 'latitude' in property_.value
    assert 'longitude' in property_.value
    assert 'extension' not in property_.value
    assert 'line' in property_.value and (not isinstance(property_.value['line'], list)), "Should simplify single item lists to scalar"


def test_communication(patient):
    """Simplify coding."""
    property_ = PropertySimplifier(name='communication', value=patient['communication'])
    assert not isinstance(property_.value, list)
    assert property_.value == {'language': 'en-US'}


def test_extension(patient):
    """Simplify extension."""
    property_ = PropertySimplifier(name='extension', value=patient['extension'])
    assert isinstance(property_.value, dict)
    assert set(property_.value.keys()) == {'patient-mothersMaidenName', 'patient-birthPlace', 'quality-adjusted-life-years', 'disability-adjusted-life-years', 'ombCategory', 'us-core-birthsex'}


def test_marital_status(patient):
    """Simplify coding."""
    property_ = PropertySimplifier(name='maritalStatus', value=patient['maritalStatus'])
    assert property_.value == 'S'


def test_identifier(patient):
    """Simplify identifiers."""
    property_ = PropertySimplifier(name='identifier', value=patient['identifier'])
    assert isinstance(property_.value, dict)
    assert set(property_.value.keys()) == {'DL', 'synthea', 'MR', 'SS'}


def test_patient(patient):
    """Derive friendly names."""
    simple_patient = ResourceSimplifier.simplify(patient)

    assert set(simple_patient.keys()) == {'identifier', 'communication', 'address', 'gender', 'id', 'text', 'patient-birthPlace', 'resourceType', 'maritalStatus', 'us-core-birthsex', 'patient-mothersMaidenName', 'birthDate', 'name', 'multipleBirthBoolean', 'disability-adjusted-life-years', 'meta', 'ombCategory', 'quality-adjusted-life-years', 'telecom'}

    from flatten_json import flatten
    print()
    print(flatten(patient, '_').keys())
    print()
    print(flatten(simple_patient, '_').keys())

    def to_tsv(obj):
        print()
        print("\t".join(list(flatten(obj, '_').keys())))
        print("\t".join([str(v) for v in flatten(obj, '_').values()]))

    to_tsv(patient)
    to_tsv(simple_patient)


