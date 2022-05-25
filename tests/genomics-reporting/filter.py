import json
from jsonpath_ng import parse
import click

INPUT_PATH_DEFAULT = 'tests/fixtures/genomics-reporting/examples/Bundle-bundle-oncologyexamples-r4.json'
OUTPUT_PATH_DEFAULT = 'tests/fixtures/genomics-reporting/examples/Bundle-bundle-oncologyexamples-r4.normalized.json'


@click.command()
@click.option('--input_path', default=INPUT_PATH_DEFAULT, help='path to json bundle')
@click.option('--output_path', default=OUTPUT_PATH_DEFAULT, help='path to json bundle')
def normalize_bundle(input_path, output_path):
    """Replace "fullPath urn:uuid:" style references with "resourceType/id" form.

    e.g.
    urn:uuid:a48256f8-db37-44e0-a0f6-d7af16c7c9ef -> Practitioner/Inline-Instance-for-oncologyexamples-r4-2
    """
    with open(input_path) as fp:
        bundle = json.load(fp)

    full_url_reference_mapping = {}
    for entry in bundle['entry']:
        full_url = entry['fullUrl']
        reference = f"{entry['resource']['resourceType']}/{entry['resource']['id']}"
        full_url_reference_mapping[full_url] = reference

    # match any reference
    any_reference = parse('$..reference')
    for reference in any_reference.find(bundle):
        if reference.value in full_url_reference_mapping:
            # if we have a mapping, change it to {resourceType/id} form
            reference.full_path.update(bundle, full_url_reference_mapping[reference.value])

    reference_values = [reference.value for reference in any_reference.find(bundle) if 'urn:uuid:' in reference.value]
    assert len(reference_values) == 0, "Should have replaced all urn style references."

    # match any contained https://build.fhir.org/domainresource-definitions.html#DomainResource.contained
    # move to bundle entry
    contained_resources = []
    for entry in bundle['entry']:
        if 'contained' in entry['resource']:
            contained_resources.extend(entry['resource']['contained'])
    assert len(contained_resources) > 0

    for entry in bundle['entry']:
        if 'contained' in entry['resource']:
            del entry['resource']['contained']

    resources_with_contained_values = [entry['resource']['id'] for entry in bundle['entry'] if 'contained' in entry['resource']]
    assert len(resources_with_contained_values) == 0, "Should have replaced all contained resources."

    # retrofit references
    contained_resource_mapping = {}
    for contained_resource in contained_resources:
        bundle['entry'].append({'resource': contained_resource})
        contained_resource_mapping[f"#{contained_resource['id']}"] = f"{contained_resource['resourceType']}/{contained_resource['id']}"

    any_reference = parse('$..reference')
    for reference in any_reference.find(bundle):
        if reference.value in contained_resource_mapping:
            # if we have a mapping, change it to {resourceType/id} form
            reference.full_path.update(bundle, contained_resource_mapping[reference.value])

    reference_values = [reference.value for reference in any_reference.find(bundle) if reference.value in contained_resource_mapping]
    assert len(reference_values) == 0, "Should have replaced all contained style references."

    with open(output_path, "w") as fp:
        json.dump(bundle, fp)

    print(f"Wrote normalized {output_path}")


if __name__ == '__main__':
    normalize_bundle()