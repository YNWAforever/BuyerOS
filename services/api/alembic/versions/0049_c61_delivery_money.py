"""Align durable delivery liability with original reservation money without erasing history."""
import sqlalchemy as sa
from alembic import op

revision='0049_c61_delivery_money'
down_revision='0048_c61_delivery_ledger'
branch_labels=depends_on=None

def _receipt_guard(head):
    for service in ('search','model','contact'):
        op.execute(f"CREATE OR REPLACE FUNCTION public.buyeros_{service}_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='{head}' FROM public.alembic_version),false) $$")

def upgrade():
    op.alter_column('delivery_liabilities','max_liability',existing_type=sa.Numeric(18,6),type_=sa.Numeric(20,6),existing_nullable=False)
    _receipt_guard(revision)

def downgrade():
    # Retain original precision, history and unknown liabilities on application rollback.
    if op.get_bind().execute(sa.text('SELECT EXISTS(SELECT 1 FROM delivery_liabilities)')).scalar_one():
        raise RuntimeError('0049 downgrade blocked: retain delivery history and numeric liability precision')
    op.alter_column('delivery_liabilities','max_liability',existing_type=sa.Numeric(20,6),type_=sa.Numeric(18,6),existing_nullable=False)
    _receipt_guard(down_revision)
