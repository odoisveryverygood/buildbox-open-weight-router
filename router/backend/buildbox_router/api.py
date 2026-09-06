import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response

from .composition import Services, example, fixture_services
from .config import Settings
from .contracts import (
    CatalogSnapshot,
    DraftPolicy,
    ErrorCode,
    ErrorResponse,
    EvaluationRun,
    Example,
    Intake,
    Job,
    Recommendation,
    StackComparison,
    Submission,
    Workflow,
)
from .errors import DomainError
from .storage import SqlStorage, engine_for


def create_app(settings: Settings | None = None, services: Services | None = None) -> FastAPI:
    config = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = None
        if services is None:
            engine = engine_for(config)
            storage = SqlStorage(engine)
            storage.check_revision()
            app.state.services = fixture_services(storage)
        else:
            app.state.services = services
        yield
        if engine is not None:
            engine.dispose()

    app = FastAPI(
        title="Buildbox offline workflow router",
        version="1.0",
        lifespan=lifespan,
        responses={
            400: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
            409: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
        },
    )
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )

    @app.middleware("http")
    async def fixture_boundary(request: Request, call_next: RequestResponseEndpoint) -> Response:
        origin = request.headers.get("origin")
        if origin and origin not in (
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:8000",
            "http://localhost:8000",
        ):
            return JSONResponse(
                status_code=403,
                content=ErrorResponse(
                    code=ErrorCode.INVALID, message="Local fixture origin required"
                ).model_dump(),
            )
        return await call_next(request)

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content=exc.detail.model_dump())

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                code=ErrorCode.INVALID,
                message="Request violates the versioned contract; check field types and graph references",
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                code=ErrorCode.INTERNAL, message="Internal error; no provider details exposed"
            ).model_dump(),
        )

    def svc() -> Services:
        return cast(Services, app.state.services)

    owner = config.fixture_owner

    @app.get("/api/examples")
    def examples() -> list[Example]:
        return [example()]

    @app.post("/api/intakes", status_code=201)
    def save_intake(intake: Intake) -> Submission:
        intake_id = uuid4().hex
        svc().storage.put(owner, "intake", intake_id, intake.model_dump_json())
        interpreted = svc().interpreter.interpret(intake, uuid4().hex)
        workflow = interpreted.workflow
        if workflow is None:
            return Submission(intake_id=intake_id, interpretation=interpreted)
        svc().storage.put(
            owner, "workflow", workflow.id, workflow.model_dump_json(), workflow.version
        )
        now = time.time()
        job = Job(
            id=uuid4().hex,
            workflow_id=workflow.id,
            workflow_version=workflow.version,
            status="queued",
            created_at=now,
            updated_at=now,
        )
        svc().storage.enqueue(owner, job)
        return Submission(intake_id=intake_id, interpretation=interpreted, job=job)

    @app.get("/api/intakes/{intake_id}")
    def get_intake(intake_id: str) -> Intake:
        return Intake.model_validate_json(svc().storage.get(owner, "intake", intake_id))

    @app.get("/api/workflows/{workflow_id}/versions/{version}")
    def get_workflow(workflow_id: str, version: int) -> Workflow:
        return Workflow.model_validate_json(
            svc().storage.get(owner, "workflow", workflow_id, version)
        )

    @app.post("/api/workflows/{workflow_id}/versions", status_code=201)
    def append_version(workflow_id: str, workflow: Workflow) -> Workflow:
        if workflow.id != workflow_id or workflow.version < 2:
            raise DomainError(ErrorCode.INVALID, "Append the next version of an owned workflow")
        svc().storage.get(owner, "workflow", workflow_id, workflow.version - 1)
        svc().storage.put(
            owner, "workflow", workflow.id, workflow.model_dump_json(), workflow.version
        )
        return workflow

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> Job:
        return svc().storage.job(owner, job_id)

    @app.get("/api/recommendations/{recommendation_id}")
    def get_recommendation(recommendation_id: str) -> Recommendation:
        return Recommendation.model_validate_json(
            svc().storage.get(owner, "recommendation", recommendation_id)
        )

    @app.get("/api/recommendations/{recommendation_id}/evidence")
    def get_evidence(recommendation_id: str) -> CatalogSnapshot:
        return CatalogSnapshot.model_validate_json(
            svc().storage.get(owner, "catalog", recommendation_id)
        )

    @app.get("/api/recommendations/{recommendation_id}/comparison")
    def compare(recommendation_id: str) -> StackComparison:
        rec = get_recommendation(recommendation_id)
        return svc().selector.compare(
            get_evidence(recommendation_id),
            tuple(
                dict.fromkeys(
                    [a.configuration_id for a in rec.assignments] + list(rec.alternatives)
                )
            ),
        )

    @app.post("/api/recommendations/{recommendation_id}/evaluation")
    def evaluate(recommendation_id: str) -> EvaluationRun:
        evaluation = svc().evaluator.evaluate(
            get_recommendation(recommendation_id), "fixture-holdout-v1"
        )
        try:
            svc().storage.put(owner, "evaluation", evaluation.id, evaluation.model_dump_json())
        except DomainError as exc:
            if exc.detail.code != ErrorCode.CONFLICT:
                raise
            return EvaluationRun.model_validate_json(
                svc().storage.get(owner, "evaluation", evaluation.id)
            )
        return evaluation

    @app.post("/api/recommendations/{recommendation_id}/policy")
    def export_policy(recommendation_id: str) -> DraftPolicy:
        rec = get_recommendation(recommendation_id)
        workflow = get_workflow(rec.workflow_id, rec.workflow_version)
        policy = svc().compiler.compile(workflow, rec)
        try:
            svc().storage.put(owner, "policy", policy.id, policy.model_dump_json())
        except DomainError as exc:
            if exc.detail.code != ErrorCode.CONFLICT:
                raise
            return DraftPolicy.model_validate_json(svc().storage.get(owner, "policy", policy.id))
        return policy

    return app
