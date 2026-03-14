# Data Integration

## A. Gov.il registry integration

### Purpose
Validate OCR-extracted Israeli private/commercial vehicle plate numbers against the Ministry of Transport registry.

### Data source
- **Local CSV**: Full or partial MoT export; column `MISPAR_RECHEV` (or `mispar_rechev`)
- **API fallback**: [data.gov.il](https://data.gov.il/he/datasets/ministry_of_transport/private-and-commercial-vehicles/053cea08-09bc-40ec-8f7a-156f0677aff3) — CKAN `datastore_search` with `filters={"mispar_rechev": plate}` and `resource_id=053cea08-09bc-40ec-8f7a-156f0677aff3`

### Required behavior
- load CSV with pandas
- normalize MISPAR_RECHEV to digits only
- set normalized plate as index
- expose:
  - exists(plate) / plate_exists(plate)
  - get(plate) / lookup(plate)
- when plate not in local CSV and `data_gov_il_resource_id` set: query data.gov.il API; fail open if API unavailable

### Validation rule
A candidate OCR plate is valid only if:
- it has 7 or 8 digits
- it exists in the registry (local or data.gov.il)

### Recommended returned fields
- plate_number
- manufacturer
- model_name
- production_year
- raw_row

## B. Plate dimensions integration

Use the following reference table:

| plate_type     | width_cm | height_cm |
|----------------|----------|-----------|
| private_long   | 52.0     | 12.0      |
| private_rect   | 32.0     | 16.0      |
| motorcycle     | 17.0     | 16.0      |
| scooter        | 17.0     | 12.0      |

## C. Future optional data sources

- tyre specification from registry or joined dataset
- vehicle dimensions by model
- camera calibration profiles
- operator review overrides
