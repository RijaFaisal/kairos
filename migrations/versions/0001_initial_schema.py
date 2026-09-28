"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2026-09-29 01:11:48.818064
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORDER_STATUS_EXISTING = postgresql.ENUM(
    'draft', 'awaiting_confirmation', 'confirmed', 'preparing', 'out_for_delivery',
    'delivered', 'cancelled', name='order_status', create_type=False,
)
ENUM_TYPES = ('order_status', 'payment_status', 'payment_method', 'message_direction', 'event_actor')


def upgrade() -> None:
    op.create_table('businesses',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('wa_phone_number_id', sa.Text(), nullable=False),
    sa.Column('owner_phones', postgresql.ARRAY(sa.Text()), server_default='{}', nullable=False),
    sa.Column('timezone', sa.Text(), server_default='Asia/Karachi', nullable=False),
    sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('wa_phone_number_id')
    )
    op.create_table('catalog_items',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('business_id', sa.BigInteger(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('aliases', postgresql.ARRAY(sa.Text()), server_default='{}', nullable=False),
    sa.Column('price', sa.Integer(), nullable=False),
    sa.Column('unit', sa.Text(), nullable=False),
    sa.Column('available', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('category', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('business_id', 'name')
    )
    op.create_index(op.f('ix_catalog_items_business_id'), 'catalog_items', ['business_id'], unique=False)
    op.create_table('customers',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('business_id', sa.BigInteger(), nullable=False),
    sa.Column('phone', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=True),
    sa.Column('default_address', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('business_id', 'phone')
    )
    op.create_index(op.f('ix_customers_business_id'), 'customers', ['business_id'], unique=False)
    op.create_table('conversations',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('business_id', sa.BigInteger(), nullable=False),
    sa.Column('customer_id', sa.BigInteger(), nullable=False),
    sa.Column('bot_paused', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('last_inbound_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('state', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('business_id', 'customer_id')
    )
    op.create_index(op.f('ix_conversations_business_id'), 'conversations', ['business_id'], unique=False)
    op.create_table('orders',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('business_id', sa.BigInteger(), nullable=False),
    sa.Column('customer_id', sa.BigInteger(), nullable=False),
    sa.Column('order_no', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('draft', 'awaiting_confirmation', 'confirmed', 'preparing', 'out_for_delivery', 'delivered', 'cancelled', name='order_status'), nullable=False),
    sa.Column('payment_status', sa.Enum('unpaid', 'paid', name='payment_status'), server_default='unpaid', nullable=False),
    sa.Column('payment_method', sa.Enum('cash', 'online', name='payment_method'), nullable=True),
    sa.Column('delivery_address', sa.Text(), nullable=True),
    sa.Column('delivery_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('total', sa.Integer(), server_default='0', nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('business_id', 'order_no')
    )
    op.create_index(op.f('ix_orders_business_id'), 'orders', ['business_id'], unique=False)
    op.create_index(op.f('ix_orders_customer_id'), 'orders', ['customer_id'], unique=False)
    op.create_table('messages',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('business_id', sa.BigInteger(), nullable=False),
    sa.Column('conversation_id', sa.BigInteger(), nullable=False),
    sa.Column('wa_message_id', sa.Text(), nullable=True),
    sa.Column('direction', sa.Enum('inbound', 'outbound', name='message_direction'), nullable=False),
    sa.Column('body', sa.Text(), nullable=True),
    sa.Column('raw', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('wa_message_id')
    )
    op.create_index(op.f('ix_messages_business_id'), 'messages', ['business_id'], unique=False)
    op.create_index(op.f('ix_messages_conversation_id'), 'messages', ['conversation_id'], unique=False)
    op.create_table('order_events',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('order_id', sa.BigInteger(), nullable=False),
    sa.Column('from_status', ORDER_STATUS_EXISTING, nullable=True),
    sa.Column('to_status', ORDER_STATUS_EXISTING, nullable=False),
    sa.Column('actor', sa.Enum('bot', 'owner', 'customer', name='event_actor'), nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_order_events_order_id'), 'order_events', ['order_id'], unique=False)
    op.create_table('order_items',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('order_id', sa.BigInteger(), nullable=False),
    sa.Column('catalog_item_id', sa.BigInteger(), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('unit_price', sa.Integer(), nullable=False),
    sa.Column('line_total', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['catalog_item_id'], ['catalog_items.id'], ),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_order_items_order_id'), 'order_items', ['order_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_order_items_order_id'), table_name='order_items')
    op.drop_table('order_items')
    op.drop_index(op.f('ix_order_events_order_id'), table_name='order_events')
    op.drop_table('order_events')
    op.drop_index(op.f('ix_messages_conversation_id'), table_name='messages')
    op.drop_index(op.f('ix_messages_business_id'), table_name='messages')
    op.drop_table('messages')
    op.drop_index(op.f('ix_orders_customer_id'), table_name='orders')
    op.drop_index(op.f('ix_orders_business_id'), table_name='orders')
    op.drop_table('orders')
    op.drop_index(op.f('ix_conversations_business_id'), table_name='conversations')
    op.drop_table('conversations')
    op.drop_index(op.f('ix_customers_business_id'), table_name='customers')
    op.drop_table('customers')
    op.drop_index(op.f('ix_catalog_items_business_id'), table_name='catalog_items')
    op.drop_table('catalog_items')
    op.drop_table('businesses')
    for name in ENUM_TYPES:
        op.execute(f'DROP TYPE IF EXISTS {name}')
