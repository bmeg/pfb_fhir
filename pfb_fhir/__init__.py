"""Useful entities."""
import subprocess
from collections import OrderedDict

import click
import yaml

from pfb_fhir.handlers import handler_factory
from pfb_fhir.model import Model
import logging
import cProfile, pstats

DEFAULT_OUTPUT_PATH = './DATA'
DEFAULT_CONFIG_PATH = './config.yaml'

logger = logging.getLogger(__name__)

PROFILER = None


class NaturalOrderGroup(click.Group):
    """Display CLick help in the order it was declared."""

    def __init__(self, name=None, commands=None, **attrs):
        """Override."""
        super(NaturalOrderGroup, self).__init__(
            name=name, commands=None, **attrs)
        if commands is None:
            commands = OrderedDict()
        elif not isinstance(commands, OrderedDict):
            commands = OrderedDict(commands)
        self.commands = commands

    def list_commands(self, ctx):
        """Satisfy click interface."""
        return self.commands.keys()


def initialize_model(config_path):
    """Build the model and it's handlers."""
    model_ = Model.parse_file(config_path)

    model_.dependency_order = list(yaml.safe_load(open(config_path))['entities'])
    # fetch child fhir profiles
    model_.fetch_profiles()
    [handler_factory(entity) for entity in model_.entities.values()]
    return model_


def run_cmd(command_line):
    """Run a command line, return stdout."""
    try:
        logger.debug(command_line)
        return subprocess.check_output(command_line, shell=True).decode("utf-8").rstrip()
    except Exception as exc:
        logger.error(exc)
        raise exc


def start_profiler():
    """Start the profiler."""
    global PROFILER
    PROFILER = cProfile.Profile()
    PROFILER.enable()


def stop_profiler():
    """"""
    PROFILER.disable()
    # Export profiler output to file
    stats = pstats.Stats(PROFILER)
    stats.dump_stats('program.prof')
    logger.info("Wrote profile to 'program.prof'.  Review with `snakeviz program.prof`")
