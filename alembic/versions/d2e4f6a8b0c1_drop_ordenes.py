"""drop ordenes (deuda tecnica, fuera del alcance de microservicios)

Revision ID: d2e4f6a8b0c1
Revises: c1a2b3d4e5f6
Create Date: 2026-07-16

Elimina el modulo `ordenes` (tablas `orden_items` y `ordenes`). No forma parte
del diseño de microservicios y acoplaba admin+carrito+productos. Ver
PLAN_MIGRACION_MICROSERVICIOS.md §7.
"""
from alembic import op
import sqlalchemy as sa


revision = 'd2e4f6a8b0c1'
down_revision = 'c1a2b3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table('orden_items')
    op.drop_index(op.f('ix_ordenes_usuario_id'), table_name='ordenes')
    op.drop_index(op.f('ix_ordenes_numero_orden'), table_name='ordenes')
    op.drop_table('ordenes')
    op.execute("DROP TYPE IF EXISTS estado_orden_enum")


def downgrade() -> None:
    op.create_table(
        'ordenes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('numero_orden', sa.String(length=50), nullable=False),
        sa.Column('usuario_id', sa.UUID(), nullable=False),
        sa.Column('subtotal', sa.Float(), nullable=False),
        sa.Column('impuesto', sa.Float(), nullable=False),
        sa.Column('descuento', sa.Float(), nullable=False),
        sa.Column('total', sa.Float(), nullable=False),
        sa.Column(
            'estado',
            sa.Enum('pendiente', 'pagada', 'procesando', 'enviada', 'entregada',
                    'cancelada', name='estado_orden_enum'),
            nullable=False,
        ),
        sa.Column('direccion_entrega', sa.String(length=255), nullable=False),
        sa.Column('telefono_contacto', sa.String(length=20), nullable=False),
        sa.Column('numero_seguimiento', sa.String(length=100), nullable=True),
        sa.Column('fecha_creacion', sa.DateTime(timezone=True), nullable=False),
        sa.Column('fecha_actualizacion', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ordenes_numero_orden'), 'ordenes', ['numero_orden'], unique=True)
    op.create_index(op.f('ix_ordenes_usuario_id'), 'ordenes', ['usuario_id'], unique=False)
    op.create_table(
        'orden_items',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('orden_id', sa.UUID(), nullable=False),
        sa.Column('producto_id', sa.UUID(), nullable=False),
        sa.Column('nombre_producto', sa.String(length=255), nullable=False),
        sa.Column('cantidad', sa.Integer(), nullable=False),
        sa.Column('precio_unitario', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['orden_id'], ['ordenes.id'], ),
        sa.ForeignKeyConstraint(['producto_id'], ['productos.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
