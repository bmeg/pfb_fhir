"""Handle Entity observations."""
from copy import deepcopy, copy
from typing import Any, Dict

from pfb_fhir.common import first_occurrence
from pfb_fhir.model import Entity, Property, TransformerContext
from pfb_fhir.observable import ObservableData
import logging
from flatten_json import flatten

logger = logging.getLogger(__name__)

# save discovered schema elements keyed by entity_id flattened_property
WALKED_PROPERTIES: Dict[str, Dict[str, Property]] = dict({})


def handler_factory(entity: Entity):
    """Assign handler."""
    if entity.category not in ['sub-profile']:
        entity.set_handler(resource_handler)


def resource_handler(entity: Entity, observable: ObservableData, context: TransformerContext, *args, **kwargs):
    """Process resource by chaining observations on child properties."""
    context.resource = observable.payload
    context.entity = entity

    # set up a dict to lookup properties
    elements = entity.element_lookup

    # append resourceType mock element so that 'resourceType' field flows
    resource_type = observable.payload['resourceType']
    resource_id = observable.payload['id']
    resource_element = elements[resource_type]
    resource_type_element = {
        "id": f"{resource_type}.resourceType",
        "short": resource_element['short'],
        "definition": resource_element['definition'],
        "type": [
            {
                "code": "string"
            }
        ],
    }
    elements[resource_type_element['id']] = resource_type_element

    # walk the payload
    # separate into  dot notation key & val
    properties = {k: {'value': v} for k, v in flatten(observable.payload, '.').items()}

    # Initialize in memory cache
    # it is technically possible to mix simplify T/F between calls
    # the lookups are different depending on setting, so include that
    # in the cache key.
    cache_key = f"{entity.id}:{context.simplify}"
    if entity.id not in WALKED_PROPERTIES:
        WALKED_PROPERTIES[cache_key] = {}
    # for this entity
    walked_properties = WALKED_PROPERTIES[cache_key]

    # retrieve definition for each element.
    resource_properties: Dict[str, Property] = {}
    for flattened_key in properties:
        if flattened_key.startswith('contained'):
            logger.warning(
                f"{resource_type}/{resource_id} includes 'contained' resources. Unsupported at this time. Ignoring."
            )
            logger.warning(properties[flattened_key])
            continue
        # see if we've walked them up already
        if flattened_key in walked_properties:
            resource_properties[flattened_key] = copy(walked_properties[flattened_key])
            resource_properties[flattened_key].value = properties[flattened_key]['value']
            continue
        simple_key = flattened_key.split('.')[0]
        if f"{resource_type}.{simple_key}" in elements:
            resource_properties[flattened_key] = Property(
                flattened_key=flattened_key, simple_key=simple_key,
                value=properties[flattened_key]['value'],
                root_element=elements[f"{resource_type}.{simple_key}"],
                leaf_elements=[]
            )
        elif isinstance(observable.payload[simple_key], dict) and 'extension' in observable.payload[simple_key]:
            resource_properties[flattened_key] = Property(
                flattened_key=flattened_key, simple_key=simple_key,
                value=properties[flattened_key]['value'],
                root_element=context.model.entities['Extension'].profile['snapshot']['element'][0],
                leaf_elements=[]
            )
        else:
            if first_occurrence(f'Could not find payload property definition. {resource_type}.{simple_key}'):
                logger.warning((f'Could not find payload property definition. {resource_type}.{simple_key}', resource_type, observable.payload['id'], flattened_key, elements.keys()))

    properties = resource_properties
    # at this point every item has a root element, a flattened key, a simple key and value

    # Examine each key part
    context.properties = properties
    for property_ in properties.values():
        if not property_.complete:
            # logger.debug(f"Finding profiles for {entity.id}:{property_.flattened_key}")
            walk_property(context, entity, property_, observable.payload[property_.simple_key])
            property_.complete = True
            walked_properties[property_.flattened_key] = property_

    # at this point each property has a flattened key in dot notation
    # and a corresponding array of leaf_elements which contain FHIR.profile elements


def walk_property(context: TransformerContext, entity: Entity, property_: Property, payload_value: Any):
    """Process property, traverse profile tree."""
    key_parts = [key_part for key_part in property_.flattened_key.split('.') if not key_part.isnumeric()]
    model = context.model
    key_type = None
    key_prefix = ''

    for key_part in key_parts:
        if key_type:
            entity = model.entities[key_type]
            assert entity
        tuple_ = _extract_key_element_type(key_prefix + key_part, entity)
        if not tuple_:
            logger.debug(f"{key_prefix + key_part} not found in {entity.id}. root_element {property_.root_element['id']}")
            if not (isinstance(payload_value, dict) and ('extension' in payload_value or 'extension' in payload_value[key_part])):
                print("?")
                assert False, f"This does not seem to be an extension. '{key_prefix + key_part}'  from {property_.flattened_key} not found in {entity.id}"
            tuple_ = ('Extension', model.entities['Extension'].profile['snapshot']['element'][0])

        key_type, leaf_element = tuple_

        assert key_type

        leaf_element = copy(leaf_element)
        leaf_element['type'] = [{'code': key_type}]

        property_.leaf_elements.append(leaf_element)
        if key_type == 'BackboneElement':
            key_type = None  # don't switch entity
            key_prefix = key_part + '.'
        else:
            key_prefix = ''  # we've switched entity, no more prefix


def _extract_key_element_type(key_, entity_) -> tuple:
    """Get the type and FHIR element."""
    if key_ == 'resourceType':
        resource_type_element = copy(entity_.profile['snapshot']['element'][0])
        resource_type_element['id'] = resource_type_element['id'] + '.resourceType'
        resource_type_element["type"] = [
            {
                "code": "string"
            }
        ]
        return 'string', resource_type_element

    if f"{entity_.id}.{key_}" in entity_.element_lookup:
        element_ = entity_.element_lookup[f"{entity_.id}.{key_}"]
        return _extract_type(key_, element_, entity_), element_

    return None


def _extract_key_prefix(key_):
    """Return a.b if key a.b.c, otherwise None."""
    key_path_parts = key_.split('.')
    if len(key_path_parts) == 1:
        return None
    return '.'.join(key_path_parts[:-1])


def _extract_type(key_, element_, entity_) -> str:
    """Filter type."""
    return next(iter([t['code'] for t in element_['type']]), None)
