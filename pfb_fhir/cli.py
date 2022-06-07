"""Implements command line."""

import glob
import json
import os
from typing import Iterator
from pathlib import Path

import click
import logging
import networkx as nx

from click_loglevel import LogLevel
from importlib_metadata import distribution
import matplotlib.pyplot as plt


from pfb_fhir import NaturalOrderGroup, DEFAULT_OUTPUT_PATH, DEFAULT_CONFIG_PATH, initialize_model, run_cmd
from pfb_fhir.emitter import pfb
from pfb_fhir.model import TransformerContext
from pfb_fhir.observable import ObservableData
from pfb_fhir.emitter import inspect_pfb
from pfb_fhir.context_simplifier import ContextSimplifier

LOG_FORMAT = '%(asctime)s %(name)s %(levelname)-8s %(message)s'
logger = logging.getLogger(__name__)


@click.group(cls=NaturalOrderGroup)
@click.option("-l", "--log-level", type=LogLevel(), default=logging.INFO)
@click.option('--output_path', default=lambda: os.environ.get("PFB_FHIR_OUTPUT_PATH", DEFAULT_OUTPUT_PATH),
              help=f'Output path for working files and output. Read from PFB_FHIR_OUTPUT_PATH [default: {DEFAULT_OUTPUT_PATH}]',)
@click.option('--config_path', default=lambda: os.environ.get("PFB_FHIR_CONFIG_PATH", DEFAULT_CONFIG_PATH),
              help=f'Path to config file. Read from PFB_FHIR_CONFIG_PATH [default: {DEFAULT_CONFIG_PATH}]',)
@click.pass_context
def cli(ctx, log_level, output_path, config_path):
    """Render FHIR Data in PFB."""
    # ensure that ctx.obj exists and is a dict
    # set root logging
    logging.basicConfig(level=log_level, format=LOG_FORMAT)
    ctx.ensure_object(dict)
    ctx.obj['log_level'] = log_level
    if not os.path.isdir(output_path):
        logger.debug(f"{output_path} does not exist")
    ctx.obj['output_path'] = output_path
    if os.path.isfile(config_path):
        model = initialize_model(config_path)
        ctx.obj['model'] = model


@cli.command()
def version():
    """Print the version."""
    dist = distribution('pfb_fhir')
    print(dist.version)


@cli.command("transform")
@click.option('--input_path',  multiple=True, help='FHIR resources paths.')
@click.option('--pfb_path', help='Location to write PFB.')
@click.option('--simplify', is_flag=True, show_default=True, default=False, help="Remove FHIR scaffolding, make data frame friendly.")
@click.pass_context
def transform(ctx, input_path, pfb_path, simplify):
    """Transform FHIR resources from directory."""
    model = ctx.obj['model']
    if not model:
        logger.error("Please provide a config file.")
        return

    with pfb(ctx.obj['output_path'], pfb_path, model) as pfb_:
        for context in process_files(model, input_path, simplify=simplify):
            pfb_.emit(context)


@cli.command("inspect")
@click.option('--pfb_path', help='Location to read PFB.')
@click.pass_context
def inspect(ctx, pfb_path):
    """Inspect a PFB."""
    results = inspect_pfb(pfb_path)
    if len(results.errors) == 0:
        print('No errors.')
    else:
        print('ERRORS:')
        print(results.errors)

    if len(results.warnings) == 0:
        print('No warnings.')
    else:
        print('WARNINGS:')
        print(results.warnings)

    print('SUMMARY:')
    for summary in results.counts.values():
        print(summary.name, summary.count)
        for relationship in summary.relationships.values():
            print('    ', relationship.dst, relationship.count)


@cli.command("visualize")
@click.option('--pfb_path', help='Location to read PFB.')
@click.option('--layout', show_default=True, default='planar_layout', help='Position nodes algorithm. see https://networkx.org/documentation/stable/reference/drawing.html')
@click.pass_context
def visualize(ctx, pfb_path, layout):
    """Create a simple visualization."""
    results = inspect_pfb(pfb_path)
    graph = nx.MultiDiGraph()
    node_dict = {}
    edge_dict = {}

    for summary in results.counts.values():
        if summary.name == 'Metadata':
            continue
        graph.add_node(summary.name, count=summary.count)
        node_dict[summary.name] = f"{summary.name}\n{summary.count}"

    for summary in results.counts.values():
        for relationship in summary.relationships.values():
            graph.add_edge(summary.name, relationship.dst, count=relationship.count)
            edge_dict[(summary.name, relationship.dst)] = relationship.count

    if not (hasattr(nx, layout) and callable(getattr(nx, layout))):
        logger.error(f"Unknown layout {layout}. {[attr for attr in dir(nx) if 'layout' in attr]}")
        return

    layout_func = getattr(nx, layout)
    pos = layout_func(graph)
    fig, ax = plt.subplots(1, 1, figsize=(15, 15))
    nx.draw(graph, pos, ax=ax, with_labels=True, labels=node_dict, node_size=6000, node_color='w', alpha=0.9,
            edgecolors="black")
    nx.draw_networkx_edge_labels(
        graph, pos,
        edge_labels=edge_dict,
    )
    plt.title(pfb_path)
    plt.tight_layout()
    plt.axis('off')

    plt.savefig(pfb_path + ".png")
    logger.info(f"Wrote png to {pfb_path + '.png'}")


def _sniff(file_path) -> Iterator[dict]:
    """Sniff json or ndjson, yield row."""
    with open(file_path, "r") as fhir_resource_file:
        try:
            fhir_resources = json.load(fhir_resource_file)
            if isinstance(fhir_resources, dict) and 'entry' in fhir_resources:
                for entry in fhir_resources['entry']:
                    yield entry['resource']
                return

            if isinstance(fhir_resources, dict):
                yield fhir_resources
                return
            for fhir_resource in fhir_resources:
                yield fhir_resource
                return
        except json.decoder.JSONDecodeError:
            fhir_resource_file.seek(0)
            for line in fhir_resource_file:
                yield json.loads(line)


def process_files(model, input_paths, simplify=False) -> Iterator[TransformerContext]:
    """Set up context and stream files into the model."""
    # handle either file or path pattern
    if not isinstance(input_paths, (list, tuple, )):
        input_paths = [input_paths]
    for input_path in input_paths:
        if os.path.isfile(input_path):
            files = [input_path]
        else:
            files = glob.glob(input_path)
        assert len(files) > 0, f"Did not find any json files in {input_path}"
        # process the data
        for file in files:
            logger.info(file)
            for json_ in _sniff(file):
                # copy the model into the observer context
                context = TransformerContext(model=model, simplify=simplify)
                model.observe(
                    ObservableData(payload=json_)) \
                    .assert_observers() \
                    .notify_observers(context=context)
                if simplify:
                    context = ContextSimplifier.simplify(context)
                yield context


@cli.command()
@click.option('--format', 'format_', type=click.Choice(['json', 'yaml'], case_sensitive=False), default='json',
              show_default=True)
@click.pass_context
def config(ctx, format_):
    """Print the config."""
    if format_ == 'yaml':
        print(ctx.obj['model'].yaml())
    else:
        print(ctx.obj['model'].json())


@cli.group()
@click.option('--demo_path', default=lambda: os.environ.get("PFB_FHIR_DEMO_PATH", "./DEMO"),
              help='Path to download demo fixtures. Read from PFB_FHIR_DEMO_PATH [default:./DEMO]')
@click.option("--show", is_flag=True, show_default=True, default=False, help="Print script to stdout")
@click.option("--dry_run", is_flag=True, show_default=True, default=False, help="Don't execute the script.")
@click.pass_context
def demo(ctx, demo_path, show, dry_run):
    """Download Test data and create example PFB and figure."""
    ctx.obj['show'] = show
    ctx.obj['dry_run'] = dry_run
    ctx.obj['demo_path'] = demo_path

    ctx.obj['ncpi_path'] = Path(demo_path, 'ncpi')
    ctx.obj['anvil_path'] = Path(demo_path, 'anvil')
    ctx.obj['dbgap_path'] = Path(demo_path, 'dbgap')
    ctx.obj['synthea_path'] = Path(demo_path, 'synthea')
    ctx.obj['kf_path'] = Path(demo_path, 'kf')
    ctx.obj['gr_path'] = Path(demo_path, 'genomics-reporting')
    download_script = f"""
    # setup
    mkdir -p {demo_path}
    cd {demo_path}
    temp_file=$(mktemp)
    wget -qO- https://github.com/bmeg/pfb_fhir/releases/download/latest/fixtures.zip > $temp_file
    unzip $temp_file
    rm $temp_file
    cd .."""


    if show:
        print(download_script)

    if not dry_run:
        logger.info(f"Running demo script in {demo_path}")
        if not ctx.obj['ncpi_path'].exists():
            logger.info("Downloading example data.")
            run_cmd(download_script)
        else:
            logger.info("Data already downloaded.")


@demo.command()
@click.pass_context
def ncpi(ctx):
    """Read examples from ncpi ImplementationGuide."""
    show = ctx.obj['show']
    dry_run = ctx.obj['dry_run']
    ncpi_path = ctx.obj['ncpi_path']

    pfb_script = f"""
    # NCPI
    mkdir -p {ncpi_path}/output
    # PFB
    pfb_fhir \
      --config_path {ncpi_path}/config.yaml \
      --output_path {ncpi_path}/output \
      transform \
      --pfb_path {ncpi_path}/output/ncpi.pfb.avro \
      --input_path '{ncpi_path}/examples/DocumentReference-research-document-reference-example-1.json' \
      --input_path '{ncpi_path}/examples/Patient-patient-example-1.json' \
      --input_path '{ncpi_path}/examples/Patient-patient-example-3.json' \
      --input_path '{ncpi_path}/examples/ResearchSubject-research-subject-example-3.json' \
      --input_path '{ncpi_path}/examples/Observation-family-relationship-example-4.json' \
      --input_path '{ncpi_path}/examples/Task-task-example-2.json' \
      --input_path '{ncpi_path}/examples/ResearchStudy-research-study-example-1.json' \
      --input_path '{ncpi_path}/examples/Specimen-specimen-example-1.json' \
      --input_path '{ncpi_path}/examples/PractitionerRole-practitioner-role-example-1.json' \
      --input_path '{ncpi_path}/examples/Practitioner-practitioner-example-1.json' \
      --input_path '{ncpi_path}/examples/Organization-organization-example-1.json' \
      --input_path '{ncpi_path}/examples/Observation-research-study-example-1.json'
      """

    figure_script = f"""
    # visualize
    pfb_fhir visualize  --pfb_path {ncpi_path}/output/ncpi.pfb.avro
    """
    if show:
        print(pfb_script)
    if not dry_run:
        logger.info("Creating PFB.")
        run_cmd(pfb_script)
        logger.info("Creating figure.")
        run_cmd(figure_script)


@demo.command()
@click.pass_context
def anvil(ctx):
    """Read 1000G data from AnVIL."""
    show = ctx.obj['show']
    dry_run = ctx.obj['dry_run']
    anvil_path = ctx.obj['anvil_path']

    pfb_script = f"""
    # ANVIL
    mkdir -p {anvil_path}/output
    # PFB
    pfb_fhir \
      --config_path {anvil_path}/config.yaml \
      --output_path {anvil_path}/output \
      transform \
      --pfb_path {anvil_path}/output/anvil.pfb.avro \
      --input_path '{anvil_path}/fhir/public/Public/1000G-high-coverage-2019/public/*.ndjson' \
      --input_path '{anvil_path}/fhir/public/Public/1000G-high-coverage-2019/protected/*.ndjson' \
      """

    figure_script = f"""
    # visualize
    pfb_fhir visualize  --pfb_path {anvil_path}/output/anvil.pfb.avro
    """
    if show:
        print(pfb_script)
    if not dry_run:
        logger.info("Creating PFB.")
        run_cmd(pfb_script)
        logger.info("Creating figure.")
        run_cmd(figure_script)


@demo.command()
@click.pass_context
def dbgap(ctx):
    """Read open access data from dbGAP's FHIR service."""
    show = ctx.obj['show']
    dry_run = ctx.obj['dry_run']
    dbgap_path = ctx.obj['dbgap_path']

    pfb_script = f"""
    # dbgap
    mkdir -p {dbgap_path}/output
    # PFB
    pfb_fhir \
      --config_path {dbgap_path}/config.yaml \
      --output_path {dbgap_path}/output \
      transform \
      --pfb_path {dbgap_path}/output/dbgap.pfb.avro \
      --input_path '{dbgap_path}/examples/*.json'
      """

    figure_script = f"""
    # visualize
    pfb_fhir visualize  --pfb_path {dbgap_path}/output/dbgap.pfb.avro
    """
    if show:
        print(pfb_script)
    if not dry_run:
        logger.info("Creating PFB.")
        run_cmd(pfb_script)
        logger.info("Creating figure.")
        run_cmd(figure_script)


@demo.command()
@click.pass_context
def synthea(ctx):
    """Read synthetic clinical data created by synthea."""
    show = ctx.obj['show']
    dry_run = ctx.obj['dry_run']
    synthea_path = ctx.obj['synthea_path']

    pfb_script = f"""
    # synthea
    mkdir -p {synthea_path}/output
    # PFB
    pfb_fhir \
      --config_path {synthea_path}/config.yaml \
      --output_path {synthea_path}/output \
      transform \
      --pfb_path {synthea_path}/output/synthea.pfb.avro \
      --input_path '{synthea_path}/filtered/*.ndjson' \
      --input_path '{synthea_path}/filtered/*.json'
      """

    figure_script = f"""
    # visualize
    pfb_fhir visualize  --pfb_path {synthea_path}/output/synthea.pfb.avro
    """
    if show:
        print(pfb_script)
    if not dry_run:
        logger.info("Creating PFB.")
        run_cmd(pfb_script)
        logger.info("Creating figure.")
        run_cmd(figure_script)


@demo.command()
@click.pass_context
def kf(ctx):
    """Read research study hosted by kids first."""
    show = ctx.obj['show']
    dry_run = ctx.obj['dry_run']
    kf_path = ctx.obj['kf_path']

    pfb_script = f"""
    # KF
    mkdir -p {kf_path}/output
    # PFB
    pfb_fhir \
      --config_path {kf_path}/config.yaml \
      --output_path {kf_path}/output \
      transform \
      --pfb_path {kf_path}/output/kf.pfb.avro \
      --input_path '{kf_path}/examples/*.ndjson'
      """

    figure_script = f"""
    # visualize
    pfb_fhir visualize  --pfb_path {kf_path}/output/kf.pfb.avro
    """
    if show:
        print(pfb_script)
    if not dry_run:
        logger.info("Creating PFB.")
        run_cmd(pfb_script)
        logger.info("Creating figure.")
        run_cmd(figure_script)


@demo.command()
@click.pass_context
def genomic_reporting(ctx):
    """Read oncology example from ImplementationGuide."""
    show = ctx.obj['show']
    dry_run = ctx.obj['dry_run']
    gr_path = ctx.obj['gr_path']

    pfb_script = f"""
    # GR
    mkdir -p {gr_path}/output
    # PFB
    pfb_fhir \
      --config_path {gr_path}/config.yaml \
      --output_path {gr_path}/output \
      transform \
      --pfb_path {gr_path}/output/genomics-reporting.pfb.avro \
      --input_path '{gr_path}/examples/Bundle-bundle-oncologyexamples-r4.normalized.json'
      """

    figure_script = f"""
    # visualize
    pfb_fhir visualize  --pfb_path {gr_path}/output/genomics-reporting.pfb.avro
    """
    if show:
        print(pfb_script)
    if not dry_run:
        logger.info("Creating PFB.")
        run_cmd(pfb_script)
        logger.info("Creating figure.")
        run_cmd(figure_script)
