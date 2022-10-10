"""Load extensions into sqlite"""
import shutil
import sqlite3
import json
import logging
from dataclasses import dataclass

import requests
from fhirclient.models.structuredefinition import StructureDefinition
from fhirclient.models.elementdefinition import ElementDefinition

import pkg_resources
import os
import yaml

from pathlib import Path

from pfb_fhir import run_cmd

logger = logging.getLogger("extensions")
# logger.setLevel(logging.INFO)

DATABASE_FILE_NAME = "extensions.sqlite"
EXTENSION_DIR_NAME = "package/"
EXTENSION_BUNDLE_NAME = "extension-definitions.json"

_create_extensions_table_sql = """
-- extensions table
CREATE TABLE IF NOT EXISTS extensions (
    url text PRIMARY KEY,
    type text NOT NULL,
    id text NOT NULL,
    resource json
);
"""


def _get_config():
    """Load our default configuration."""
    resource_package = __name__
    path = 'extensions.yaml'  # Do not use os.path.join()
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
    c.execute("SELECT count(*) as \"resource_count\" FROM extensions")
    data = c.fetchone()
    return data['resource_count']


def _load_dict(database_path, resource):
    """Save dict to db."""
    conn = _create_connection(database_path)
    c = conn.cursor()
    extension = resource
    id_ = extension['id']
    url = extension['url']
    type_ = resource['resourceType']
    c.execute("insert into extensions values (?, ?, ?, ?)", [url, type_, id_, json.dumps(extension)])
    conn.commit()


def _load_bundle(database_path, json_path):
    """Load the json into a sqlite table"""

    conn = _create_connection(database_path)

    with open(json_path, "r") as input_stream:
        collection = json.load(input_stream)
        assert collection['type'] == 'collection'
    resource_count = 0
    for structure_definition in collection['entry']:
        resource = structure_definition['resource']
        type_ = resource['resourceType']
        c = conn.cursor()
        if type_ == 'StructureDefinition':
            extension = resource
            id_ = extension['id']
            url = extension['url']
            # logger.debug(f"{type_}, {id_}, {full_url}, {url}")
            c.execute("insert into extensions values (?, ?, ?, ?)", [url, type_, id_, json.dumps(extension)])
            resource_count += 1
        conn.commit()

    # no longer need json
    os.unlink(json_path)
    return resource_count


def _load_dir(database_path, extension_dir_name):
    """Load the json into a sqlite table"""

    extension_path = Path(extension_dir_name)

    conn = _create_connection(database_path)
    _create_table(conn, _create_extensions_table_sql)

    resource_count = 0
    for file in extension_path.glob("StructureDefinition*.json"):
        with open(file, "r") as input_stream:
            extension = json.load(input_stream)
            if extension['type'] == 'Extension':
                # expect [CodeSystem, ValueSet] as types
                type_ = extension['type']
                id_ = extension['id']
                url = extension['url']
                # logger.debug(f"{type_}, {id_}, {full_url}, {url}")
                c = conn.cursor()
                c.execute("insert into extensions values (?, ?, ?, ?)", [url, type_, id_, json.dumps(extension)])
                resource_count += 1
                conn.commit()

    # no longer need json
    shutil.rmtree(extension_dir_name)
    return resource_count


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
    extension = url.split('.')[-1]
    cmds = {
        'tgz': f'''
                temp_file=$(mktemp)
                wget -qO- {url} > $temp_file
                tar -zxvf $temp_file -C  {cache_path}
                rm $temp_file
                ''',
        'zip': f'''
                temp_file=$(mktemp)
                wget -qO- {url} > $temp_file
                unzip -o $temp_file extension-definitions.json -d {cache_path}
                rm $temp_file
                '''
    }

    run_cmd(cmds[extension])


@dataclass
class ExtensionElement:
    slice: ElementDefinition
    type: ElementDefinition


class Extension(StructureDefinition):
    """Get details from StructureDefinition."""

    def __init__(self, *args, **kwargs):
        """Passthrough."""
        super().__init__(*args, **kwargs)

    def extension_type(self):
        """value[x] type. for extensions without elements"""
        return next(iter([e for e in self.snapshot.element if '.value' in e.id]), None)

    def elements(self):
        """Find slices and their definitions."""
        # There are two types of extensions,
        # ones with multiple properties ...
        for slice_ in [e for e in self.snapshot.element if e.sliceName]:
            yield ExtensionElement(slice=slice_, type=next(iter([e for e in self.snapshot.element if f'{slice_.sliceName}.value' in e.id]), None))
        # ones with single properties ... handled by caller


class Extensions(object):
    """Lookup FHIR ValueSet and Codeset from sqlite."""

    def __init__(self, database_file_name=DATABASE_FILE_NAME, extension_dir_name=EXTENSION_DIR_NAME,
                 extension_bundle_name=EXTENSION_BUNDLE_NAME) -> None:
        """Load table."""
        cache_path = Path(os.environ.get("PFB_FHIR_CACHE_PATH", 'cache'))
        cache_path.mkdir(exist_ok=True)

        config = _get_config()

        self.database_file_name = Path(cache_path, database_file_name)
        self.extension_dir_name = Path(cache_path, extension_dir_name)
        self.extension_bundle_name = Path(cache_path, extension_bundle_name)
        self.resource_count = 0
        if not os.path.isfile(self.database_file_name):

            if os.path.isfile(self.database_file_name):
                logger.debug(f"Deleting existing db file {self.database_file_name}")
                os.unlink(self.database_file_name)

            if not self.extension_dir_name.is_dir():
                for base in config['base']:
                    _download_base(str(cache_path), base)

            assert self.extension_dir_name.is_dir(), f"{self.extension_dir_name} does not exist?"
            logger.error(f"Loading from {self.extension_dir_name} into {self.extension_dir_name}")
            self.resource_count = _load_dir(self.database_file_name, self.extension_dir_name)
            logger.error(f"Loaded {self.resource_count} ")

            logger.error(f"Loading from {self.extension_dir_name} into {self.database_file_name}")
            self.resource_count = _load_bundle(self.database_file_name, self.extension_bundle_name)
            logger.error(f"Loaded {self.resource_count} ")

        else:
            self.resource_count = _resource_count(self.database_file_name)

    def resource(self, url):
        """Lookup extension, return as StructureDefinition."""
        url = url.split('|')[0]
        logger.debug(f"Looking up {url}")
        conn = _create_connection(self.database_file_name)
        conn.row_factory = _dict_factory

        c = conn.cursor()
        c.execute("SELECT * FROM extensions WHERE url=?;", [url])
        data = c.fetchone()
        if data:
            data['resource'] = json.loads(data['resource'])
            return Extension(data['resource'])

        # look up on line
        response_text = None
        try:
            logger.warning(f"No find extension for {url}")
            response = requests.get(url)
            response_text = response.text
            response.raise_for_status()
            data = {'resource': response.json()}
            _load_dict(self.database_file_name, response.json())
            logger.warning(("miss saved", url))
            return Extension(response.json())
        except Exception as e:
            logger.warning(("no find", url, response_text))
            return None
