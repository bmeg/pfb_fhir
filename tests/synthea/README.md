    

## synthea
```commandline

mkdir tests/synthea



wget https://github.com/synthetichealth/synthea/releases/download/v3.0.0/synthea-with-dependencies.jar
wget 'https://raw.githubusercontent.com/ga4gh/cohort-rep-hackathon/main/synthea/config/synthea.properties' -O  tests/synthea/synthea.properties 
wget 'https://raw.githubusercontent.com/ga4gh/cohort-rep-hackathon/main/filter.py' -O tests/synthea/filter.py

rm -r  tests/fixtures/synthea/raw
rm -r tests/fixtures/synthea/filtered

mkdir -p tests/fixtures/synthea/raw
mkdir -p tests/fixtures/synthea/filtered


java -jar synthea-with-dependencies.jar \
    -p 100 \
    -c tests/synthea/synthea.properties \
    --exporter.baseDirectory "./tests/fixtures/synthea/raw/"

export GA4GH_DEMO_INPUT_DIR=./tests/fixtures/synthea/raw/fhir/
export GA4GH_DEMO_OUTPUT_DIR=./tests/fixtures/synthea/filtered/
python3 tests/synthea/filter.py

rm -r ./tests/fixtures/synthea/raw

```

custom_input_dir = os.getenv("GA4GH_DEMO_INPUT_DIR")
    input_dir = custom_input_dir if custom_input_dir else default_input_dir

    default_output_dir = os.path.join("output", "synthea", "filtered", "fhir")
    custom_output_dir = os.getenv("GA4GH_DEMO_OUTPUT_DIR")
