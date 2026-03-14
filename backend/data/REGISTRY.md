# Vehicle Registry & Plate Validation

Plates are validated against the **Ministry of Transport registry** (private and commercial vehicles).

- **Dataset:** [data.gov.il - מספרי רישוי של כלי רכב פרטיים ומסחריים](https://data.gov.il/he/datasets/ministry_of_transport/private-and-commercial-vehicles/053cea08-09bc-40ec-8f7a-156f0677aff3)

## Options

### 1. Local CSV (recommended for production)

Download the full dataset from data.gov.il and save as CSV. Configure:

```env
VEHICLE_REGISTRY_FILE=data/registry.csv
```

**Column mapping:** The registry expects a plate column. Auto-detected names:
`MISPAR_RECHEV`, `mispar_rechev`, `plate_number`, `plate`

### 2. data.gov.il API (fallback when plate not in local CSV)

When `data_gov_il_resource_id` is set, plates not found in the local CSV are checked via the CKAN `datastore_search` API.

```env
VALIDATE_PLATE_IN_REGISTRY=true
DATA_GOV_IL_RESOURCE_ID=053cea08-09bc-40ec-8f7a-156f0677aff3
```

**Note:** The data.gov.il API may return 403 in some environments. Use a local CSV for reliable validation.

### 3. Disable validation

```env
VALIDATE_PLATE_IN_REGISTRY=false
```

## Sample registry (development)

`registry_sample.csv` contains 3 sample plates for development. Replace with the full MoT export for production.
