"""Code-set entries offered when entering a claim (dim_cpt_codes.csv, dim_icd10_codes.csv)."""

from app.models.common import CptCode, DomainModel, Icd10Code, Money


class ProcedureCode(DomainModel):
    cpt_code: CptCode
    description: str
    category: str
    standard_charge: Money


class DiagnosisCode(DomainModel):
    icd10_code: Icd10Code
    description: str
    body_system: str
