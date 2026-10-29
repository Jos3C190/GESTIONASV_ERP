"""Read development records and render QA copies; never modify business data."""
import asyncio
import uuid
from pathlib import Path

from sqlalchemy import select, text

from app.application.procurement_reports import consolidation_report, retaceo_report
from app.infrastructure.db.session import async_session_factory, dispose_engine
from app.infrastructure.models.purchase_consolidation import PurchaseConsolidationModel
from app.infrastructure.models.retaceo import RetaceoModel
from app.infrastructure.procurement_report_renderer import render_pdf, render_xlsx
from app.infrastructure.repositories.procurement_report_repository import ProcurementReportRepository
from app.infrastructure.repositories.purchase_consolidation_repository import SqlAlchemyPurchaseConsolidationRepository
from app.infrastructure.repositories.retaceo_repository import SqlAlchemyRetaceoRepository


async def main():
    folder = Path('/app/tmp-procurement-reports')
    folder.mkdir(exist_ok=True)
    company_id = uuid.UUID('0a7303f6-64a5-428c-a829-c2b09966fefd')
    try:
        async with async_session_factory() as session:
            await session.execute(text('SET TRANSACTION READ ONLY'))
            repository = ProcurementReportRepository(session)
            rid = await session.scalar(select(RetaceoModel.id).where(
                RetaceoModel.company_id == company_id, RetaceoModel.code == 'RET-00021'))
            item = await SqlAlchemyRetaceoRepository(session).get_retaceo(company_id, rid)
            report = retaceo_report(item, await repository.context(company_id, item))
            (folder/'RET-00021.pdf').write_bytes(render_pdf(report))
            (folder/'RET-00021.xlsx').write_bytes(render_xlsx(report))
            print('retaceo', item.code, 'total', item.total_cost)
            cid = await session.scalar(select(PurchaseConsolidationModel.id).where(
                PurchaseConsolidationModel.company_id == company_id
            ).order_by(PurchaseConsolidationModel.updated_at.desc()).limit(1))
            item = await SqlAlchemyPurchaseConsolidationRepository(session).get(company_id, cid)
            report = consolidation_report(item, await repository.context(company_id))
            (folder/'consolidado-general.pdf').write_bytes(render_pdf(report))
            print('consolidado', item.code, 'productos', len(item.lines))
            await session.rollback()
    finally:
        await dispose_engine()


asyncio.run(main())
