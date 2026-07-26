"""Central API router registration."""

from fastapi import FastAPI

from vip_api.api.routes.operational import router as operational_router
from vip_api.api.routes.v1.version import router as version_router
from vip_api.auth.routes import router as auth_router
from vip_api.catalog.routes import router as catalog_router
from vip_api.connections.routes import router as connections_router
from vip_api.core.config import Settings
from vip_api.dashboard_delivery.routes import router as dashboard_delivery_router
from vip_api.dashboards.routes import router as dashboards_router
from vip_api.datasets.routes import router as datasets_router
from vip_api.events.routes import router as events_router
from vip_api.files.routes import router as files_router
from vip_api.governance.routes import router as governance_router
from vip_api.home.routes import notifications_router
from vip_api.home.routes import router as home_router
from vip_api.jobs.routes import router as jobs_router
from vip_api.pipelines.routes import artifact_router as pipeline_artifact_router
from vip_api.pipelines.routes import router as pipelines_router
from vip_api.semantic.routes import glossary_router, models_router, query_router
from vip_api.tenancy.routes import router as tenancy_router


def register_routers(app: FastAPI, settings: Settings) -> None:
    app.include_router(operational_router)
    app.include_router(auth_router)
    app.include_router(version_router, prefix=settings.API_V1_PREFIX, tags=["version"])
    app.include_router(tenancy_router, prefix=settings.API_V1_PREFIX)
    app.include_router(governance_router, prefix=settings.API_V1_PREFIX)
    app.include_router(home_router, prefix=settings.API_V1_PREFIX)
    app.include_router(notifications_router, prefix=settings.API_V1_PREFIX)
    app.include_router(catalog_router, prefix=settings.API_V1_PREFIX)
    app.include_router(jobs_router, prefix=settings.API_V1_PREFIX)
    app.include_router(files_router, prefix=settings.API_V1_PREFIX)
    app.include_router(events_router, prefix=settings.API_V1_PREFIX)
    app.include_router(connections_router, prefix=settings.API_V1_PREFIX)
    app.include_router(datasets_router, prefix=settings.API_V1_PREFIX)
    app.include_router(dashboards_router, prefix=settings.API_V1_PREFIX)
    app.include_router(dashboard_delivery_router, prefix=settings.API_V1_PREFIX)
    app.include_router(pipelines_router, prefix=settings.API_V1_PREFIX)
    app.include_router(pipeline_artifact_router, prefix=settings.API_V1_PREFIX)
    app.include_router(models_router, prefix=settings.API_V1_PREFIX)
    app.include_router(glossary_router, prefix=settings.API_V1_PREFIX)
    app.include_router(query_router, prefix=settings.API_V1_PREFIX)
