"""Idempotent local semantic and glossary seed."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.datasets.models import Dataset, DatasetField
from vip_api.semantic.models import (
    GlossaryDomain,
    GlossaryTerm,
    SemanticDimension,
    SemanticMeasure,
    SemanticMetric,
    SemanticModel,
    SemanticModelDataset,
)


async def seed_semantic_layer(db: AsyncSession) -> None:
    dataset = await db.scalar(select(Dataset).where(Dataset.source_name == "vip_b5_sales_demo"))
    if dataset is None:
        raise RuntimeError("Run seed-dataset-catalogs before seed-semantic-layer")
    model = await db.scalar(
        select(SemanticModel).where(
            SemanticModel.organization_id == dataset.organization_id,
            SemanticModel.workspace_id == dataset.workspace_id,
            SemanticModel.key == "sales_demo",
        )
    )
    if model is None:
        model = SemanticModel(
            organization_id=dataset.organization_id,
            workspace_id=dataset.workspace_id,
            key="sales_demo",
            name="Sales Analytics Demo",
            description="Published semantic model backed by the local PostgreSQL demo source",
            status="published",
            primary_dataset_id=dataset.id,
            currency="SAR",
            published_version=1,
            created_by_user_id=dataset.created_by_user_id,
            updated_by_user_id=dataset.created_by_user_id,
        )
        db.add(model)
        await db.flush()
        db.add(
            SemanticModelDataset(
                organization_id=dataset.organization_id,
                workspace_id=dataset.workspace_id,
                semantic_model_id=model.id,
                dataset_id=dataset.id,
                alias="sales",
                is_primary=True,
            )
        )
    fields = {
        field.source_name: field
        for field in (
            await db.scalars(select(DatasetField).where(DatasetField.dataset_id == dataset.id))
        ).all()
    }
    for key, kind, time in (("order_date", "time", True), ("country", "categorical", False)):
        if (
            await db.scalar(
                select(SemanticDimension.id).where(
                    SemanticDimension.semantic_model_id == model.id, SemanticDimension.key == key
                )
            )
            is None
        ):
            field = fields[key]
            db.add(
                SemanticDimension(
                    organization_id=dataset.organization_id,
                    workspace_id=dataset.workspace_id,
                    semantic_model_id=model.id,
                    dataset_id=dataset.id,
                    field_id=field.id,
                    key=key,
                    name=field.display_name,
                    dimension_type=kind,
                    data_type=field.normalized_data_type,
                    is_time_dimension=time,
                    time_granularities=["day", "month", "year"] if time else [],
                )
            )
    measure = await db.scalar(
        select(SemanticMeasure).where(
            SemanticMeasure.semantic_model_id == model.id, SemanticMeasure.key == "revenue"
        )
    )
    if measure is None:
        measure = SemanticMeasure(
            organization_id=dataset.organization_id,
            workspace_id=dataset.workspace_id,
            semantic_model_id=model.id,
            dataset_id=dataset.id,
            field_id=fields["revenue"].id,
            key="revenue",
            name="Revenue",
            aggregation="sum",
            data_type="decimal",
            format={"style": "currency", "currency": "SAR"},
        )
        db.add(measure)
        await db.flush()
    if (
        await db.scalar(
            select(SemanticMetric.id).where(
                SemanticMetric.semantic_model_id == model.id, SemanticMetric.key == "total_revenue"
            )
        )
        is None
    ):
        db.add(
            SemanticMetric(
                organization_id=dataset.organization_id,
                workspace_id=dataset.workspace_id,
                semantic_model_id=model.id,
                key="total_revenue",
                name="Total Revenue",
                metric_type="measure",
                base_measure_id=measure.id,
                status="active",
                format={"style": "currency", "currency": "SAR"},
            )
        )
    domain = await db.scalar(
        select(GlossaryDomain).where(
            GlossaryDomain.organization_id == dataset.organization_id,
            GlossaryDomain.workspace_id == dataset.workspace_id,
            GlossaryDomain.key == "revenue",
        )
    )
    if domain is None:
        domain = GlossaryDomain(
            organization_id=dataset.organization_id,
            workspace_id=dataset.workspace_id,
            key="revenue",
            name="Revenue",
            description="Commercial performance terminology",
        )
        db.add(domain)
        await db.flush()
    if (
        await db.scalar(
            select(GlossaryTerm.id).where(
                GlossaryTerm.organization_id == dataset.organization_id,
                GlossaryTerm.workspace_id == dataset.workspace_id,
                GlossaryTerm.key == "total_revenue",
            )
        )
        is None
    ):
        db.add(
            GlossaryTerm(
                organization_id=dataset.organization_id,
                workspace_id=dataset.workspace_id,
                domain_id=domain.id,
                key="total_revenue",
                name="Total Revenue",
                definition="The sum of recognized revenue for the selected business context.",
                status="approved",
                synonyms=["revenue"],
                examples=["Monthly total revenue"],
                source="system",
            )
        )
    await db.commit()
