"""Implements model, matches Entities to Profiles."""

import json
import os
from copy import deepcopy
from typing import Optional, Dict, Any, List, OrderedDict
import collections

import requests
from pydantic import BaseModel, PrivateAttr
import logging

from pfb_fhir.observable import Command, ObservableData, Context

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


class Entity(Element, Command):
    """A FHIR resource, or embedded profile."""

    category: str
    """Corresponds to Gen3's dictionary category, embedded resources are assigned 'sub-profile'."""
    links: Optional[Dict[str, Link]] = {}
    """Narrow the scope of links."""
    source: Optional[str]
    """Explicit url for the profile."""
    _profile: dict = PrivateAttr()
    """Actual profile."""
    _handler: Any = PrivateAttr()
    """Method that processes this entity. TODO - should be callable?"""
    # TODO should be callable?
    _element_lookup: Dict[str, dict] = PrivateAttr()

    def __init__(self, **data):
        """Retrieve the fhir schema for this entity, make schema searchable."""
        super().__init__(**data)
        self._profile = fhir_profile_retriever.get_profile(self.id, self.source)
        self._ensure_element_lookup()

    @property
    def profile(self):
        """Getter."""
        return self._profile

    @property
    def handler(self):
        """Getter."""
        return self._handler

    @property
    def element_lookup(self):
        """Getter."""
        return self._element_lookup

    # doesn't work see https://github.com/samuelcolvin/pydantic/issues/1577#issuecomment-790506164
    # @property.setter
    # def handler(self, handler):
    #     self._handler = handler
    # TODO - for now, java style setter
    def set_handler(self, handler):
        """Setter."""
        self._handler = handler

    def notify(self, observable: ObservableData, context: Context = None, *args, **kwargs) -> None:
        """Delegate to handler."""
        self._handler(entity=self, observable=observable, context=context, *args, **kwargs)

    def interested(self, observable: ObservableData) -> bool:
        """Return True if data matches our profile."""
        if isinstance(observable.payload, dict):
            return self.id == observable.payload.get('resourceType', None)

        if isinstance(observable.payload, Property):
            starting_element = observable.payload.root_element
            if len(observable.payload.leaf_elements) > 0:
                starting_element = observable.payload.leaf_elements[-1]
            for observable_type in starting_element['type']:
                if not isinstance(observable_type, dict):
                    Exception('?')
                if observable_type.get('code', None) == self.id:
                    return True
                if observable_type.get('code', None) in FHIR_TYPES:
                    json_type = FHIR_TYPES[observable_type['code']].json_type
                    return json_type == self.id

        else:
            assert False, (observable.payload.__class__.__name__, observable.payload.parent_definition['type'], self.id)

    def fetch_profile(self):
        """Fetch FHIR sub profiles."""
        for profile in fhir_profile_retriever.fetch_all(self._profile):
            yield profile

    def _ensure_element_lookup(self):
        """Add lookup dict of properties and expand value[x].

        see https://build.fhir.org/formats.html#choice
        """

        def _camel_case(code_: str) -> str:
            """Return entity type from code."""
            if code_.lower() == 'datetime':
                return 'DateTime'
            if code_.lower() == 'codeableconcept':
                return 'CodeableConcept'
            return code_.title()

        elements = {element['id']: element for element in self._profile['snapshot']['element']}
        new_elements = {}
        to_delete = []
        for id_, element in elements.items():
            if '[x]' in id_:
                base = id_.replace('[x]', '')
                for type_ in element['type']:
                    code = type_['code']
                    if code is None:
                        print("?")
                    new_element = deepcopy(element)
                    new_element['id'] = f"{base}{_camel_case(code)}"
                    new_element['type'] = [type_]
                    new_elements[new_element['id']] = new_element
                to_delete.append(id_)
        if len(to_delete) > 0:
            # logger.info(f"Removing {to_delete}")
            for id_ in to_delete:
                elements.pop(id_)
            # logger.info(f"Adding {new_elements.keys()}")
            elements = elements | new_elements

        self._element_lookup = elements


class Property(BaseModel):
    """Resource.property and it's FHIR definition."""

    flattened_key: str
    """The key in a flattened representation."""
    simple_key: str
    """The simple key direct from parent's point of view."""
    root_element: dict
    """The fhir profile of the root."""
    leaf_elements: Optional[List[dict]] = []
    """The fhir profile of the leaf."""
    value: Any
    """The value."""
    complete: bool = False
    """Have we discovered schema profiles"""


class ObservableProperty(ObservableData):
    """Overrides payload type."""

    payload: Property
    """A property in a resource"""


class Model(Command):
    """Delegates to a collection of Entity."""

    entities: Optional[OrderedDict[str, Entity]] = collections.OrderedDict()
    dependency_order: Optional[List[str]] = []

    def notify(self, observable: ObservableData, context: Context = None, *args, **kwargs) -> None:
        """NO-OP, entities process the data."""
        pass

    def interested(self, observable: ObservableData) -> bool:
        """Delegate to entities."""
        return any(entity.interested(observable) for entity in self.entities)

    def observe(self, observable):
        """Register self with data if interested.

        :type observable: ObservableData|list
        """
        assert observable
        observable_list = observable
        if not isinstance(observable, list):
            observable_list = [observable]
        for observable_ in observable_list:
            for entity in self.entities.values():
                if entity.interested(observable_):
                    observable_.register_observer(entity)
        return observable

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


class TransformerContext(Context):
    """Typed context."""

    model: Model
    """A collection of Entity."""

    resource: Optional[ObservableData]
    """Source object with entity and handlers."""

    properties: Optional[List[Property]]
    """A list of transformed properties"""

    entity: Optional[Entity]
    """Model Entity associated with transformer."""

    simplify: Optional[bool] = False
    """Flag, if set, remove FHIR scaffolding"""


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
