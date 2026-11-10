
from fastapi import APIRouter, HTTPException, Response, status

from app.models import (
    RULE_FIELDS,
    Permission,
    Rule,
    RuleCreate,
    RuleDefinition,
    RuleField,
    RuleTestResult,
    RuleUpdate,
)
from app.models.rule import RuleId, RuleSource
from app.services import validation_engine
from app.services.auth import require
from app.services.org_context import OrgClaims, OrgPayerDocuments, OrgRules

router = APIRouter(prefix="/api/rules", tags=["rules"], dependencies=[require(Permission.CLAIMS_READ)])

WRITE = [require(Permission.RULES_WRITE)]

Rules = OrgRules


@router.get("", response_model=list[Rule])
def list_rules(rules: Rules) -> list[Rule]:
    return rules.list()


@router.get("/fields", response_model=list[RuleField])
def list_rule_fields() -> list[RuleField]:
    """Claim fields that rule conditions can test, with their types and allowed values."""
    return list(RULE_FIELDS.values())


@router.post("/test", response_model=RuleTestResult, dependencies=WRITE)
def test_rule(
    rule: RuleDefinition,
    claims: OrgClaims,
) -> RuleTestResult:
    """Run a draft rule against every claim without saving it."""
    return validation_engine.test_rule(rule, claims.claims_frame())


@router.get("/{rule_id}", response_model=Rule)
def get_rule(rule_id: RuleId, rules: Rules) -> Rule:
    return _found(rules.get(rule_id), rule_id)


def _checked_source(source: RuleSource | None, documents) -> RuleSource | None:
    """The rule's source with its document's title, if the document and page exist."""
    if source is None:
        return None
    document = documents.get(source.document_id)
    if document is None:
        raise HTTPException(status_code=422, detail=f"No payer document {source.document_id}")
    if source.page is not None and source.page > document.pages:
        raise HTTPException(
            status_code=422, detail=f"{document.title} has {document.pages} pages; there's no page {source.page}"
        )
    return source.model_copy(update={"document_title": document.title, "excerpt": source.excerpt.strip()})


@router.post("", response_model=Rule, status_code=status.HTTP_201_CREATED, dependencies=WRITE)
def create_rule(data: RuleCreate, rules: Rules, documents: OrgPayerDocuments) -> Rule:
    data = data.model_copy(update={"source": _checked_source(data.source, documents)})
    return rules.create(data)


@router.put("/{rule_id}", response_model=Rule, dependencies=WRITE)
def replace_rule(rule_id: RuleId, data: RuleCreate, rules: Rules, documents: OrgPayerDocuments) -> Rule:
    data = data.model_copy(update={"source": _checked_source(data.source, documents)})
    return _found(rules.replace(rule_id, data), rule_id)


@router.patch("/{rule_id}", response_model=Rule, dependencies=WRITE)
def update_rule(rule_id: RuleId, changes: RuleUpdate, rules: Rules, documents: OrgPayerDocuments) -> Rule:
    """Partial update, e.g. {"enabled": false} to toggle a rule off, or {"source": null}."""
    if "source" in changes.model_fields_set:
        changes = changes.model_copy(update={"source": _checked_source(changes.source, documents)})
    return _found(rules.update(rule_id, changes), rule_id)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=WRITE)
def delete_rule(rule_id: RuleId, rules: Rules) -> Response:
    if not rules.delete(rule_id):
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _found(rule: Rule | None, rule_id: str) -> Rule:
    if rule is None:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    return rule
