"""Add video signing columns and vehicle data columns to tickets.

- video_signature: RSA-PSS signature hex of processed video
- video_signature_key: public key fingerprint
- video_signed_at: when the signature was created
- vehicle_type: car type from registry (e.g. 'sedan', 'suv')
- vehicle_color: colour from registry
- vehicle_year: year of manufacturing from registry
- violation_rules: per-camera violation_rules column on cameras (if missing)
- violation_zone on cameras (if missing)
- violation_rules table (if missing)
"""
from alembic import op
from sqlalchemy import text

revision = "20260315_0004"
down_revision = "20260314_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # --- Tickets: digital signature columns ---
    conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS video_signature TEXT"))
    conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS video_signature_key VARCHAR(50)"))
    conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS video_signed_at TIMESTAMP WITH TIME ZONE"))

    # --- Tickets: vehicle data from registry ---
    conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS vehicle_type VARCHAR(100)"))
    conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS vehicle_color VARCHAR(100)"))
    conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS vehicle_year INTEGER"))
    conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS vehicle_make VARCHAR(100)"))
    conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS vehicle_model VARCHAR(100)"))

    # --- Cameras: violation_rules and violation_zone (may already exist) ---
    conn.execute(text("ALTER TABLE cameras ADD COLUMN IF NOT EXISTS violation_rules JSONB"))
    conn.execute(text("ALTER TABLE cameras ADD COLUMN IF NOT EXISTS violation_zone VARCHAR(20)"))

    # --- violation_rules table ---
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS violation_rules (
            id SERIAL PRIMARY KEY,
            rule_id VARCHAR(30) UNIQUE NOT NULL,
            title_he VARCHAR(200) NOT NULL,
            title_en VARCHAR(200) NOT NULL,
            description_he TEXT,
            description_en TEXT,
            legal_basis_he TEXT,
            legal_basis_en TEXT,
            fine_ils INTEGER,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        )
    """))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_violation_rules_rule_id ON violation_rules (rule_id)"))


def downgrade() -> None:
    pass  # columns are safe to leave in place
