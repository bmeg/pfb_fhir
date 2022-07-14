"""Implements model, matches Entities to Profiles."""

import collections
import json
import logging
import os
from copy import deepcopy
from typing import Optional, Dict, Any, List, OrderedDict

import requests
import yaml
from fhirclient.models.resource import Resource
from flatten_json import flatten
from pydantic import BaseModel, PrivateAttr

logger = logging.getLogger(__name__)


class FHIRTypeAlias(BaseModel):
    """Aliases for FHIR primitives, helps normalization."""

    code: str
    """Code used in profiles."""
    json_type: str
    """Type used in json schema."""
    url: str
    """Actual url used to retrieve it."""


FHIR_TYPES: Dict[str, FHIRTypeAlias] = {
    'http://hl7.org/fhirpath/System.String': FHIRTypeAlias(json_type='string',
                                                           code='http://hl7.org/fhirpath/System.String',
                                                           url='http://build.fhir.org/string.profile.json'),
    'http://hl7.org/fhirpath/System.Integer': FHIRTypeAlias(json_type='integer',
                                                            code='http://hl7.org/fhirpath/System.Integer',
                                                            url='http://build.fhir.org/integer.profile.json'),
    'http://hl7.org/fhirpath/System.Decimal': FHIRTypeAlias(json_type='decimal',
                                                            code='http://hl7.org/fhirpath/System.Decimal',
                                                            url='http://build.fhir.org/decimal.profile.json'),
    'http://hl7.org/fhirpath/System.Boolean': FHIRTypeAlias(json_type='boolean',
                                                            code='http://hl7.org/fhirpath/System.Boolean',
                                                            url='http://build.fhir.org/boolean.profile.json'),
}


class FHIRProfileRetriever(object):
    """Fetch and cache FHIR profiles(schemas)."""

    def __init__(self) -> None:
        """Load schema."""
        self.primitives = []
        os.makedirs(os.environ.get("PFB_FHIR_CACHE_PATH", 'cache'),  exist_ok=True)

    def get_profile(self, profile_name, url=None):
        """Retrieve schema."""
        if profile_name in self.primitives:
            return None
        if profile_name == 'FHIRReference':
            profile_name = 'reference'
        if not url:
            url = f"https://www.hl7.org/fhir/{profile_name}.profile.json"
        if 'ncpi-fhir.github.io' in url:
            # logger.debug('patching ncpi host name')
            url = url.replace('ncpi-fhir.github.io', 'nih-ncpi.github.io')
        if 'StructureDefinition/ncpi' in url:
            # logger.debug('patch profile path')
            url = url.replace('StructureDefinition/ncpi', 'StructureDefinition-ncpi')
        if not url.endswith('json'):
            url = url + '.json'

        file_name = f'cache/{profile_name}.profile.json'
        if os.path.isfile(file_name):
            with open(file_name, 'r') as input_:
                logger.debug(f'found in cache {file_name}')
                return json.load(input_)

        logger.info(f"fetching profile_name {profile_name} {url}")
        response = requests.get(url)
        if response.status_code != 200:
            self.primitives.append(profile_name)
            logger.info(f"fetching {url} got {response.status_code}")
            return None

        profile = response.json()
        file_name = f"cache/{profile['name']}.profile.json"
        with open(file_name, 'w') as output:
            logger.debug(f'wrote to cache {file_name}')
            json.dump(profile, output)

        return profile

    def fetch_all(self, profile) -> collections.abc.Iterable:
        """Retrieve sub profiles for all elements in snapshot, yields sub-profiles."""
        if 'snapshot' not in profile or 'element' not in profile['snapshot']:
            logger.debug(f"No snapshot.element in {profile['id']}")
            return
        for element in profile['snapshot']['element']:
            if 'type' not in element:
                logger.debug(f"No type in {element['id']}")
                continue
            for type_ in element['type']:
                if type_['code'] in FHIR_TYPES:
                    yield self.get_profile(FHIR_TYPES[type_['code']].json_type, url=FHIR_TYPES[type_['code']].url)
                else:
                    yield self.get_profile(type_['code'])


# instantiate for module
fhir_profile_retriever = FHIRProfileRetriever()


class Element(BaseModel):
    """Entity root."""

    id: str


class Link(Element):
    """Edge between entities."""

    targetProfile: str
    """Constrain edge target."""
    required: Optional[bool] = True
    """Warn if missing."""


class Enum(Element):
    """Property enum."""

    source: str
    required: Optional[bool] = True


class Constant(Element):
    """Property constant."""

    value: str


class SubmitterIdAlias(BaseModel):
    """Property constant."""
    identifier_system: str


class Entity(Element):
    """A FHIR resource, or embedded profile."""

    category: str
    """Corresponds to Gen3's dictionary category, embedded resources are assigned 'sub-profile'."""
    links: Optional[Dict[str, Link]] = {}
    """Narrow the scope of links."""
    source: Optional[str]
    """Explicit url for the profile."""
    submitter_id: Optional[SubmitterIdAlias] = None
    """Alias for submitter_id."""


class AttributeEnum(BaseModel):
    """Information about an enumeration."""

    url: str
    """Value/Code set url."""

    restricted_to: List[str]
    """Enumerated values."""

    binding_strength: str
    """FHIR binding strength, how should this enumeration be validated?"""

    class_name: str
    """FHIR class name."""


class Property(BaseModel):
    """Resource.property and it's FHIR definition."""

    flattened_key: str
    """The key in a flattened representation."""
    docstring: Optional[str]
    """FHIR documentation for the element."""
    enum: Optional[AttributeEnum]
    """Information about the Value/Code set."""
    name: str
    """The FHIR attribute name (possibly renamed for python compatibility)."""
    jsname: str
    """The FHIR attribute name in JSON."""
    typ: str
    """The FHIR type."""
    is_list: bool
    """List of FHIR resources?"""
    of_many: Optional[str]
    """A value[x]?"""
    not_optional: bool
    """Required."""

    value: Any
    """The value."""


class Model(BaseModel):
    """Delegates to a collection of Entity."""

    entities: Optional[OrderedDict[str, Entity]] = collections.OrderedDict()
    dependency_order: Optional[List[str]] = []

    @staticmethod
    def parse_file(path: str) -> Any:
        """Use entity_name, the map key  as id."""
        with open(path) as fp:
            config = yaml.safe_load(fp)

        needs_adding = []
        for entity_name, entity in config['entities'].items():
            if 'id' not in entity:
                entity['id'] = entity_name
            if 'links' in entity:
                assert isinstance(entity['links'], dict), f"Error parsing file {path} unexpected link type for {entity_name} {entity['links']}"
                for link_name, link in entity['links'].items():
                    if 'id' not in link:
                        link['id'] = link_name
            if entity['id'] not in config['entities']:
                needs_adding.append(entity)
        # add entities that not are sub-typed
        for entity in needs_adding:
            config['entities'][entity['id']] = entity

        return Model.parse_obj(config)

    def fetch_profiles(self):
        """Ask entities to recursively fetch their FHIR profiles, add Entities to model."""
        sub_entities = []
        for entity in self.entities.values():
            for profile in entity.fetch_profile():
                if not profile:
                    continue
                sub_entities.append(Entity(id=profile['id'], profile=profile, category='sub-profile'))
        for entity in sub_entities:
            self.entities[entity.id] = entity


class Context(BaseModel):
    """Transient data for command(s)."""

    obj: dict = {}


class TransformerContext(Context):
    """Typed context."""
    class Config:
        arbitrary_types_allowed = True

    resource: Optional[Resource]
    """Source FHIR object."""

    properties: Optional[Dict[str, Property]] = {}
    """A list of transformed properties"""

    simplify: Optional[bool] = False
    """Flag, if set, remove FHIR scaffolding"""

    entity: Optional[Entity]
    """Model Entity associated with transformer."""

    def __init__(self, **data):
        """Runs transform after init."""
        super().__init__(**data)
        self.transform()

    def transform(self):
        """Creates properties."""
        if self.simplify:
            js, simplified_schema = self.resource.as_simplified_json()
            flattened = flatten(js, separator='|')

            for flattened_key, value in flattened.items():
                dict_ = simplified_schema
                for flattened_key_part in flattened_key.split('|'):
                    if flattened_key_part not in dict_ and flattened_key_part.isnumeric():
                        # traverse over list index
                        continue
                    if flattened_key_part in dict_:
                        dict_ = dict_[flattened_key_part]
                flattened_key = flattened_key.replace('|', '.')
                self.properties[flattened_key] = Property(**dict_, value=value, flattened_key=flattened_key)
        else:
            js = self.resource.as_json(strict=False)

            assert 'resourceType' in js, "Should have resourceType"
            js['resource_type'] = js['resourceType']

            flattened = flatten(js, separator='.')

            for flattened_key, value in flattened.items():
                resource_ = self.resource
                contained_list_ = None
                found = False
                for flattened_key_part in flattened_key.split('.'):
                    if flattened_key_part.isnumeric():
                        # traverse over list index
                        index = int(flattened_key_part)
                        if contained_list_ and len(contained_list_) > index and hasattr(contained_list_[index], 'attribute_docstrings'):
                            resource_ = contained_list_[int(flattened_key_part)]
                        continue
                    for name, jsname, typ, is_list, of_many, not_optional in resource_.elementProperties() + [
                            ("resource_type", "resource_type", str, False, None, False)]:
                        if flattened_key_part == name:
                            found = True

                            if isinstance(getattr(resource_, name), list):
                                test_list_ = getattr(resource_, name)
                                if len(test_list_) > 0 and hasattr(test_list_[0], 'attribute_docstrings'):
                                    contained_list_ = getattr(resource_, name)
                                    break

                            docstring = resource_.attribute_docstrings().get(name)

                            enum_ = None
                            if resource_.attribute_enums().get(name):
                                enum_ = resource_.attribute_enums().get(name)

                            # follow resource
                            if hasattr(getattr(resource_, name), 'attribute_docstrings'):
                                resource_ = getattr(resource_, name)

                            if flattened_key == 'resource_type':
                                flattened_key = 'resourceType'

                            # apply_enum = enum_
                            # if resource_.__class__.__name__ == 'CodeableConcept' and name != 'code':
                            #     apply_enum = None

                            self.properties[flattened_key] = Property(
                                    flattened_key=flattened_key,
                                    value=value,
                                    docstring=docstring,
                                    enum=enum_,
                                    name=name,
                                    jsname=jsname,
                                    typ=value.__class__.__name__,
                                    is_list=is_list,
                                    of_many=of_many,
                                    not_optional=not_optional
                                )

                            break

                if not found:
                    self.properties[flattened_key] = Property(
                        flattened_key=flattened_key,
                        value=value,
                        docstring='extension',
                        enum=None,
                        name='extension',
                        jsname='extension',
                        typ=value.__class__.__name__,
                        is_list=True,
                        of_many=None,
                        not_optional=False
                    )


class EdgeSummary(BaseModel):
    """Summary of edge in PFB."""

    src: str = None
    dst: str = None
    count: int = 0


class EntitySummary(BaseModel):
    """Summary of entity in PFB."""

    name: str = None
    count: int = 0
    relationships: Dict[str, EdgeSummary] = {}


class InspectionResults(BaseModel):
    """Results of PFB inspection."""

    errors: List[str] = []
    warnings: List[str] = []
    info: List[str] = []
    counts: Dict[str, EntitySummary] = {}
