"""Integer credit accounting. All entry points run in short tenant transactions.

Lock order: native runtime/outbox (when owned by caller), policy workspace,
USD workspace gate, USD reservation/accounts, credit account, workspace/project
limits, connection, quote, credit reservation, receipt. No external IO here.
The USD workspace gate serializes both ledgers, including settlement and caps.
"""
from decimal import Decimal
from sqlalchemy import func, select
from ..api.errors import ApiError
from ..db.xverum import (XverumCreditAccount as Account, XverumCreditLimit as Limit,
    XverumCreditReservation as Reservation, XverumReceiptRow as Receipt,
    XverumCreditSettlement as Settlement, XverumQuoteRow as Quote, XverumTariff as Tariff)
from .budget_service import lock_budget_workspace


async def lock_account(session, workspace_id, account_id):
    account = (await session.execute(select(Account).where(Account.workspace_id==workspace_id,
        Account.id==account_id).with_for_update().execution_options(populate_existing=True))).scalar_one()
    limits = (await session.execute(select(Limit).where(Limit.workspace_id==workspace_id)
        .order_by(Limit.project_id.asc().nullsfirst()).with_for_update())).scalars().all()
    return account, limits


async def capacity(session, workspace_id, project_id, account_id, credits):
    account, limits = await lock_account(session,workspace_id,account_id)
    relevant = [limit for limit in limits if limit.project_id in (None,project_id)]
    if len(relevant)!=2:
        raise ApiError(503,'XVERUM_CREDIT_LIMIT','administrator credit limits required')
    for bound, account_filter, project_filter in [(account.credit_limit,account.id,None)]+[
            (limit.credit_limit,None,limit.project_id) for limit in relevant]:
        hold = select(func.coalesce(func.sum(Reservation.held_credits),0)).where(Reservation.workspace_id==workspace_id)
        spend = select(func.coalesce(func.sum(Settlement.credits_used),0)).where(Settlement.workspace_id==workspace_id)
        if account_filter is not None:
            hold=hold.where(Reservation.account_id==account_filter);spend=spend.where(Settlement.account_id==account_filter)
        if project_filter is not None:
            hold=hold.where(Reservation.project_id==project_filter);spend=spend.where(Settlement.project_id==project_filter)
        if (await session.execute(hold)).scalar_one()+(await session.execute(spend)).scalar_one()+credits>bound:
            raise ApiError(409,'XVERUM_CREDIT_LIMIT','approved credit limit cannot cover operation')


async def settle_credits(session, receipt_id, credits_used: int) -> None:
    """Server evidence owner only; no browser settlement endpoint.

    Unknown/malformed/over-ceiling evidence keeps BOTH monetary and credit holds.
    A genuine integer zero is authoritative usage, not a missing-result heuristic.
    """
    candidate=(await session.execute(select(Receipt).where(Receipt.id==receipt_id))).scalar_one_or_none()
    if candidate is None:raise ApiError(404,'NOT_FOUND','receipt not available')
    await lock_budget_workspace(session,candidate.workspace_id)
    # A competing transaction may have advanced state/version while we waited.
    candidate=(await session.execute(select(Receipt).where(Receipt.id==receipt_id)
        .execution_options(populate_existing=True))).scalar_one()
    reservation=(await session.execute(select(Reservation).where(Reservation.id==candidate.reservation_id))).scalar_one()
    quote=(await session.execute(select(Quote).where(Quote.id==reservation.quote_id))).scalar_one()
    existing=(await session.execute(select(Settlement).where(Settlement.receipt_id==receipt_id))).scalar_one_or_none()
    if existing:
        if type(credits_used) is not int or existing.credits_used!=credits_used:
            raise ApiError(409,'IDEMPOTENCY_CONFLICT','settlement evidence differs')
        return
    if candidate.dispatch_state not in ('dispatched','outcome_unknown'):
        raise ApiError(409,'XVERUM_NOT_DISPATCHED','receipt has no dispatched operation')
    if type(credits_used) is not int or not 0<=credits_used<=reservation.max_credits:
        if candidate.dispatch_state!='outcome_unknown':candidate.version+=1
        candidate.dispatch_state='outcome_unknown'
        await session.flush()
        return
    tariff=(await session.execute(select(Tariff).where(Tariff.workspace_id==quote.workspace_id,
        Tariff.account_id==quote.account_id,Tariff.version==quote.tariff_version))).scalar_one()
    from .settlement import settle_operation
    async with session.begin_nested():
        await settle_operation(session,reservation.operation_id,Decimal(credits_used)*tariff.usd_per_credit,
            'xverum:'+str(receipt_id))
        await lock_account(session,candidate.workspace_id,reservation.account_id)
        reservation.held_credits=0
        candidate.dispatch_state='settled'
        candidate.version+=1
        session.add(Settlement(workspace_id=candidate.workspace_id,receipt_id=receipt_id,
            account_id=reservation.account_id,project_id=reservation.project_id,credits_used=credits_used))
        await session.flush()
