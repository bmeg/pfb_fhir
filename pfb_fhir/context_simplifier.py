"""package."""
import re
from collections import defaultdict
from copy import deepcopy
from typing import Dict, List

import logging

from urllib.parse import urlparse

from pfb_fhir.model import TransformerContext

logger = logging.getLogger(__name__)


class ContextSimplifier(object):
    """Simplify flattened properties."""

    @staticmethod
    def simplify(context: TransformerContext) -> TransformerContext:
        """

        :rtype: object
        """
        assert context.properties
        logger.info(f"{context.resource['resourceType']}/{context.resource['id']}")
        simplified_properties = ContextSimplifier._group_by_root(context)
        simplified_properties = ContextSimplifier._extensions(simplified_properties)
        simplified_properties = ContextSimplifier._single_item_lists(simplified_properties)
        simplified_properties = ContextSimplifier._codings(simplified_properties)
        simplified_properties = ContextSimplifier._identifiers(simplified_properties)
        # logger.info([p.flattened_key for p in context.properties.values()])
        context.properties = {}
        for k, properties in simplified_properties.items():
            for p in properties:
                context.properties[p.flattened_key] = p
        return context

    @staticmethod
    def _group_by_root(context: TransformerContext) -> Dict[str, list]:
        """Gather flattened properties to original key."""
        simplified_properties = defaultdict(list)
        for property_ in context.properties.values():
            simplified_properties[property_.leaf_elements[0]['id']].append(property_)
        return simplified_properties

    @staticmethod
    def _single_item_lists(simplified_properties: Dict[str, List]) -> Dict[str, List]:
        """Simplify values with single item lists."""
        # values single item array
        # inspect 3x to get embedded single item lists
        for i in range(3):
            logger.debug(f"iterate {i}")
            for k, properties in simplified_properties.items():
                if k == 'Extension':
                    continue
                entity, property_name = k.split('.')
                # ignore identifier array, handled separately
                if property_name == 'identifier':
                    continue
                flattened_keys = [p.flattened_key for p in properties]
                for flattened_key in flattened_keys:
                    flattened_key_parts = flattened_key.split('.')
                    array_index = -1
                    if '0' in flattened_key_parts:
                        array_index = flattened_key_parts.index('0')
                    if array_index > 0:
                        property_name = flattened_key_parts[array_index - 1]
                        if not any([f"{property_name}.1" in k for k in flattened_keys]):
                            logger.debug(f"{property_name}.0  in {flattened_key} is a single item list")
                            for p in properties:
                                # replace first occurrence of index in property name
                                p.flattened_key = p.flattened_key.replace(f"{property_name}.0", property_name, 1)
                simplified_properties[k] = properties

        return simplified_properties

    @staticmethod
    def _extensions(simplified_properties: Dict[str, List]) -> Dict[str, List]:
        """Simplify root values with extensions."""
        # There are at least two ways to define extensions
        # A)
        #   "extension": [
        #     {
        #       "extension": [
        #  lets call these "root extensions"
        #
        # B)
        #   "_receivedTime": {
        #     "extension": [
        #       {
        #         "extension": [
        #  lets call these "named extensions"
        simplified_extensions_key = None
        simplified_extensions = []

        for k, properties in simplified_properties.items():
            if k.endswith('extension'):
                # root extensions
                simplified_extensions_key, simplified_extensions = ContextSimplifier._root_extension(k, properties)
            elif k == 'Extension':
                # named extensions
                simplified_extensions_key, simplified_extensions = ContextSimplifier._named_extension(k, properties)
            else:
                continue

        if simplified_extensions_key:
            del simplified_properties[simplified_extensions_key]
            simplified_properties[simplified_extensions_key] = simplified_extensions

        return ContextSimplifier._property_extensions(simplified_properties)

    @staticmethod
    def _root_extension(k, properties):
        simplified_extensions_key = k
        simplified_extensions = []
        # there can be many extensions, iterate through all
        extension_index = 0
        while True:
            flattened_keys = [p.flattened_key for p in properties if
                              p.flattened_key.startswith(f"extension.{extension_index}")]
            if len(flattened_keys) == 0:
                logger.warning(f"{k} has no flattened keys?")
                break
            url_property = next(
                iter([p for p in properties if p.flattened_key == f"extension.{extension_index}.url"]), None)
            extension_name = url_property.value.split('/')[-1]
            # there can be many sub-extensions, iterate through all
            sub_extension_index = 0
            while True:
                sub_extension_flattened_keys = [p.flattened_key for p in properties if
                                                f"extension.{extension_index}.extension.{sub_extension_index}" in p.flattened_key]
                if len(sub_extension_flattened_keys) == 0:
                    break
                sub_extension_url_property = next(
                    iter([p for p in properties if
                          p.flattened_key == f"extension.{extension_index}.extension.{sub_extension_index}.url"]))
                sub_extension_value = next(
                    iter([p for p in properties if
                          p.flattened_key.startswith(f"extension.{extension_index}.extension.{sub_extension_index}.value")]),
                    None)

                sub_extension_name = sub_extension_url_property.value.split('/')[-1]
                simplified_extension = deepcopy(sub_extension_value)
                simplified_extension.flattened_key = f"{extension_name}.{sub_extension_name}"
                simplified_extensions.append(simplified_extension)
                sub_extension_index += 1

            extension_index += 1
        if len(simplified_extensions) > 0:
            return simplified_extensions_key, simplified_extensions
        return None, None

    @staticmethod
    def _named_extension(k, properties):
        simplified_extensions_key = k
        simplified_extensions = []
        extension_keys = list(set([p.simple_key for p in properties]))
        if not len(extension_keys) == 1:
            assert False, f"{k} Unexpected extension, does not start with extension, " \
                          "nor has a key prefix."
        extension_key = extension_keys[0]

        # there can be many extensions, iterate through all
        extension_index = 0
        while True:
            flattened_keys = [p.flattened_key for p in properties if
                              p.flattened_key.startswith(f"{extension_key}.extension.{extension_index}")]
            if len(flattened_keys) == 0:
                logger.warning(f"{k} has no flattened keys?")
                break
            url_property = next(
                iter([p for p in properties if p.flattened_key == f"{extension_key}.extension.{extension_index}.url"]), None)
            extension_name = url_property.value.split('/')[-1]
            # there can be many sub-extensions, iterate through all
            sub_extension_index = 0
            while True:
                sub_extension_flattened_keys = [p.flattened_key for p in properties if
                                                f"{extension_key}.extension.{extension_index}.extension.{sub_extension_index}" in p.flattened_key]
                if len(sub_extension_flattened_keys) == 0:
                    break
                sub_extension_url_property = next(
                    iter([p for p in properties if
                          p.flattened_key == f"{extension_key}.extension.{extension_index}.extension.{sub_extension_index}.url"]))
                sub_extension_value = next(
                    iter([p for p in properties if
                          p.flattened_key.startswith(f"{extension_key}.extension.{extension_index}.extension.{sub_extension_index}.value")]),
                    None)

                sub_extension_name = sub_extension_url_property.value.split('/')[-1]
                simplified_extension = deepcopy(sub_extension_value)
                simplified_extension.flattened_key = f"{extension_name}.{sub_extension_name}"
                simplified_extensions.append(simplified_extension)
                sub_extension_index += 1

            extension_index += 1
        if len(simplified_extensions) > 0:
            return simplified_extensions_key, simplified_extensions
        return None, None

    # @staticmethod
    # def _extensions_old(simplified_properties: Dict[str, List]) -> Dict[str, List]:
    #     """Simplify root values with extensions."""
    #
    #     simplified_extensions = []
    #     simplified_extensions_key = None
    #     for k, properties in simplified_properties.items():
    #         # root extensions
    #         if not (k.endswith('extension') or k == 'Extension'):
    #             continue
    #         simplified_extensions_key = k
    #         extension_index = 0
    #         extension_flattened_key_prefix = None
    #         extension_flattened_key_prefix_set = set([p.flattened_key for p in properties if p.simple_key == 'extension'])
    #         if all([p.simple_key == 'extension' for p in properties]):
    #             extension_flattened_key_prefix = None
    #         elif len(extension_flattened_key_prefix_set) == 1:
    #             extension_flattened_key_prefix = extension_flattened_key_prefix_set.pop()
    #         while True:
    #             flattened_keys = [p.flattened_key for p in properties if
    #                               p.flattened_key.startswith(f"extension.{extension_index}")
    #                               or
    #                               p.flattened_key.startswith(f"{p.simple_key}.extension.{extension_index}")
    #                               ]
    #
    #             if len(flattened_keys) == 0:
    #                 logger.warning(f"{k} has no flattened keys?")
    #                 break
    #
    #             url_property = next(
    #                 iter([p for p in properties if p.flattened_key == f"extension.{extension_index}.url"]), None)
    #             extension_key = None
    #             if not url_property:
    #                 # assert url_property, f"{k} not found extension.{extension_index}.url"
    #                 extension_keys = list(set([p.simple_key for p in properties]))
    #                 if not len(extension_keys) == 1:
    #                     print("?")
    #                     assert False, f"{k} Unexpected extension, does not start with extension, "\
    #                                           "nor has a key prefix."
    #                 extension_key = extension_keys[0]
    #                 url_property = next(
    #                     iter([p for p in properties if p.flattened_key == f"{extension_key}.extension.{extension_index}.url"]), None)
    #                 assert url_property, f"{k} not found {extension_key}.{extension_index}.url"
    #
    #             extension_name = url_property.value.split('/')[-1]
    #             sub_extension_index = 0
    #             while True:
    #                 if extension_key:
    #                     sub_extension_flattened_keys = [p.flattened_key for p in properties if
    #                                                     f"{extension_key}.extension.{extension_index}.extension.{sub_extension_index}" in p.flattened_key]
    #                     if len(sub_extension_flattened_keys) == 0:
    #                         break
    #                     sub_extension_url_property = next(
    #                         iter([p for p in properties if
    #                               p.flattened_key == f"{extension_key}.extension.{extension_index}.extension.{sub_extension_index}.url"]))
    #                     sub_extension_value = next(
    #                         iter([p for p in properties if
    #                               p.flattened_key == f"{extension_key}.extension.{extension_index}.extension.{sub_extension_index}.valueCoding.code"]),
    #                         None)
    #                     if not sub_extension_value:
    #                         sub_extension_value = next(
    #                             iter([p for p in properties if
    #                                   p.flattened_key == f"{extension_key}.extension.{extension_index}.extension.{sub_extension_index}.valueString"]),
    #                             None)
    #                 else:
    #                     sub_extension_flattened_keys = [p.flattened_key for p in properties if
    #                                                     f"extension.{extension_index}.extension.{sub_extension_index}" in p.flattened_key]
    #                     if len(sub_extension_flattened_keys) == 0:
    #                         break
    #                     sub_extension_url_property = next(
    #                         iter([p for p in properties if
    #                               p.flattened_key == f"extension.{extension_index}.extension.{sub_extension_index}.url"]))
    #                     sub_extension_value = next(
    #                         iter([p for p in properties if
    #                               p.flattened_key == f"extension.{extension_index}.extension.{sub_extension_index}.valueCoding.code"]),
    #                         None)
    #                     if not sub_extension_value:
    #                         sub_extension_value = next(
    #                             iter([p for p in properties if
    #                                   p.flattened_key == f"extension.{extension_index}.extension.{sub_extension_index}.valueString"]),
    #                             None)
    #
    #                 sub_extension_name = sub_extension_url_property.value.split('/')[-1]
    #                 simplified_extension = deepcopy(sub_extension_value)
    #                 simplified_extension.flattened_key = f"{extension_name}.{sub_extension_name}"
    #                 simplified_extensions.append(simplified_extension)
    #                 sub_extension_index += 1
    #
    #             extension_index += 1
    #
    #     if simplified_extensions_key:
    #         del simplified_properties[simplified_extensions_key]
    #         simplified_properties[simplified_extensions_key] = simplified_extensions
    #
    #     return ContextSimplifier._property_extensions(simplified_properties)

    @staticmethod
    def _property_extensions(simplified_properties: Dict[str, List]) -> Dict[str, List]:
        """Simplify root values with extensions."""
        simplified_extensions = {}
        for k, properties in simplified_properties.items():
            # property extensions
            items_to_remove = []
            items_to_add = []
            if k == 'Extension':
                continue
            extensions = defaultdict(dict)
            for p in properties:
                if 'extension' not in p.flattened_key:
                    continue
                # this is too simplistic, properties in the extension may be nested
                matches = re.match(r'(.*extension\.[0-9]+)\.(.*)', p.flattened_key)
                path = matches.group(1)
                key = matches.group(2)
                extensions[path][key] = p
            if len(extensions.keys()) > 0:
                # how many extensions are there for this property?
                extension_instances = []
                for extension_instance in extensions.keys():
                    if extension_instance.count('extension') == 1:
                        extension_instances.append(extension_instance)
                for extension_instance in extension_instances:
                    property_key = extension_instance.split('extension')[0]
                    for extension_key in extensions:
                        if extension_key.startswith(extension_instance) and extension_key != extension_instance:
                            extension_name = extensions[extension_instance]['url'].value.split('/')[-1]
                            sub_extension_name = extensions[extension_key]['url'].value.split('/')[-1]
                            sub_extension_value = next(iter(v_ for k_, v_ in extensions[extension_key].items() if k_.startswith('value') ), None)
                            assert sub_extension_value, (k, extension_instance)
                            simplified_property = deepcopy(sub_extension_value)
                            simplified_property.flattened_key = f"{property_key}{extension_name}.{sub_extension_name}"
                            items_to_add.append(simplified_property)
                            items_to_remove.extend(extensions.keys())
            if len(items_to_add) > 0:
                filtered_properties = []
                for p in properties:
                    if any([p.flattened_key.startswith(partial_key) for partial_key in items_to_remove]):
                        continue
                    filtered_properties.append(p)
                properties = filtered_properties
                properties.extend(items_to_add)
                simplified_extensions[k] = properties

        for k in simplified_extensions:
            simplified_properties[k] = simplified_extensions[k]
        return simplified_properties

    @staticmethod
    def _codings(simplified_properties: Dict[str, List]) -> Dict[str, List]:
        """Values with codings (just look at first level of dict for coding)."""
        original_coded_values = defaultdict(list)
        for k, properties in simplified_properties.items():
            flattened_keys = [p.flattened_key for p in properties if 'coding' in p.flattened_key]
            simplified_coding_values = []
            if len(flattened_keys) > 0:
                system = next(iter([k for k in flattened_keys if k.endswith('.coding.system')]), None)
                code = next(iter([k for k in flattened_keys if k.endswith('.coding.code')]), None)
                display = next(iter([k for k in flattened_keys if k.endswith('.coding.display')]), None)
                if system:
                    original_coded_values[k].append(system)
                    system = next(iter([p for p in properties if p.flattened_key == system]), None)
                if code:
                    original_coded_values[k].append(code)
                    code = next(iter([p for p in properties if p.flattened_key == code]), None)
                if display:
                    original_coded_values[k].append(display)
                    display = next(iter([p for p in properties if p.flattened_key == display]), None)
                if system and code:
                    base_key = system.flattened_key.replace('.coding.system', '')
                    system_value = system.value.split('/')[-1]
                    # logger.info(f"{base_key}.{system_value} = {code.value}")
                    simplified_coding = deepcopy(code)
                    simplified_coding.flattened_key = f"{base_key}.{system_value}"
                    simplified_coding_values.append(simplified_coding)
                elif system and display:
                    base_key = system.flattened_key.replace('.coding.system', '')
                    # display_value = display.value
                    # logger.info(f"{base_key}.{system_value}.display = {display_value}")
                    simplified_coding = deepcopy(display)
                    simplified_coding.flattened_key = f"{base_key}.{system_value}.display"
                    simplified_coding_values.append(simplified_coding)
            simplified_properties[k].extend(simplified_coding_values)
        for k, original_coded_values in original_coded_values.items():
            # logger.info([(k, p.flattened_key) for p in simplified_properties[k] if p.flattened_key not in original_coded_values])
            simplified_properties[k] = [p for p in simplified_properties[k] if
                                        p.flattened_key not in original_coded_values]
        return simplified_properties

    @staticmethod
    def _identifiers(simplified_properties: Dict[str, List]) -> Dict[str, List]:
        """Simplify identifier to single property"""
        for k, properties in simplified_properties.items():
            if k == 'Extension':
                continue
            entity, property_name = k.split('.')
            # ignore identifier array, handled separately
            if property_name != 'identifier':
                continue
            items_to_remove = []
            items_to_add = []
            index = 0
            while True:
                identifier_properties = [p for p in properties if p.flattened_key.startswith(f"identifier.{index}")]
                if len(identifier_properties) == 0:
                    break
                system = next(iter([p for p in identifier_properties if p.flattened_key == f"identifier.{index}.system"]), None)
                value = next(iter([p for p in identifier_properties if p.flattened_key == f"identifier.{index}.value"]), None)
                type_code_value = next(iter([p.value for p in identifier_properties if p.flattened_key == f"identifier.{index}.type.coding.0.code"]), None)
                # logger.info((system.value, value.value, type_code_value))
                system_name = type_code_value
                if not system_name:
                    url_parts = urlparse(system.value)
                    if url_parts.path:
                        system_name = url_parts.path.split('/')[-1]
                    else:
                        netloc_parts = url_parts.netloc.split('.')
                        system_name = netloc_parts[-2] if len(netloc_parts) > 2 else netloc_parts[-1]
                # logger.info((f"identifier.{index}.{system_name}", value.value))
                items_to_remove.extend([p.flattened_key for p in identifier_properties])
                simplified_identifier = deepcopy(value)
                simplified_identifier.flattened_key = f"identifier.{index}.{system_name}"
                items_to_add.append(simplified_identifier)
                index += 1
            if len(items_to_add) > 0:
                filtered_properties = []
                for p in properties:
                    if any([p.flattened_key.startswith(partial_key) for partial_key in items_to_remove]):
                        continue
                    filtered_properties.append(p)
                properties = filtered_properties
                properties.extend(items_to_add)
                simplified_properties[k] = properties

        return simplified_properties



