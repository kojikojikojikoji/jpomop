"""Arrow schemas for the CDM v5.4 tables jpomop writes.

Column order follows the CDM v5.4 DDL.
"""

import pyarrow as pa

i64, d, ts, s = pa.int64(), pa.date32(), pa.timestamp("s"), pa.string()

PERSON = pa.schema([
    ("person_id", i64), ("gender_concept_id", i64), ("year_of_birth", i64),
    ("month_of_birth", i64), ("day_of_birth", i64), ("birth_datetime", ts),
    ("race_concept_id", i64), ("ethnicity_concept_id", i64), ("location_id", i64),
    ("provider_id", i64), ("care_site_id", i64), ("person_source_value", s),
    ("gender_source_value", s), ("gender_source_concept_id", i64), ("race_source_value", s),
    ("race_source_concept_id", i64), ("ethnicity_source_value", s),
    ("ethnicity_source_concept_id", i64),
])

OBSERVATION_PERIOD = pa.schema([
    ("observation_period_id", i64), ("person_id", i64), ("observation_period_start_date", d),
    ("observation_period_end_date", d), ("period_type_concept_id", i64),
])

VISIT_OCCURRENCE = pa.schema([
    ("visit_occurrence_id", i64), ("person_id", i64), ("visit_concept_id", i64),
    ("visit_start_date", d), ("visit_start_datetime", ts), ("visit_end_date", d),
    ("visit_end_datetime", ts), ("visit_type_concept_id", i64), ("provider_id", i64),
    ("care_site_id", i64), ("visit_source_value", s), ("visit_source_concept_id", i64),
    ("admitted_from_concept_id", i64), ("admitted_from_source_value", s),
    ("discharged_to_concept_id", i64), ("discharged_to_source_value", s),
    ("preceding_visit_occurrence_id", i64),
])

VISIT_DETAIL = pa.schema([
    ("visit_detail_id", i64), ("person_id", i64), ("visit_detail_concept_id", i64),
    ("visit_detail_start_date", d), ("visit_detail_start_datetime", ts),
    ("visit_detail_end_date", d), ("visit_detail_end_datetime", ts),
    ("visit_detail_type_concept_id", i64), ("provider_id", i64), ("care_site_id", i64),
    ("visit_detail_source_value", s), ("visit_detail_source_concept_id", i64),
    ("admitted_from_concept_id", i64), ("admitted_from_source_value", s),
    ("discharged_to_source_value", s), ("discharged_to_concept_id", i64),
    ("preceding_visit_detail_id", i64), ("parent_visit_detail_id", i64),
    ("visit_occurrence_id", i64),
])

DEATH = pa.schema([
    ("person_id", i64), ("death_date", d), ("death_datetime", ts),
    ("death_type_concept_id", i64), ("cause_concept_id", i64), ("cause_source_value", s),
    ("cause_source_concept_id", i64),
])

CONDITION_OCCURRENCE = pa.schema([
    ("condition_occurrence_id", i64), ("person_id", i64), ("condition_concept_id", i64),
    ("condition_start_date", d), ("condition_start_datetime", ts), ("condition_end_date", d),
    ("condition_end_datetime", ts), ("condition_type_concept_id", i64),
    ("condition_status_concept_id", i64), ("stop_reason", s), ("provider_id", i64),
    ("visit_occurrence_id", i64), ("visit_detail_id", i64), ("condition_source_value", s),
    ("condition_source_concept_id", i64), ("condition_status_source_value", s),
])

DRUG_EXPOSURE = pa.schema([
    ("drug_exposure_id", i64), ("person_id", i64), ("drug_concept_id", i64),
    ("drug_exposure_start_date", d), ("drug_exposure_start_datetime", ts),
    ("drug_exposure_end_date", d), ("drug_exposure_end_datetime", ts),
    ("verbatim_end_date", d), ("drug_type_concept_id", i64), ("stop_reason", s),
    ("refills", i64), ("quantity", pa.float64()), ("days_supply", i64), ("sig", s),
    ("route_concept_id", i64), ("lot_number", s), ("provider_id", i64),
    ("visit_occurrence_id", i64), ("visit_detail_id", i64), ("drug_source_value", s),
    ("drug_source_concept_id", i64), ("route_source_value", s), ("dose_unit_source_value", s),
])

PROCEDURE_OCCURRENCE = pa.schema([
    ("procedure_occurrence_id", i64), ("person_id", i64), ("procedure_concept_id", i64),
    ("procedure_date", d), ("procedure_datetime", ts), ("procedure_end_date", d),
    ("procedure_end_datetime", ts), ("procedure_type_concept_id", i64),
    ("modifier_concept_id", i64), ("quantity", i64), ("provider_id", i64),
    ("visit_occurrence_id", i64), ("visit_detail_id", i64), ("procedure_source_value", s),
    ("procedure_source_concept_id", i64), ("modifier_source_value", s),
])
