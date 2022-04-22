"""Load valuesets into sqlite"""

import sqlite3
import json
import logging
from typing import List

import pkg_resources
import requests
import os
import yaml

from pathlib import Path

from pfb_fhir import run_cmd

logger = logging.getLogger("valuesets")
# logger.setLevel(logging.INFO)

DATABASE_FILE_NAME = "valuesets.sqlite"
VALUESET_FILE_NAME = "valuesets.json"

_create_valuesets_table_sql = """
-- projects table
CREATE TABLE IF NOT EXISTS valuesets (
    fullUrl text PRIMARY KEY,
    type text NOT NULL,
    id text NOT NULL,
    url text NOT NULL,
    resource json
);
"""


def _get_config():
    """Load our default configuration."""
    resource_package = __name__
    path = 'terminology.yaml'  # Do not use os.path.join()
    config_file = pkg_resources.resource_stream(resource_package, path)
    return yaml.load(config_file, Loader=yaml.SafeLoader)


def _dict_factory(cursor, row):
    """Return dicts from db"""
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


def _resource_count(database_path):
    """Load the json into a sqlite table"""

    conn = _create_connection(database_path)
    conn.row_factory = _dict_factory

    c = conn.cursor()
    c.execute("SELECT count(*) as \"resource_count\" FROM valuesets")
    data = c.fetchone()
    return data['resource_count']


def _load(database_path, json_path):
    """Load the json into a sqlite table"""

    conn = _create_connection(database_path)
    _create_table(conn, _create_valuesets_table_sql)

    with open(json_path, "r") as input_stream:
        valuesets = json.load(input_stream)

    resource_count = 0
    # expect [CodeSystem, ValueSet] as types
    entries = None
    if 'Bundle' in valuesets:
        entries = valuesets['Bundle']['entry']
    else:
        entries = valuesets['entry']

    for entry in entries:
        resource = entry['resource']
        type_ = resource['resourceType']
        id_ = resource['id']
        full_url = entry['fullUrl']
        url = resource['url']
        # logger.debug(f"{type_}, {id_}, {full_url}, {url}")
        c = conn.cursor()
        c.execute("insert into valuesets values (?, ?, ?, ?, ?)", [full_url, type_, id_, url, json.dumps(resource)])
        resource_count += 1
        conn.commit()

    # no longer need json
    os.unlink(json_path)
    return resource_count


def _load_curated(database_path, valueset_config):
    """Load a manually curated list of valuesets into db."""
    conn = _create_connection(database_path)
    c = conn.cursor()

    logger.debug(f"Loading {valueset_config['valueset']}")
    fullUrl = valueset_config['fullUrl']
    valueset = requests.get(valueset_config['valueset']).json()
    type_ = valueset['resourceType']
    id_ = valueset['id']
    url = valueset['url']

    # wrangle to match shape of codesystems in valuesets.json
    codesystem_fullUrl = valueset['compose']['include']
    if isinstance(codesystem_fullUrl, list):
        codesystem_fullUrl = codesystem_fullUrl[0]['system']
    # logger.debug(f"Replacing old include: {valueset['compose']['include']}")
    new_include = {k: valueset['compose']['include'][0][k] for k in valueset['compose']['include'][0]}
    new_include['system'] = {'@value': codesystem_fullUrl}
    valueset['compose']['include'] = [new_include]

    # logger.debug(f"{type_}, {id_}, {fullUrl}, {url} {codesystem_fullUrl}")
    c.execute("replace into valuesets values (?, ?, ?, ?, ?)", [fullUrl, type_, id_, url, json.dumps(valueset)])
    conn.commit()

    # logger.debug(f"Loading {valueset_config['codesystem']}")
    codesystem = requests.get(valueset_config['codesystem']).json()
    type_ = codesystem['resourceType']
    id_ = codesystem['id']
    fullUrl = codesystem_fullUrl
    url = codesystem['url']

    # logger.debug(f"{type_}, {id_}, {fullUrl}, {url}")
    c.execute("replace into valuesets values (?, ?, ?, ?, ?)", [fullUrl, type_, id_, url, json.dumps(codesystem)])
    conn.commit()


def _create_connection(db_file):
    """ create a database connection to the SQLite database
        specified by db_file
    :param db_file: database file
    :return: Connection object or None
    """
    conn = None
    conn = sqlite3.connect(db_file)
    return conn


def _create_table(conn, create_table_sql):
    """ create a table from the create_table_sql statement
    :param conn: Connection object
    :param create_table_sql: a CREATE TABLE statement
    :return:
    """
    c = conn.cursor()
    c.execute(create_table_sql)


def _download_base(cache_path, url):
    """Download and unzip base terminology."""
    cmd = f'''
    temp_file=$(mktemp)
    wget -qO- {url} > $temp_file
    unzip $temp_file valuesets.json -d {cache_path}
    rm $temp_file
    '''

    run_cmd(cmd)


class ValueSets(object):
    """Lookup FHIR ValueSet and Codeset from sqlite."""

    def __init__(self, database_file_name=DATABASE_FILE_NAME, valueset_file_name=VALUESET_FILE_NAME) -> None:
        """Load table."""
        cache_path = Path(os.environ.get("PFB_FHIR_CACHE_PATH", 'cache'))
        cache_path.mkdir(exist_ok=True)

        config = _get_config()

        self.database_file_name = Path(cache_path, database_file_name)
        self.valueset_file_name = Path(cache_path, valueset_file_name)
        self.resource_count = 0
        if not os.path.isfile(self.database_file_name):

            if os.path.isfile(self.database_file_name):
                logger.debug(f"Deleting existing db file {self.database_file_name}")
                os.unlink(self.database_file_name)

            if not self.valueset_file_name.is_file():
                _download_base(str(cache_path), config['base'])

            assert self.valueset_file_name.is_file()
            logger.debug(f"Loading from {self.valueset_file_name} into {self.database_file_name}")
            self.resource_count = _load(self.database_file_name, self.valueset_file_name)

            for valueset in config['valuesets']:
                _load_curated(self.database_file_name, valueset)
        else:
            self.resource_count = _resource_count(self.database_file_name)

    def resource(self, fullUrl):
        """Lookup valueset, fetch referenced includes."""
        fullUrl = fullUrl.split('|')[0]
        logger.debug(f"Looking up {fullUrl}")
        conn = _create_connection(self.database_file_name)
        conn.row_factory = _dict_factory

        c = conn.cursor()
        c.execute("SELECT * FROM valuesets WHERE fullUrl=?;", [fullUrl])
        data = c.fetchone()
        if not data:
            logger.warning(f"No find valuset for {fullUrl}")
            return None
        data['resource'] = json.loads(data['resource'])

        includes = data['resource']['compose']['include']
        if not isinstance(includes, list):
            includes = [includes]

        accumulated_concepts = []

        for include in includes:
            if 'concept' not in include:
                if 'system' in include:
                    codesystem_url = include['system']
                else:
                    codesystem_url = include['valueSet']
                    if isinstance(codesystem_url, list):
                        if len(codesystem_url) > 1:
                            logger.warning(f"{fullUrl} has more than one valueset, {include}. processing {codesystem_url[0]}")
                        codesystem_url = codesystem_url[0]
                if isinstance(codesystem_url, dict):
                    codesystem_url = codesystem_url['@value']
                assert isinstance(codesystem_url, str), f"{codesystem_url}  {fullUrl}  {include}"
                included_data = c.execute("SELECT * FROM valuesets WHERE url=?;", [codesystem_url, ]).fetchone()
                if not included_data:
                    logger.debug(f"No codeset for {codesystem_url}")
                    continue
                included_data['resource'] = json.loads(included_data['resource'])
                included_concepts = included_data['resource']['concept']
                # some includes have codes for all fields in a resource, so we need to filter them
                if 'filter' in include:
                    filter = include['filter']
                    if not isinstance(filter, list):
                        filter = [filter]
                    filter = next(iter(filter), None)
                    filter_value = filter['value']
                    filter_op = filter['op']
                    if filter_op not in ['is-a', 'is-not-a', 'descendent-of']:
                        logger.error(f"UNSUPPORTED FILTER OP {fullUrl} {filter_op}")
                    filtered_concepts = []
                    for concept in included_concepts:
                        if 'property' in concept and filter_op == 'is-a':
                            is_subsumed_by = next(iter([p for p in concept['property'] if p['code'] == 'subsumedBy' and p['valueCode'] == filter_value]), None)
                            if is_subsumed_by:
                                filtered_concepts.append(concept)
                                # we need to drill down at least one level
                                parent_code = concept['code']
                                self._drill_down(filtered_concepts, included_concepts, parent_code)
                                continue
                        if concept['code'] == filter_value and (filter_op == 'is-a' or filter_op == 'descendent-of'):
                            if 'concept' in concept:
                                filtered_concepts = concept['concept']
                                continue
                        if concept['code'] != filter_value and filter_op == 'is-not-a':
                            filtered_concepts.append(concept)
                    if len(filtered_concepts) > 0:
                        included_concepts = filtered_concepts
                accumulated_concepts.extend(included_concepts)
            else:
                accumulated_concepts.extend(include['concept'])

        data['resource']['concept'] = accumulated_concepts

        return data['resource']

    def _drill_down(self, filtered_concepts, included_concepts, parent_code):
        """Find all subsumed children, add to filtered concepts"""
        for child_concept in included_concepts:
            is_subsumed_by_parent = next(iter([p for p in child_concept['property'] if
                                               p['code'] == 'subsumedBy' and p[
                                                   'valueCode'] == parent_code]), None)
            if is_subsumed_by_parent:
                filtered_concepts.append(child_concept)
                # recurse
                self._drill_down(filtered_concepts, included_concepts, child_concept['code'])

    def codes(self, fullUrl) -> List[str]:
        """Get all codes for valueset."""
        resource = self.resource(fullUrl)
        if resource:
            codes = [c['code'] for c in resource['concept']]
            for c in resource['concept']:
                if 'concept' in c:
                    for concept in c['concept']:
                        codes.append(concept['code'])
            # exceptions for
            if fullUrl == 'http://hl7.org/fhir/ValueSet/condition-code' and len(codes) == 1:
                return None
            return codes
        return None
