from _pytest.fixtures import fixture

from pfb_fhir.terminology.value_sets import ValueSets

@fixture
def value_sets():
    return ValueSets()
