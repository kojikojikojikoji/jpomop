"""OMOP concept IDs used by the ETL.

Every ID here must be checked against the Athena CONCEPT table before
v0.1. `verified` records whether that has been done.
"""

MALE = 8507  # Gender, verified: no
FEMALE = 8532  # Gender, verified: no
INPATIENT_VISIT = 9201  # Visit, verified: no
TYPE_CLAIM = 32810  # Type Concept "Claim", verified: no
UNKNOWN = 0

GENDER = {"1": MALE, "2": FEMALE}
