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

    targetProfile: List[str]
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
    is_extension: Optional[bool] = False
    """is this property derived from an extension"""
    extension_url: Optional[str] = None
    """The base url of the extension."""
    extension_child_url: Optional[str] = None
    """The url of the child aka sub_extension."""

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
        # use name as id
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
        # make all targetProfile lists
        for entity_name, entity in config['entities'].items():
            if 'links' in entity:
                for link_name, link in entity['links'].items():
                    if isinstance(link['targetProfile'], str):
                        link['targetProfile'] = [link['targetProfile']]
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


class ExtensionValue(BaseModel):
    url: str
    value: object


def extension_value(ext) -> List[ExtensionValue]:
    """Returns value in extension for single, and multi values."""
    # single
    for property_, value_ in ext.__dict__.items():
        if property_.startswith('value') and value_:
            return [ExtensionValue(url=ext.url, value=value_)]
    values = []
    if ext.extension:
        for sub_extension in ext.extension:
            for property_, value_ in sub_extension.__dict__.items():
                if property_.startswith('value') and value_:
                    values.append(ExtensionValue(url=sub_extension.url, value=value_))
    return values


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

    _value_sets: object = PrivateAttr()

    # extensions: Optional[Extensions]
    # """Extensions helper."""

    def __init__(self, **data):
        """Runs transform after init."""
        # defer import
        from pfb_fhir.terminology.value_sets import ValueSets
        super().__init__(**data)
        self._value_sets = ValueSets()
        self.transform()

    def transform(self):
        """Creates properties."""

        # deferred import, avoids circular references
        from pfb_fhir.extensions.extensions import Extensions
        extension_lookup = Extensions()

        # # handle extensions separately
        # # what about extensions in child classes and lists?
        # resource_extensions = self.resource.extension
        # self.resource.extension = None

        if self.simplify:
            # simplified json
            js, simplified_schema = self.resource.as_simplified_json()
            flattened = flatten(js, separator='|')

            for flattened_key, value in flattened.items():
                element_schema = simplified_schema
                for flattened_key_part in flattened_key.split('|'):
                    if flattened_key_part not in element_schema and flattened_key_part.isnumeric():
                        # traverse over list index
                        continue
                    # traverse down the element to get child schemas
                    if flattened_key_part in element_schema:
                        element_schema = element_schema[flattened_key_part]
                flattened_key = flattened_key.replace('|', '.')

                extension_docstring = self.lookup_extension_docstring(element_schema, extension_lookup, flattened_key)
                if extension_docstring:
                    element_schema['docstring'] = extension_docstring

                extension_enum = self.lookup_extension_enum(element_schema, extension_lookup, flattened_key)
                if extension_enum:
                    element_schema['enum'] = extension_enum

                self.properties[flattened_key] = Property(**element_schema, value=value, flattened_key=flattened_key)
        else:
            # as-is, flattened json
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
                    for name, jsname, typ, is_list, of_many, not_optional in resource_.elementProperties() + [("resource_type", "resource_type", str, False, None, False)]:

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

        # # handle extensions the same way for both simplified and as-is
        # if resource_extensions:
        #     logger.debug(f"> extensions {[ext.url for ext in resource_extensions]}")
        #     for resource_extension in resource_extensions:
        #         resource_extension_values = extension_value(resource_extension)
        #         if len(resource_extension_values) == 0:
        #             logger.warning(("no value in extension", resource_extension.url))
        #             continue
        #         extension_definition = extension_lookup.resource(resource_extension.url)
        #         if not extension_definition:
        #             logger.warning(("could not find definition for extension", resource_extension.url))
        #             for resource_extension_value in resource_extension_values:
        #                 flattened_key = resource_extension.url.split('/')[-1].replace('-', '_')
        #                 resource_extension_value_url = resource_extension_value.url.split('/')[-1].replace('-', '_')
        #                 if flattened_key != resource_extension_value_url:
        #                     flattened_key = f"{flattened_key}_{resource_extension_value_url}"
        #                 self.properties[flattened_key] = Property(
        #                     flattened_key=flattened_key,
        #                     value=resource_extension_value.value,
        #                     docstring=f"No documentation for extension. {resource_extension.url} {flattened_key}",
        #                     enum=None,
        #                     name=flattened_key,
        #                     jsname=flattened_key,
        #                     typ=resource_extension_value.value.__class__.__name__,
        #                     is_list=False,
        #                     of_many=False,
        #                     not_optional=False
        #                 )
        #             continue
        #         if extension_definition:
        #             extension_elements = [ee for ee in extension_definition.elements()]
        #             if len(extension_elements) > 0:
        #                 # multi valued
        #                 logger.debug((' > multi', resource_extension_values, resource_extension.url,
        #                              [(ee.slice.sliceName, ee.type.type[0].code) for ee in extension_elements]))
        #                 for extension_element in extension_elements:
        #                     resource_extension_value = next(iter(rev for rev in resource_extension_values if
        #                                                          rev.url == extension_element.slice.sliceName), None)
        #                     if not resource_extension_value:
        #                         logger.warning(("missing extension definition", resource_extension.url,
        #                                        extension_element.slice.sliceName))
        #                         continue
        #                     flattened_key = resource_extension.url.split('/')[-1].replace('-', '_')
        #                     resource_extension_value_url = extension_element.slice.sliceName.split('/')[-1].replace('-', '_')
        #                     if flattened_key != resource_extension_value_url:
        #                         flattened_key = f"{flattened_key}_{resource_extension_value_url}"
        #                     self.properties[flattened_key] = Property(
        #                         flattened_key=flattened_key,
        #                         value=resource_extension_value.value,
        #                         docstring=f"extension:{extension_definition.description}\nproperty:{extension_element.slice.definition}",
        #                         enum=None,  # TODO
        #                         name=flattened_key,
        #                         jsname=flattened_key,
        #                         typ=resource_extension_value.value.__class__.__name__,
        #                         is_list=False,
        #                         of_many=False,
        #                         not_optional=False
        #                     )
        #             else:
        #                 # single valued
        #                 logger.debug((' > single', resource_extension_value, resource_extension.url,
        #                              [(extension_definition.id, extension_definition.extension_type().type[0].code)]))
        #                 resource_extension_value = resource_extension_values[0]
        #                 flattened_key = resource_extension.url.split('/')[-1].replace('-', '_')
        #                 resource_extension_value_url = resource_extension_value.url.split('/')[-1].replace('-', '_')
        #                 if flattened_key != resource_extension_value_url:
        #                     flattened_key = f"{flattened_key}_{resource_extension_value_url}"
        #                 self.properties[flattened_key] = Property(
        #                     flattened_key=flattened_key,
        #                     value=resource_extension_value.value,
        #                     docstring=f"extension:{extension_definition.description}",
        #                     enum=None,
        #                     name=flattened_key,
        #                     jsname=flattened_key,
        #                     typ=resource_extension_value.value.__class__.__name__,
        #                     is_list=False,
        #                     of_many=False,
        #                     not_optional=False
        #                 )
        #

    def lookup_extension_docstring(self, element_schema, extension_lookup, flattened_key):
        if element_schema.get('is_extension', False) and element_schema['docstring'] is None:
            # lookup documentation of extension
            if not element_schema['extension_url']:
                logger.warning(
                    ("No extension_url", self.resource.resource_type, self.resource.id, flattened_key))
            else:
                extension_definition = extension_lookup.resource(element_schema['extension_url'])
                if not extension_definition:
                    logger.warning(
                        ("No extension_definition", self.resource.resource_type, self.resource.id,
                         flattened_key, element_schema['extension_url']))
                else:
                    extension_docstring = extension_definition.description
                    if element_schema['extension_child_url']:
                        extension_child = next(iter([ec for ec in extension_definition.snapshot.element if
                                                     ec.sliceName == element_schema['extension_child_url']]), None)
                        if not extension_child:
                            logger.warning(
                                ("No extension_child", self.resource.resource_type, self.resource.id,
                                 flattened_key, element_schema['extension_url'],
                                 element_schema['extension_child_url']))
                        else:
                            extension_docstring += f"\n{extension_child.definition}"
                    return extension_docstring
        return None

    def lookup_extension_enum(self, element_schema, extension_lookup, flattened_key):
        if element_schema.get('is_extension', False) and element_schema['enum'] is None and element_schema['typ'] == 'Coding':
            # lookup documentation of extension
            if not element_schema['extension_url']:
                logger.warning(
                    ("No extension_url", self.resource.resource_type, self.resource.id, flattened_key))
            else:
                extension_definition = extension_lookup.resource(element_schema['extension_url'])
                if not extension_definition:
                    logger.warning(
                        ("No extension_definition", self.resource.resource_type, self.resource.id,
                         flattened_key, element_schema['extension_url']))
                else:
                    flattened_key_part = flattened_key.split('_')[-1]
                    value_definition = next(iter([e for e in extension_definition.snapshot.element if f"{flattened_key_part}.value[" in e.id]), None)
                    binding = value_definition.binding
                    if not binding:
                        logger.warning(
                            ("No value_definition.binding", self.resource.resource_type, self.resource.id,
                             flattened_key, element_schema['extension_url'], flattened_key_part))
                    else:
                        value_set = self._value_sets.resource(binding.valueSet)
                        restricted_to = []
                        if value_set:
                            if 'expansion' in value_set and 'contains' in value_set['expansion']:
                                for concept in value_set['expansion']['contains']:
                                    restricted_to.append(concept['code'])
                            for concept in value_set['concept']:
                                restricted_to.append(concept['code'])
                        return {
                            'url': binding.valueSet,
                            'restricted_to': restricted_to,
                            'binding_strength': binding.strength,
                            'class_name': 'str'
                        }
        return None


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
