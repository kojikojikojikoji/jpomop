"""OMOP concept IDs used by the ETL.

Checked on 2026-10-13 against the public OHDSI WebAPI
(https://api.ohdsi.org/WebAPI/vocabulary/concept/<id>): all are standard
and valid.
"""

MALE = 8507  # Gender "MALE"
FEMALE = 8532  # Gender "FEMALE"
INPATIENT_VISIT = 9201  # Visit "Inpatient Visit"
TYPE_CLAIM = 32810  # Type Concept "Claim"
UNKNOWN = 0

GENDER = {"1": MALE, "2": FEMALE}

# Form 1 diagnosis fields to Condition Status concepts. This is an
# interpretation of the DPC fields, not a published mapping.
CONDITION_STATUS = {
    "dx_main": 32902,  # Primary diagnosis (主傷病名)
    "dx_trigger": 32901,  # Primary admission diagnosis (入院の契機となった傷病名)
    "dx_resource1": 32908,  # Secondary diagnosis (医療資源を最も投入した傷病名)
    "dx_resource2": 32908,  # Secondary diagnosis (医療資源を2番目に投入した傷病名)
    "dx_comorbid": 32907,  # Secondary admission diagnosis (入院時併存症)
    "dx_complication": 32909,  # Secondary discharge diagnosis (入院後発症疾患)
}
