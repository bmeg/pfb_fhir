## dbGap

### research study
wget 'https://dbgap-api.ncbi.nlm.nih.gov/fhir/x1/ResearchStudy?_id=phs002409&_include=ResearchStudy:sponsor' -O research_study.json

### subject and patient
wget 'https://dbgap-api.ncbi.nlm.nih.gov/fhir/x1/ResearchSubject?study=phs002409&_count=1000&_include=ResearchSubject:individual' -O research_subject_patient.json

### observations
wget 'https://dbgap-api.ncbi.nlm.nih.gov/fhir/x1/Observation?_security=phs002409-1&_count=1000' -O observation.json
