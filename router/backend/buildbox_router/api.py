import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast
from uuid import uuid4

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response

from .auth import Authenticator
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
from .intelligence.selection.policy import SafeDraftCompiler
from .planning import planning_examples
from .planning_contracts import PlanInput, PlanningCapabilities, PlanView
from .planning_storage import PlanningStorage
from .storage import SqlStorage, engine_for


def create_app(settings: Settings | None = None, services: Services | None = None) -> FastAPI:
    config = settings or Settings.from_env()
    authenticator = (
        Authenticator(config.auth_file)
        if config.identity_mode == "shared" and config.auth_file
        else None
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = None
        if services is None:
            engine = engine_for(config)
            storage = PlanningStorage(engine)
            storage.check_revision()
            app.state.services = fixture_services(storage)
        else:
            app.state.services = services
        yield
        if engine is not None:
            engine.dispose()

    app = FastAPI(
        title="Buildbox planning router",
        version="1.1",
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
        if (
            config.identity_mode == "local_fixture"
            and request.client
            and request.client.host not in ("127.0.0.1", "::1", "testclient")
        ):
            return JSONResponse(
                status_code=403,
                content={
                    "message": "Unauthenticated fixture identity is restricted to loopback clients"
                },
            )
        request.state.owner = config.fixture_owner
        if authenticator:
            identity = authenticator.owner(request.headers.get("authorization", ""))
            if identity is None:
                return JSONResponse(
                    status_code=401,
                    content={"message": "Authentication required"},
                    headers={
                        "WWW-Authenticate": 'Basic realm="Buildbox planning", charset="UTF-8"',
                        "Cache-Control": "no-store",
                    },
                )
            request.state.owner = identity
        if request.method == "POST":
            length = request.headers.get("content-length", "")
            if not length.isdecimal() or int(length) > 65536:
                return JSONResponse(
                    status_code=413,
                    content={
                        "message": "Planning request must have a bounded content length, at most 64 KiB"
                    },
                )
        if (
            (config.identity_mode == "shared" or config.mode == "live")
            and request.url.path.startswith("/api/")
            and not request.url.path.startswith(("/api/plans", "/api/planning-"))
        ):
            return JSONResponse(
                status_code=404,
                content={
                    "message": "Legacy fixture API is unavailable in shared/live mode; use exact-version planning endpoints"
                },
            )
        origin = request.headers.get("origin")
        if origin and origin not in (
            config.web_origin,
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
        try:
            response = await call_next(request)
        except Exception:
            # Do not let server traceback logging expose request/provider/SQL payloads.
            response = JSONResponse(
                status_code=500,
                content=ErrorResponse(
                    code=ErrorCode.INTERNAL, message="Internal planning error; details redacted"
                ).model_dump(),
            )
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

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

    def reject_legacy_plan(workflow_id: str) -> None:
        try:
            svc().storage.get(owner, "plan", workflow_id)
        except DomainError as exc:
            if exc.detail.code == ErrorCode.NOT_FOUND:
                return
            raise
        raise DomainError(
            ErrorCode.UNSUPPORTED,
            "Use the authenticated exact-version planning endpoint for this resource",
        )

    def planning_storage() -> PlanningStorage:
        storage = svc().storage
        if not isinstance(storage, SqlStorage):
            raise DomainError(ErrorCode.UNSUPPORTED, "Durable planning storage is not configured")
        return PlanningStorage(storage.engine)

    @app.get("/api/planning-capabilities")
    def capabilities() -> PlanningCapabilities:
        return PlanningCapabilities(
            mode=config.mode,
            authentication=config.identity_mode,
            interpretation_available=config.local_interpretation_model is not None,
            local_model=config.local_interpretation_model,
            live_gate="Opt-in local cached-model interpretation uses no external provider. Hosted interpretation requires a recorded role/key permission and budget. Public metadata research needs separate opt-in but no paid credential.",
        )

    @app.get("/api/planning-examples")
    def plan_examples() -> list[Example]:
        return planning_examples()

    @app.post("/api/plans", status_code=201)
    def create_plan(
        value: PlanInput,
        request: Request,
        idempotency_key: str = Header(min_length=8, max_length=80),
    ) -> PlanView:
        return planning_storage().submit(request.state.owner, idempotency_key, value)

    @app.get("/api/plans/{plan_id}/versions/{version}")
    def read_plan(plan_id: str, version: int, request: Request) -> PlanView:
        return planning_storage().view(request.state.owner, plan_id, version)

    @app.post("/api/plans/{plan_id}/versions/{version}/revise", status_code=201)
    def revise_plan(
        plan_id: str,
        version: int,
        value: PlanInput,
        request: Request,
        idempotency_key: str = Header(min_length=8, max_length=80),
    ) -> PlanView:
        return planning_storage().submit(
            request.state.owner, idempotency_key, value, plan_id, version
        )

    @app.post("/api/plans/{plan_id}/versions/{version}/cancel")
    def cancel_plan(plan_id: str, version: int, request: Request) -> PlanView:
        return planning_storage().cancel(request.state.owner, plan_id, version)

    @app.post("/api/plans/{plan_id}/versions/{version}/policy")
    def plan_policy(plan_id: str, version: int, request: Request) -> DraftPolicy:
        view = planning_storage().view(request.state.owner, plan_id, version)
        if view.stale:
            raise DomainError(
                ErrorCode.CONFLICT,
                "Earlier recommendation is stale; export requires the latest exact plan version",
                409,
            )
        result = view.result
        if (
            not result
            or not result.workflow
            or not result.recommendation
            or not result.catalog
            or result.status == "blocked"
        ):
            raise DomainError(
                ErrorCode.UNSUPPORTED, "No complete admissible mapping exists for this version"
            )
        return SafeDraftCompiler(result.catalog).compile(result.workflow, result.recommendation)

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
        reject_legacy_plan(workflow_id)
        return Workflow.model_validate_json(
            svc().storage.get(owner, "workflow", workflow_id, version)
        )

    @app.post("/api/workflows/{workflow_id}/versions", status_code=201)
    def append_version(workflow_id: str, workflow: Workflow) -> Workflow:
        reject_legacy_plan(workflow_id)
        if workflow.id != workflow_id or workflow.version < 2:
            raise DomainError(ErrorCode.INVALID, "Append the next version of an owned workflow")
        svc().storage.get(owner, "workflow", workflow_id, workflow.version - 1)
        svc().storage.put(
            owner, "workflow", workflow.id, workflow.model_dump_json(), workflow.version
        )
        return workflow

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> Job:
        job = svc().storage.job(owner, job_id)
        if job.operation == "planning":
            raise DomainError(
                ErrorCode.UNSUPPORTED, "Read planning jobs through their exact plan/version"
            )
        return job

    @app.get("/api/recommendations/{recommendation_id}")
    def get_recommendation(recommendation_id: str) -> Recommendation:
        value = Recommendation.model_validate_json(
            svc().storage.get(owner, "recommendation", recommendation_id)
        )
        reject_legacy_plan(value.workflow_id)
        return value

    @app.get("/api/recommendations/{recommendation_id}/evidence")
    def get_evidence(recommendation_id: str) -> CatalogSnapshot:
        get_recommendation(recommendation_id)
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
