"""initial

Revision ID: 001
Revises: 
Create Date: 2026-05-01 14:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('tenders',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('department', sa.String(100), nullable=False),
        sa.Column('publish_date', sa.DateTime, nullable=True),
        sa.Column('closing_date', sa.DateTime, nullable=True),
        sa.Column('status', sa.String(20), nullable=True),
        sa.Column('criteria', sa.JSON, nullable=True),
        sa.Column('criteria_locked', sa.DateTime, nullable=True),
    )

    op.create_table('bidders',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('tender_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenders.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('pan', sa.String(10), nullable=True),
        sa.Column('gstin', sa.String(15), nullable=True),
        sa.Column('status', sa.String(20), nullable=True),
    )

    op.create_table('bidder_documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('bidder_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('bidders.id'), nullable=False),
        sa.Column('doc_type', sa.String(50), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('minio_path', sa.String(500), nullable=True),
        sa.Column('extracted_text', sa.Text, nullable=True),
        sa.Column('extracted_json', sa.JSON, nullable=True),
        sa.Column('ocr_confidence', sa.Float, nullable=True),
        sa.Column('page_count', sa.Integer, nullable=True),
    )

    op.create_table('verdicts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('bidder_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('bidders.id'), nullable=False),
        sa.Column('criterion_id', sa.String(20), nullable=False),
        sa.Column('criterion_type', sa.String(20), nullable=False),
        sa.Column('verdict', sa.String(20), nullable=False),
        sa.Column('reason', sa.Text, nullable=True),
        sa.Column('confidence', sa.Float, nullable=True),
        sa.Column('source_page', sa.Integer, nullable=True),
        sa.Column('source_bbox', sa.JSON, nullable=True),
        sa.Column('verbatim_quote', sa.Text, nullable=True),
        sa.Column('computed_at', sa.DateTime, nullable=True),
    )

    op.create_table('audit_log',
        sa.Column('index', sa.BigInteger, autoincrement=True, primary_key=True),
        sa.Column('timestamp', sa.DateTime, nullable=True),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('actor', sa.String(100), nullable=True),
        sa.Column('data', sa.JSON, nullable=True),
        sa.Column('prev_hash', sa.String(64), nullable=True),
        sa.Column('this_hash', sa.String(64), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('audit_log')
    op.drop_table('verdicts')
    op.drop_table('bidder_documents')
    op.drop_table('bidders')
    op.drop_table('tenders')
