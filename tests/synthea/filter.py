"""Filter Synthea dataset to create a filtered dataset of all asthma patients, plus 100 non-asthma patients."""

import os
import json


def copy_json_file(filename_start, output_filename, input_dir, output_dir):
    """Copy file from input to output."""
    input_file = [a for a in os.listdir(input_dir) if a.startswith(filename_start)][0]
    open(os.path.join(output_dir, output_filename + ".json"), "w").write(
        open(os.path.join(input_dir, input_file), "r").read()
    )


def output_filtered_records(fhir_model, input_dir, output_dir):
    """Write as ndjson."""
    filtered_records = []
    for record in open(os.path.join(input_dir, fhir_model + ".ndjson")):
        record_json = json.loads(record)
        # for some reason synthea uses a non-standard code
        if fhir_model == 'Encounter':
            if record_json['status'] == 'finished':
                record_json['status'] = 'completed'
        if fhir_model == 'Patient':
            if "communication" in record_json:
                for communication in record_json["communication"]:
                    if "language" in communication:
                        for coding in communication["language"]["coding"]:
                            if coding['code'] == "vi":
                                coding['code'] = "en-US"
                                coding['display'] = "English"
        #     for identifier in record_json['identifier']:
        #         if 'type' not in identifier:
        #             continue
        #         for coding in identifier['type']['coding']:
        #             if coding['code'] == 'SS':
        #                 coding['code'] = 'SB'
        record = json.dumps(record_json, separators=(',', ':')) + "\n"
        filtered_records.append(record)
    open(os.path.join(output_dir, fhir_model + ".ndjson"), "w").write("".join(filtered_records))


def main():
    """PARSE PROGRAM INPUTS."""
    ##################################################
    # PARSE PROGRAM INPUTS
    ##################################################
    default_input_dir = os.path.join("output", "synthea", "raw", "fhir")
    custom_input_dir = os.getenv("GA4GH_DEMO_INPUT_DIR")
    input_dir = custom_input_dir if custom_input_dir else default_input_dir

    default_output_dir = os.path.join("output", "synthea", "filtered", "fhir")
    custom_output_dir = os.getenv("GA4GH_DEMO_OUTPUT_DIR")
    output_dir = custom_output_dir if custom_output_dir else default_output_dir

    ##################################################
    # OUTPUT
    ##################################################

    # copy all practitioner and hospital JSON
    copy_json_file("practitionerInformation", "PractitionerInformation", input_dir, output_dir)
    copy_json_file("hospitalInformation", "HospitalInformation", input_dir, output_dir)

    output_filtered_records("Patient", input_dir, output_dir)
    output_filtered_records("Condition", input_dir, output_dir)
    output_filtered_records("Encounter", input_dir, output_dir)
    output_filtered_records("Immunization", input_dir, output_dir)
    output_filtered_records("Observation", input_dir, output_dir)
    output_filtered_records("DiagnosticReport", input_dir, output_dir)
    output_filtered_records("DocumentReference", input_dir, output_dir)
    output_filtered_records("Procedure", input_dir, output_dir)


if __name__ == "__main__":
    main()
