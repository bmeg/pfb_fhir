"""Implements base emitters."""
import abc
import io
import json
import os.path
from collections import defaultdict
from collections.abc import Iterator
from copy import deepcopy
from typing import List, Dict
import pathlib
from fastavro import reader

import inflection as inflection
import yaml
from pydantic import BaseModel, PrivateAttr

from pfb_fhir import run_cmd
from pfb_fhir.model import TransformerContext, FHIR_TYPES, InspectionResults, EntitySummary, EdgeSummary, Model
from contextlib import contextmanager
import pkg_resources
from dictionaryutils import dump_schemas_from_dir
import logging
from pfb_fhir.common import first_occurrence
from pfb_fhir.terminology.value_sets import ValueSets

logger = logging.getLogger(__name__)

STATIC_ENTITIES = [
    "_definitions",
    "_settings",
    "_terms",
]


class Emitter(BaseModel, abc.ABC):
    """Writes context to a directory."""

    work_dir: str
    """Directory|File to write to."""
    open_files: Dict[str, io.IOBase] = {}
    """Open files with lookup key."""

    class Config:
        """Allow arbitrary user types for fields (since we have reference to io.IOBase)."""

        arbitrary_types_allowed = True

    def __init__(self, **data):
        """Ensure output_path exists."""
        super().__init__(**data)
        pathlib.Path(self.work_dir).mkdir(parents=True, exist_ok=True)

    def close(self) -> None:
        """Close any open files."""
        for file in self.open_files.values():
            file.close()

    @abc.abstractmethod
    def emit(self, context: TransformerContext) -> bool:
        """Lookup or open file, write context to file."""
        pass


class DictionaryEmitter(Emitter):
    """Writes gen3 schema elements."""

    template: dict
    _value_sets: object = PrivateAttr()

    class Config:
        """Allow arbitrary user types for fields (since we have reference to dict)."""

        arbitrary_types_allowed = True

    def __init__(self, **data):
        """Append /gen3 to output_path, init template."""
        data["work_dir"] = data["work_dir"] + "/gen3"
        data["template"] = self._get_template()
        super().__init__(**data)
        assert self.template
        self._value_sets = ValueSets()

    @staticmethod
    def _get_template():
        resource_package = __name__
        path = 'gen3_schema_template.yaml'  # Do not use os.path.join()
        template_file = pkg_resources.resource_stream(resource_package, path)
        return yaml.load(template_file, Loader=yaml.SafeLoader)

    def emit(self, context: TransformerContext) -> bool:
        """Ensure file open, write row."""
        path = f'{self.work_dir}/{context.entity.id}.yaml'
        if path in self.open_files:
            # already wrote schema
            return True

        self.open_files[path] = open(path, "w")
        yaml.dump(self.render_schema(self.template, context), self.open_files[path])
        self.open_files[path].flush()

    def render_schema(self, template, context):
        """Render context into a gen3 schema."""
        schema = deepcopy(template)
        schema['id'] = context.entity.id
        schema['title'] = context.entity.id
        schema['category'] = context.entity.category
        schema['description'] = context.entity.profile['description']
        schema['links'] = [link for link in self.render_links(context)]
        schema['required'] = [required.replace('.', '_') for required in self.render_required(context)]
        for property_name, schema_property in self.render_property(context):
            schema['properties'][property_name] = schema_property
        return schema

    @staticmethod
    def render_links(context) -> Iterator[dict]:
        """Gen3 link collection."""
        for link_key, link in context.entity.links.items():
            _neighbor = link.targetProfile
            target_type = _neighbor.split('/')[-1]
            backref = inflection.pluralize(context.entity.id)
            name = inflection.pluralize(target_type)
            yield {
                'name': name,
                'backref': backref,
                'label': name,
                'target_type': target_type,
                'multiplicity': 'many_to_many',
                'required': link.required
            }

    @staticmethod
    def render_required(context) -> Iterator[str]:
        """Return fields that are mandatory."""
        for property_name in ['submitter_id', 'type']:
            yield property_name

        for property_ in context.properties.values():
            if property_.root_element.get('min', -1) > 0:
                yield property_.flattened_key

    def render_property(self, context) -> tuple[str, dict]:
        """Render the property type and description."""
        for property_ in context.properties.values():
            element = property_.root_element
            if property_.leaf_elements:
                element = property_.leaf_elements[-1]
            required = property_.root_element.get('min', -1) > 0

            assert 'type' in element, f"no type? {element}"

            type_codes = [DictionaryEmitter.normalize_type(type_['code'], property_) for type_ in element['type']]
            if not required:
                type_codes.append('null')

            schema_property = {
                    'type': type_codes, 'description': '. '.join(DictionaryEmitter.description(property_))
                }
            term_def = None
            for type_ in element['type']:
                code = type_['code']
                term_def = DictionaryEmitter.get_term_def(code, property_)
                if term_def:
                    break
            if term_def:
                description = '. '.join(DictionaryEmitter.description(property_) + [term_def['term_url']])
                schema_property = {
                    'type': type_codes,
                    'description': description,
                    'term': {'termDef': term_def, 'description': description}
                }
                # add enum
                enum_codes = self._value_sets.codes(term_def['term_url'])
                if enum_codes and term_def['strength'] in ['required', 'preferred']:
                    del schema_property['type']
                    schema_property['enum'] = enum_codes
                elif enum_codes:
                    schema_property['description'] = schema_property['description'] + ' ' + '|'.join(enum_codes)
                    schema_property['term']['description'] = schema_property['description']
                else:
                    logger.debug(f"No enumeration found for: {property_.flattened_key} {term_def['term_url']}")

            yield property_.flattened_key.replace('.', '_'), schema_property

    @staticmethod
    def get_term_def(code, property_) -> str:
        """Cast to json schema types."""
        term_def = None
        if code in ['code', 'Code']:
            for element in reversed(property_.leaf_elements):
                value_set = element.get('binding', {}).get('valueSet', None)
                if value_set:
                    value_set_version = None
                    if '|' in value_set:
                        value_set_version = value_set.split('|')[-1]
                    value_set_id = value_set.split('|')[0].split('/')[-1]
                    strength = 'required'
                    for element_ in reversed(property_.leaf_elements):
                        if 'binding' in element_:
                            strength = element_['binding'].get('strength', None)
                    term_def = {
                        'term': value_set_id,
                        'source': 'fhir',
                        'cde_id': value_set_id,
                        'cde_version': value_set_version,
                        'term_url': value_set,
                        'strength': strength
                    }
                    break
        return term_def

    @staticmethod
    def normalize_type(code, property_) -> str:
        """Cast to json schema types."""
        if code in FHIR_TYPES:
            return FHIR_TYPES[code].json_type
        if code in ['code', 'uri', 'url', 'canonical', 'xhtml', 'date', 'instant', 'id', 'markdown', 'base64Binary',
                    'string', 'dateTime', 'String', 'Code', 'DateTime']:
            return 'string'
        if code in ['decimal', 'positiveInt', 'integer', 'Decimal', 'Integer']:
            return "number"
        if code in ['boolean', 'Boolean']:
            return 'boolean'
        if first_occurrence(f"No mapping for {code} default to string"):
            logger.warning(f"No mapping for {code} default to string")
        return 'string'

    @staticmethod
    def description(property_) -> List[str]:
        """Concatenates descriptions (utility)."""
        descriptions = []
        # add short description of ancestors
        for leaf_element in property_.leaf_elements[:-1]:
            if leaf_element['short'] not in descriptions:
                descriptions.append(leaf_element['short'])
        # add long description of leaf
        leaf_element = property_.leaf_elements[-1]
        if leaf_element['short'] not in descriptions:
            descriptions.append(leaf_element.get('definition', leaf_element['short']))

        return descriptions


class IdentifierAlias(BaseModel):
    """Lookup id and resource type given system and value."""

    submitter_id: str
    resource_type: str


class PFBJsonEmitter(Emitter):
    """Writes transform to PFB friendly JSON."""

    aliases: Dict[str, IdentifierAlias] = {}

    class Config:
        """Allow arbitrary user types for fields (since we have reference to dict)."""

        arbitrary_types_allowed = True

    def __init__(self, **data):
        """Append /pfb to output_path."""
        data["work_dir"] = data["work_dir"] + "/pfb"
        super().__init__(**data)

    def _update_aliases(self, pfb_dict: dict) -> None:
        """Maintain a lookup table."""
        i = 0
        while True:
            system = f"identifier_{i}_system"
            value = f"identifier_{i}_value"
            if system in pfb_dict['object']:
                if value not in pfb_dict['object']:
                    value = f"identifier_{i}_id"
                    if value not in pfb_dict['object']:
                        logger.warning(f"identifier_{i}_system - no value or id found?")
                        continue
                self.aliases[f"{pfb_dict['object'][system]}/{pfb_dict['object'][value]}"] = \
                    IdentifierAlias(resource_type=pfb_dict['name'], submitter_id=pfb_dict['id'])
                i += 1
            else:
                break

    def emit(self, context: TransformerContext) -> bool:
        """Ensure file open, write row."""
        path = f'{self.work_dir}/{context.entity.id}.ndjson'
        if path not in self.open_files:
            self.open_files[path] = open(path, "w")
        pfb_dict = self.render_json(context)
        self._update_aliases(pfb_dict)
        json.dump(pfb_dict, self.open_files[path])
        self.open_files[path].write('\n')
        return True

    def render_json(self, context):
        """Create links, add submitter_id and other PFB dependencies."""
        links = []
        for link_key, link in context.entity.links.items():
            if link_key not in context.resource and link.required:
                if first_occurrence(f"Could not find {link_key} in {context.resource['resourceType']}"):
                    logger.warning(f"Could not find {link_key} in {context.resource['resourceType']}.{context.resource['id']}")
            if link_key in context.resource:
                references = context.resource[link_key]
                if not isinstance(context.resource[link_key], list):
                    references = [context.resource[link_key]]
                for reference in references:
                    reference_parts = self._link_submitter_id(reference)
                    if reference_parts['resource_type'] is None:
                        reference_parts['resource_type'] = link.targetProfile.split('/')[-1]
                    links.append({
                        'dst_id': reference_parts['submitter_id'],
                        'dst_name': reference_parts['resource_type'],
                    })

        # create simple flat json
        flattened = {p.flattened_key.replace('.', '_'): p.value for p in context.properties.values()}
        flattened['links'] = links
        flattened['submitter_id'] = context.resource['id']

        pfb_record = {'id': flattened['id'], 'name': context.entity.id}
        if 'links' in flattened:
            relations = flattened['links']
            pfb_record['relations'] = relations
            # for link in flattened['links']:
            #     del flattened[link['dst_name']]
            del flattened['links']
        pfb_record['object'] = flattened

        return pfb_record

    def _link_submitter_id(self, fhir_reference):
        """Transform to PFB friendly submitter_id link."""
        if 'reference' in fhir_reference:
            if '?identifier' in fhir_reference['reference']:
                resource_type = fhir_reference['reference'].split('?')[0]
                submitter_id = fhir_reference['reference'].split('|')[-1]
                return {'submitter_id': submitter_id, 'resource_type': resource_type}
            else:
                reference_parts = fhir_reference['reference'].split('/')
                return {'submitter_id': reference_parts[-1], 'resource_type': reference_parts[0]}
        if 'valueReference' in fhir_reference:
            reference_parts = fhir_reference['valueReference']['reference'].split('/')
            return {'submitter_id': reference_parts[-1], 'resource_type': reference_parts[0]}
        if 'identifier' in fhir_reference:
            # see https://build.fhir.org/references.html#logical
            # {
            #   'display': 'HEALTHALLIANCE HOSPITALS, INC',
            #   'identifier': {'system': 'https://github.com/synthetichealth/synthea', 'value': 'ef58ea08-d883-3957-8300-150554edc8fb'}
            # }
            if 'http' in fhir_reference['identifier']['system']:
                key = f"{fhir_reference['identifier']['system']}/{fhir_reference['identifier']['value']}"
                assert key in self.aliases, f"{key} not seen"
                alias = self.aliases[key]
                return {
                    'submitter_id': alias.submitter_id,
                    'resource_type': alias.resource_type
                }
        raise Exception(f'Not supported pfb link {fhir_reference}')


class PFB(BaseModel):
    """Delegate to a set of emitters."""

    emitters: List[Emitter]
    """Emitters that will do the actual IO"""
    file_path: str
    """Destination avro file."""
    model: Model
    """Model that processed the data."""

    _results: InspectionResults = PrivateAttr()

    def emit(self, context: TransformerContext) -> bool:
        """Delegate."""
        return any([emitter.emit(context) for emitter in self.emitters])

    def close(self) -> None:
        """Delegate close, ensure path to pfb exists."""
        for emitter in self.emitters:
            emitter.close()
        # create our path
        path = pathlib.Path(self.file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def results(self) -> InspectionResults:
        """Getter, introspection of PFB."""
        return self._results

    # @property
    def set_results(self, results: InspectionResults):
        """Setter."""
        self._results = results


@contextmanager
def pfb(work_dir: str, file_path: str, model: Model) -> Iterator[PFB]:
    """Create a context with our emitters, close when done.

    :param work_dir: Used for transient files, will create if it doesn't exist.
    :param file_path: Path to PFB file output.
    :param model: schema entities written out in config files order.
    """
    # create emitters
    pfb_json_emitter = PFBJsonEmitter(work_dir=work_dir)
    data_dictionary_emitter = DictionaryEmitter(work_dir=work_dir)
    pfb_ = PFB(emitters=[pfb_json_emitter, data_dictionary_emitter], file_path=file_path, model=model)
    try:
        # return to caller
        yield pfb_
    finally:
        # tell emitters to close
        pfb_.close()
        # ask gen3 to create a single dump file. See WORK_FILES
        schema_dump_path = f"{work_dir}/dump.json"
        schema_dump_ordered_path = f"{work_dir}/dump-ordered.json"
        with open(schema_dump_path, 'w') as f:
            json.dump(dump_schemas_from_dir(data_dictionary_emitter.work_dir), f)
        # verify this worked
        schema = json.load(open(schema_dump_path))
        assert schema
        assert len(schema.keys()) > 0

        # Note: `dump_schemas_from_dir` creates the schema in an unspecified order, as
        # under the covers it uses `glob to find the files`).
        # However, we need to reshape the schema:
        # * avro delivers records to its reader in the order they were defined in the schema
        # * terra processes the file a page at a time, and verifies link integrity (both sides of the edge must exist)
        # so all records must be read in a specific order.
        #

        # write the keys back in a specific order
        ordered_entities = [f"{e}.yaml" for e in model.dependency_order if f"{e}.yaml" in schema]
        # only entities that exist
        assert len(ordered_entities) > 0, f"No schemas in {data_dictionary_emitter.work_dir}/*.yaml"
        additional_entities = [e for e in schema if e not in ordered_entities]
        ordered_keys = ordered_entities + additional_entities
        ordered_schema = {k: schema[k] for k in ordered_keys}
        with open(schema_dump_ordered_path, "w") as fp:
            json.dump(ordered_schema, fp, sort_keys=False)

        # deprecate jq, do this in python
        # jq_script = ", ".join([f'"{e}.yaml": .["{e}.yaml"]' for e in ordered_entities + STATIC_ENTITIES])
        # cmd_line = f"jq '. | {{ {jq_script} }}' {schema_dump_path}  > {schema_dump_ordered_path}"
        # run_cmd(cmd_line)
        # to verify
        # jq '. | keys_unsorted'  dump-ordered.json

        # create pfb file with the schema
        logger.info("Creating pfb file with the schema")
        run_cmd(f"pfb from -o {file_path} dict {schema_dump_ordered_path}")

        # now we can add the data to the pfb

        for e in model.dependency_order:
            if os.path.isfile(f"{pfb_json_emitter.work_dir}/{e}.ndjson"):
                logger.info(f"adding {pfb_json_emitter.work_dir}/{e}.ndjson to {file_path}")
                cmd_line = f"pfb add -i {pfb_json_emitter.work_dir}/{e}.ndjson {file_path}"
                run_cmd(cmd_line)

        pfb_.set_results(inspect_pfb(file_path))

        # clean up
        os.remove(schema_dump_path)
        # os.remove(schema_dump_ordered_path)
        # done!


def inspect_pfb(file_name) -> InspectionResults:
    """Show details of the pfb."""
    # TODO - simplify
    results = InspectionResults()
    # raw records
    records = []
    # TODO - should this be a generator?
    with open(file_name, 'rb') as fo:
        records = [record for record in reader(fo)]

    # ensure loaded in the correct order

    def recursive_default_dict():
        """Recursive default dict."""
        return defaultdict(recursive_default_dict)

    seen_already = set()

    def log_first_occurrence(obj_):
        seen_already.add(obj_['name'])

    def check_links(obj_, graph_) -> Iterator[str]:
        """Make sure relations from obj exist in graph."""
        assert 'relations' in obj_
        for r in obj_['relations']:
            if not graph_[r['dst_name']][r['dst_id']]:
                yield f"{r['dst_name']}.{r['dst_id']} , referenced from {obj_['name']}.{obj_['id']} not found in Graph "

    graph = recursive_default_dict()

    for obj in records:
        log_first_occurrence(obj)
        graph[obj['name']][obj['id']] = obj
        for error in check_links(obj, graph):
            results.errors.append(error)

    # ensure no duplicates
    seen_already = set()

    def check_duplicates(obj_):
        if obj_['id'] in seen_already:
            yield f"Duplicate {obj_['name']}/{obj_['id']}"
        seen_already.add(obj_['id'])

    for obj in records:
        for error in check_duplicates(obj):
            results.errors.append(error)

    with_relations = [r for r in records if len(r['relations']) > 0]
    results.info.append(f"'Records with relationships': {len(with_relations)}")
    results.info.append(f"'Records': {len(records)}")

    assert len(records) > 1, "Should have more than just metadata"
    if len(with_relations) == 0:
        results.warnings.append("No records have relationships.")

    for obj in records:
        if obj['name'] not in results.counts:
            results.counts[obj['name']] = EntitySummary(name=obj['name'])
        summary = results.counts[obj['name']]
        summary.count += 1
        for r in obj['relations']:
            if r['dst_name'] not in summary.relationships:
                summary.relationships[r['dst_name']] = EdgeSummary(src=summary.name, dst=r['dst_name'])
            edge_summary = summary.relationships[r['dst_name']]
            edge_summary.count += 1

    return results
