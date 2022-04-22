"""package."""

from typing import Any, Dict

import logging

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ResourceSimplifier(object):
    """Simplify a fhir resource."""

    @staticmethod
    def simplify(fhir_resource: Dict) -> Dict:
        simple_resource = {k: PropertySimplifier(name=k, value=v).value for k, v in fhir_resource.items() if k != 'extension'}
        simple_extension = {}
        if 'extension' in fhir_resource:
            simple_extension = PropertySimplifier(name='extension', value=fhir_resource['extension']).value
        return simple_resource | simple_extension


class PropertySimplifier(BaseModel):
    """Container for FHIR property pre-processing."""

    name: str
    value: Any

    def __init__(self, **data):
        """Simplify property value."""
        value = data['value']
        if data['name'] == 'identifier':
            value = self._simplify_resource_identifiers(value)
        elif data['name'] == 'extension':
            value = self._simplify_resource_extension(value)
        else:
            value = self._simplify_value(value)
        data['value'] = value
        super().__init__(**data)

    @staticmethod
    def _simplify_value(value):
        """Single item lists to scalar, extensions promoted as named variables."""
        # TODO - simplify
        if isinstance(value, list) and len(value) == 1:
            value = value[0]

        if isinstance(value, dict):

            # values with extensions
            if 'extension' in value:

                for extension in value['extension']:
                    assert 'extension' in extension
                    extension = extension['extension']
                    for extension_item in extension:
                        extension_property_name, extension_property_value = PropertySimplifier._simplify_extension(extension_item)
                        value[extension_property_name] = extension_property_value

                del value['extension']

            # values with codings (just look at first level of dict for coding)
            for k, v in value.items():
                if not isinstance(v, dict):
                    continue
                if 'coding' in v:
                    coding = v['coding']
                    if isinstance(coding, list) and len(coding) == 1:
                        coding = coding[0]
                        assert 'code' in coding and 'system' in coding
                        value[k] = coding['code']
            # get codes too.
            if 'code' in value and 'system' in value and len(value.keys()) == 2:
                value = value['code']
            if 'code' in value and 'system' in value and 'value' in value:
                value = {
                    'code': value['code'],
                    'value': value['value'],
                }

            if 'coding' in value:
                coding = value['coding']
                if isinstance(coding, list) and len(coding) == 1:
                    coding = coding[0]
                    assert 'code' in coding and 'system' in coding
                    value = coding['code']

        if isinstance(value, dict):
            for k, v in value.items():
                if isinstance(v, list) and len(v) == 1:
                    value[k] = v[0]

        return value

    @staticmethod
    def _simplify_extension(extension_item):
        if len(extension_item) != 2:
            pass
        assert len(extension_item) == 2, extension_item
        assert 'url' in extension_item
        extension_property_name = None
        extension_property_value = None
        for k, v in extension_item.items():
            if k == 'url':
                extension_property_name = v
                continue
            extension_property_value = v
        if 'http' in extension_property_name:
            extension_property_name = extension_property_name.split('/')[-1]
        return extension_property_name, extension_property_value

    @staticmethod
    def _simplify_resource_extension(extensions):
        """Create simple dict from extensions."""
        # TODO - simplify.
        values = {}

        if not isinstance(extensions, list):
            extensions = [extensions]

        for extension in extensions:

            if 'extension' not in extension:
                extension_property_name, extension_property_value = PropertySimplifier._simplify_extension(extension)
                if extension_property_name in values:
                    if not isinstance(values[extension_property_name], list):
                        values[extension_property_name] = [values[extension_property_name]]
                    values[extension_property_name].append(PropertySimplifier._simplify_value(extension_property_value))
                else:
                    values[extension_property_name] = PropertySimplifier._simplify_value(extension_property_value)
                continue

            extension = extension['extension']

            for extension_item in extension:
                extension_property_name, extension_property_value = PropertySimplifier._simplify_extension(extension_item)
                if extension_property_name == 'text':
                    continue
                if isinstance(extension_property_value, list):
                    extension_property_value = [PropertySimplifier._simplify_value(v) for v in extension_property_value]
                if extension_property_name in values:
                    if not isinstance(values[extension_property_name], list):
                        values[extension_property_name] = [values[extension_property_name]]
                    values[extension_property_name].append(PropertySimplifier._simplify_value(extension_property_value))
                else:
                    values[extension_property_name] = PropertySimplifier._simplify_value(extension_property_value)

        return values

    @staticmethod
    def _simplify_resource_identifiers(identifiers):
        values = {}

        if not isinstance(identifiers, list):
            identifiers = [identifiers]

        for identifier in identifiers:
            if 'type' not in identifier:
                property_name = identifier['system']
                if 'http' in property_name:
                    property_name = property_name.split('/')[-1]
                values[property_name] = identifier['value']
                continue
            if 'coding' in identifier['type']:
                assert len(identifier['type']['coding']) == 1
                coding = identifier['type']['coding'][0]
                values[coding['code']] = identifier['value']
                continue
            assert False, f"unsupported identifier {identifier}"

        return values

