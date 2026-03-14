"""masterpiece evidence and confidence additions

Revision ID: 20260314_0001
Revises: 
Create Date: 2026-03-14 13:05:00
"""
from alembic import op
import sqlalchemy as sa

revision = '20260314_0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('tickets', sa.Column('source_video_hash', sa.String(length=128), nullable=True))
    op.add_column('tickets', sa.Column('confidence_status', sa.String(length=32), nullable=True))
    op.add_column('tickets', sa.Column('confidence_reason', sa.Text(), nullable=True))
    op.add_column('tickets', sa.Column('parking_likelihood_score', sa.Float(), nullable=True))
    op.add_column('tickets', sa.Column('stop_due_to_traffic_possible', sa.Boolean(), nullable=True))
    op.add_column('tickets', sa.Column('stationary_duration_seconds', sa.Float(), nullable=True))
    op.add_column('tickets', sa.Column('traffic_flow_state', sa.String(length=32), nullable=True))
    op.add_column('tickets', sa.Column('target_track_id', sa.Integer(), nullable=True))
    op.add_column('tickets', sa.Column('registry_match', sa.JSON(), nullable=True))
    op.add_column('tickets', sa.Column('vehicle_attributes', sa.JSON(), nullable=True))
    op.add_column('tickets', sa.Column('evidence_summary', sa.JSON(), nullable=True))

    op.create_table(
        'ticket_screenshots',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('ticket_id', sa.Integer(), nullable=False),
        sa.Column('image_path', sa.String(length=500), nullable=False),
        sa.Column('thumbnail_path', sa.String(length=500), nullable=True),
        sa.Column('frame_timestamp_ms', sa.BigInteger(), nullable=False),
        sa.Column('video_timestamp_text', sa.String(length=64), nullable=False),
        sa.Column('source_video_hash', sa.String(length=128), nullable=True),
        sa.Column('captured_by', sa.String(length=100), nullable=True),
        sa.Column('capture_note', sa.Text(), nullable=True),
        sa.Column('frame_width', sa.Integer(), nullable=True),
        sa.Column('frame_height', sa.Integer(), nullable=True),
        sa.Column('is_blurred_source', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_ticket_screenshots_ticket_id', 'ticket_screenshots', ['ticket_id'])
    op.create_index('ix_ticket_screenshots_frame_timestamp_ms', 'ticket_screenshots', ['frame_timestamp_ms'])
    op.create_index('ix_tickets_confidence_status', 'tickets', ['confidence_status'])


def downgrade() -> None:
    op.drop_index('ix_tickets_confidence_status', table_name='tickets')
    op.drop_index('ix_ticket_screenshots_frame_timestamp_ms', table_name='ticket_screenshots')
    op.drop_index('ix_ticket_screenshots_ticket_id', table_name='ticket_screenshots')
    op.drop_table('ticket_screenshots')

    for column in [
        'evidence_summary',
        'vehicle_attributes',
        'registry_match',
        'target_track_id',
        'traffic_flow_state',
        'stationary_duration_seconds',
        'stop_due_to_traffic_possible',
        'parking_likelihood_score',
        'confidence_reason',
        'confidence_status',
        'source_video_hash',
    ]:
        op.drop_column('tickets', column)
