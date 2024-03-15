import pandas as pd
from models import RacialGroup
import os

print(os.getcwd())
POLICE_GEOGRAPHIES = pd.read_csv(
    "deo_backend/demographics/police_geographies.csv", dtype=str
)

DEMOGRAPHICS_DF = pd.read_csv(
    "deo_backend/demographics/police_service_area.csv", dtype={"PSA_NUM": str}
).set_index("PSA_NUM")

DEMOGRAPHICS_PSA = DEMOGRAPHICS_DF.to_dict("index")

DEMOGRAPHICS_DISTRICT = DEMOGRAPHICS_DF.join(
    POLICE_GEOGRAPHIES.set_index("full_psa_num")["district"]
).set_index("district")
DEMOGRAPHICS_DISTRICT = DEMOGRAPHICS_DISTRICT.groupby(DEMOGRAPHICS_DISTRICT.index).sum()

DEMOGRAPHICS_DIVISION = DEMOGRAPHICS_DF.join(
    POLICE_GEOGRAPHIES.set_index("full_psa_num")["division"]
).set_index("division")
DEMOGRAPHICS_DIVISION = DEMOGRAPHICS_DIVISION.groupby(DEMOGRAPHICS_DIVISION.index).sum()
DEMOGRAPHICS_TOTAL = DEMOGRAPHICS_DF.sum().to_dict()

# Align with ODP columns
DEMOGRAPHICS_TOTAL.pop("total")
DEMOGRAPHICS_TOTAL[RacialGroup.white.value] = DEMOGRAPHICS_TOTAL.pop("white")
DEMOGRAPHICS_TOTAL[RacialGroup.black.value] = DEMOGRAPHICS_TOTAL.pop("black")
DEMOGRAPHICS_TOTAL[RacialGroup.asian.value] = DEMOGRAPHICS_TOTAL.pop("asian")
DEMOGRAPHICS_TOTAL[RacialGroup.latino.value] = DEMOGRAPHICS_TOTAL.pop(
    "hispanic_or_latino"
)
DEMOGRAPHICS_TOTAL[RacialGroup.other_race.value] = DEMOGRAPHICS_TOTAL.pop(
    "american_indian"
) + DEMOGRAPHICS_TOTAL.pop("unknown")
