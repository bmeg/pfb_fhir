genomics-reporting

## Data source

### copy from IG build
# from tests/fixtures/genomics-reporting 
mkdir examples/
curl http://hl7.org/fhir/uv/genomics-reporting/examples.json.zip --output examples.json.zip 2> /dev/null 
unzip examples.json.zip Bundle-bundle-oncologyexamples-r4.json -d examples/
rm examples.json.zip

# SNAFUs
* This IG's examples contain bundles of resources.  
* The unusual thing is that the resources contained in the bundle have references that resolve to fullUrl of the bundle entry, not the `id` of the resource? 

