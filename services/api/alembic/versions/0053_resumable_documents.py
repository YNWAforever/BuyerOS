"""Bounded private resumable uploads and immutable PowerPoint source pages."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '0053_resumable_documents'
down_revision = '0052_private_document_storage'
branch_labels = depends_on = None
TABLES = ('document_uploads', 'document_upload_chunks', 'document_slides')


def receipts(head):
    for service in ('search', 'model', 'contact'):
        op.execute(f"CREATE OR REPLACE FUNCTION public.buyeros_{service}_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='{head}' FROM public.alembic_version),false) $$")


def upgrade():
    op.add_column('offer_documents', sa.Column('extraction_metadata', JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.drop_constraint(op.f('ck_private_document_objects_private_object_size'), 'private_document_objects', type_='check')
    op.create_check_constraint('private_object_size', 'private_document_objects', 'octet_length(body) BETWEEN 1 AND 20971520')
    op.create_table('document_uploads',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', UUID(as_uuid=True), nullable=False),
        sa.Column('actor_user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('media_type', sa.String(128), nullable=False),
        sa.Column('byte_length', sa.Integer, nullable=False),
        sa.Column('source_sha256', sa.String(64), nullable=False),
        sa.Column('chunk_size', sa.Integer, nullable=False),
        sa.Column('chunk_count', sa.Integer, nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('document_id', UUID(as_uuid=True), nullable=True),
        sa.Column('failure_code', sa.String(64), nullable=True),
        sa.Column('version', sa.Integer, nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('workspace_id', 'id'),
        sa.ForeignKeyConstraint(['workspace_id', 'project_id'], ['projects.workspace_id', 'projects.id'], ondelete='CASCADE', name='fk_document_uploads_project'),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], name='fk_document_uploads_actor'),
        sa.ForeignKeyConstraint(['workspace_id', 'project_id', 'document_id'], ['offer_documents.workspace_id', 'offer_documents.project_id', 'offer_documents.id'], ondelete='CASCADE', name='fk_document_uploads_document'),
        sa.CheckConstraint("byte_length BETWEEN 1 AND 20971520 AND (media_type='application/vnd.openxmlformats-officedocument.presentationml.presentation' OR byte_length<=5242880)", name='size'),
        sa.CheckConstraint("media_type IN ('application/vnd.openxmlformats-officedocument.presentationml.presentation','application/pdf','text/plain','text/markdown')", name='media_type'),
        sa.CheckConstraint("source_sha256 ~ '^[a-f0-9]{64}$'", name='digest'),
        sa.CheckConstraint('chunk_size=2097152 AND chunk_count=(byte_length+chunk_size-1)/chunk_size', name='geometry'),
        sa.CheckConstraint("status IN ('uploading','completed','failed','expired') AND version>0 AND (status<>'completed' OR document_id IS NOT NULL)", name='state'),
        sa.CheckConstraint("expires_at > created_at AND expires_at <= created_at + interval '1 hour'", name='expiry'),
    )
    op.create_index('ix_document_uploads_active_scope', 'document_uploads', ['workspace_id','actor_user_id','project_id','status','expires_at'])
    op.create_index('ix_document_uploads_document', 'document_uploads', ['workspace_id','project_id','document_id'])
    op.create_index('uq_document_uploads_active_manifest', 'document_uploads', ['workspace_id','project_id','actor_user_id','filename','media_type','source_sha256','byte_length'], unique=True, postgresql_where=sa.text("status='uploading'"))
    op.create_table('document_upload_chunks',
        sa.Column('workspace_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('upload_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('chunk_index', sa.Integer, primary_key=True),
        sa.Column('body', sa.LargeBinary, nullable=False),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id','upload_id'], ['document_uploads.workspace_id','document_uploads.id'], ondelete='CASCADE'),
        sa.CheckConstraint('chunk_index BETWEEN 0 AND 9 AND octet_length(body) BETWEEN 1 AND 2097152', name='bounds'),
        sa.CheckConstraint("sha256=encode(sha256(body),'hex')", name='digest'),
    )
    op.create_table('document_slides',
        sa.Column('workspace_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('document_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('slide_number', sa.Integer, primary_key=True),
        sa.Column('project_id', UUID(as_uuid=True), nullable=False),
        sa.Column('text', sa.Text, nullable=False),
        sa.Column('classification', sa.String(16), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id','project_id','document_id'], ['offer_documents.workspace_id','offer_documents.project_id','offer_documents.id'], ondelete='CASCADE'),
        sa.CheckConstraint("slide_number BETWEEN 1 AND 100 AND octet_length(text)<=100000 AND classification IN ('text','image_only')", name='bounds'),
    )
    op.create_index('ix_document_slides_project', 'document_slides', ['workspace_id','project_id','document_id'])
    for table in TABLES:
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        op.execute(f"CREATE POLICY tenant_isolation ON {table} USING (workspace_id=nullif(current_setting('app.workspace_id',true),'')::uuid) WITH CHECK (workspace_id=nullif(current_setting('app.workspace_id',true),'')::uuid)")
        op.execute(f'REVOKE ALL ON {table} FROM PUBLIC')
        privileges = 'SELECT,INSERT,UPDATE,DELETE' if table == 'document_uploads' else 'SELECT,INSERT,DELETE'
        op.execute(f'GRANT {privileges} ON {table} TO buyeros_api')
    op.execute("CREATE FUNCTION public.buyeros_document_part_immutable() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$ BEGIN RAISE EXCEPTION 'immutable document part' USING ERRCODE='23514'; END $$")
    for table in TABLES[1:]:
        op.execute(f'CREATE TRIGGER document_part_immutable BEFORE UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION public.buyeros_document_part_immutable()')
    op.execute("""CREATE FUNCTION public.buyeros_document_manifest_immutable() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$ BEGIN
      IF OLD.status<>'uploading' OR ROW(NEW.id,NEW.workspace_id,NEW.project_id,NEW.actor_user_id,NEW.filename,NEW.media_type,NEW.byte_length,NEW.source_sha256,NEW.chunk_size,NEW.chunk_count,NEW.created_at,NEW.expires_at)
        IS DISTINCT FROM ROW(OLD.id,OLD.workspace_id,OLD.project_id,OLD.actor_user_id,OLD.filename,OLD.media_type,OLD.byte_length,OLD.source_sha256,OLD.chunk_size,OLD.chunk_count,OLD.created_at,OLD.expires_at) THEN
        RAISE EXCEPTION 'immutable upload manifest' USING ERRCODE='23514'; END IF; RETURN NEW; END $$""")
    op.execute('CREATE TRIGGER document_manifest_immutable BEFORE UPDATE ON document_uploads FOR EACH ROW EXECUTE FUNCTION public.buyeros_document_manifest_immutable()')
    receipts(revision)


def downgrade():
    for table in (*TABLES, 'offer_documents', 'private_document_objects'):
        op.execute(f'ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY')
    db = op.get_bind()
    populated = any(db.execute(sa.text(f'SELECT EXISTS(SELECT 1 FROM {table})')).scalar_one() for table in TABLES)
    populated |= bool(db.execute(sa.text("SELECT EXISTS(SELECT 1 FROM offer_documents WHERE extraction_metadata<>'{}'::jsonb) OR EXISTS(SELECT 1 FROM private_document_objects WHERE octet_length(body)>5242880)")).scalar_one())
    if populated:
        raise RuntimeError('0053 downgrade blocked: preserve uploaded originals and receipts')
    for table in reversed(TABLES):
        op.drop_table(table)
    op.execute('DROP FUNCTION public.buyeros_document_part_immutable()')
    op.execute('DROP FUNCTION public.buyeros_document_manifest_immutable()')
    op.drop_column('offer_documents','extraction_metadata')
    op.drop_constraint(op.f('ck_private_document_objects_private_object_size'), 'private_document_objects', type_='check')
    op.create_check_constraint('private_object_size', 'private_document_objects', 'octet_length(body) BETWEEN 1 AND 5242880')
    for table in ('offer_documents','private_document_objects'):
        op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
    receipts(down_revision)
