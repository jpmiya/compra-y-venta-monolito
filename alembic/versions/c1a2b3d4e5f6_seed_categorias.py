"""seed categorias

Revision ID: c1a2b3d4e5f6
Revises: b946013361d1
Create Date: 2026-04-30

"""
from alembic import op
import sqlalchemy as sa

revision = 'c1a2b3d4e5f6'
down_revision = 'b946013361d1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO categorias (id, nombre, descripcion, imagen)
        VALUES
          (gen_random_uuid(), 'Electrónica',       'Computadoras, celulares y accesorios', NULL),
          (gen_random_uuid(), 'Ropa y Calzado',    'Indumentaria y accesorios de moda',    NULL),
          (gen_random_uuid(), 'Hogar y Muebles',   'Decoración, electrodomésticos, muebles', NULL),
          (gen_random_uuid(), 'Deportes',          'Equipamiento deportivo',               NULL),
          (gen_random_uuid(), 'Libros y Educación','Libros, cursos y material educativo',  NULL),
          (gen_random_uuid(), 'Juguetes',          'Juguetes y artículos infantiles',      NULL),
          (gen_random_uuid(), 'Alimentos',         'Productos alimenticios y bebidas',     NULL),
          (gen_random_uuid(), 'Otros',             'Artículos varios',                     NULL)
        ON CONFLICT DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("DELETE FROM categorias WHERE nombre IN ('Electrónica','Ropa y Calzado','Hogar y Muebles','Deportes','Libros y Educación','Juguetes','Alimentos','Otros');")
