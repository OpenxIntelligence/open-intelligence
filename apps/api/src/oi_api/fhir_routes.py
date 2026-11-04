"""FHIR interoperability endpoints whose claims are generated from implemented behavior."""
from fastapi import APIRouter

from .fhir_kernel import capability_statement


def fhir_router() -> APIRouter:
    router = APIRouter(tags=["FHIR interoperability"])

    @router.get("/v1/fhir/metadata", operation_id="fhir_capability_statement_r4")
    def metadata():
        return capability_statement()

    return router
