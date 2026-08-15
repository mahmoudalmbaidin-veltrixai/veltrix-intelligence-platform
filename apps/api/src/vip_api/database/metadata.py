"""Authoritative SQLAlchemy model registry for schema tooling.

Importing this module loads every ORM model onto the one shared ``Base`` and
then exposes that complete metadata graph to Alembic and schema tests. Keep
model registration explicit here so a runtime router import cannot determine
whether a production table is visible to autogenerate.
"""

from __future__ import annotations

from types import ModuleType

from sqlalchemy import MetaData

from vip_api.auth import models as auth_models
from vip_api.connections import models as connection_models
from vip_api.dashboard_delivery import models as dashboard_delivery_models
from vip_api.dashboards import models as dashboard_models
from vip_api.database.base import Base
from vip_api.datasets import models as dataset_models
from vip_api.files import models as file_models
from vip_api.governance import models as governance_models
from vip_api.home import models as home_models
from vip_api.jobs import models as job_models
from vip_api.pipelines import models as pipeline_models
from vip_api.semantic import models as semantic_models
from vip_api.tenancy import models as tenancy_models

MODEL_MODULES: tuple[ModuleType, ...] = (
    auth_models,
    connection_models,
    dashboard_delivery_models,
    dashboard_models,
    dataset_models,
    file_models,
    governance_models,
    home_models,
    job_models,
    pipeline_models,
    semantic_models,
    tenancy_models,
)

target_metadata: MetaData = Base.metadata

__all__ = ("MODEL_MODULES", "target_metadata")
