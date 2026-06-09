-- E-commerce BI initial Supabase schema.
-- Tables are in public for Data API access; RLS is enabled on every table.

CREATE SCHEMA IF NOT EXISTS app_private;
REVOKE ALL ON SCHEMA app_private FROM PUBLIC;

-- SKU Master Map (rebuilt from listing + channel item reports)
CREATE TABLE IF NOT EXISTS sku_master_map (
    style_id            BIGINT,
    myntra_seller_sku   TEXT,
    myntra_sku_code     TEXT,
    sku_id              BIGINT,
    uniware_sku         TEXT,
    internal_sku        TEXT,
    style_color         TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (style_id, myntra_seller_sku)
);
CREATE INDEX IF NOT EXISTS idx_sku_map_style_color ON sku_master_map(style_color);
CREATE INDEX IF NOT EXISTS idx_sku_map_style_id ON sku_master_map(style_id);
CREATE INDEX IF NOT EXISTS idx_sku_map_internal_sku ON sku_master_map(internal_sku);

-- SKU Master (one row per style_color, the primary decision grain)
CREATE TABLE IF NOT EXISTS sku_master (
    style_color         TEXT PRIMARY KEY,
    category_new        TEXT CHECK (
        category_new IS NULL OR category_new IN (
            'Discontinue',
            'OOS',
            'Winter',
            'Dog styles',
            'NOOS',
            'NOOS(Green)',
            'NOOS(Yellow)',
            'NOOS(Red)',
            'NOOS(OOS)',
            'NOOS(Potential)',
            'Green',
            'Yellow',
            'Red',
            'Dead',
            'Unknown',
            'Watchlist',
            'RED(Repeat)',
            'New Launch',
            'Potential NOOS',
            'Winter NOOS',
            'AW Styles',
            'Core Winter'
        )
    ),
    category_old        TEXT,
    sale_grade_old      TEXT,
    cross_category      TEXT,
    inventory_status    TEXT CHECK (inventory_status IS NULL OR inventory_status IN ('OOS','BROKEN','INSTOCK','UNKNOWN')),
    total_inventory     INTEGER DEFAULT 0,
    ros                 FLOAT DEFAULT 0,
    ros_7d              FLOAT DEFAULT 0,
    ros_30d             FLOAT DEFAULT 0,
    doi                 FLOAT DEFAULT 0,
    current_month_sales INTEGER DEFAULT 0,
    is_potential_noos   BOOLEAN DEFAULT FALSE,
    is_discontinue      BOOLEAN DEFAULT FALSE,
    is_dog_style        BOOLEAN DEFAULT FALSE,
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sku_master_category_new ON sku_master(category_new);
CREATE INDEX IF NOT EXISTS idx_sku_master_inventory_status ON sku_master(inventory_status);
CREATE INDEX IF NOT EXISTS idx_sku_master_doi ON sku_master(doi);

-- Category Overrides (manual approvals)
CREATE TABLE IF NOT EXISTS category_overrides (
    style_color         TEXT PRIMARY KEY REFERENCES sku_master(style_color) ON DELETE CASCADE,
    override_category   TEXT NOT NULL,
    override_by         TEXT,
    override_date       DATE DEFAULT CURRENT_DATE,
    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Sales Fact
CREATE TABLE IF NOT EXISTS sales_fact (
    id              BIGSERIAL PRIMARY KEY,
    date            DATE NOT NULL,
    internal_sku    TEXT,
    style_color     TEXT,
    channel         TEXT,
    marketplace     TEXT,
    selling_price   FLOAT,
    mrp             FLOAT,
    discount        FLOAT,
    qty             INTEGER DEFAULT 1,
    order_id        TEXT,
    order_status    TEXT,
    state           TEXT,
    city            TEXT,
    size            TEXT,
    style_id        BIGINT,
    source          TEXT CHECK (source IS NULL OR source IN ('myntra_orders','unicommerce','sales_master')),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(order_id, internal_sku)
);
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales_fact(date);
CREATE INDEX IF NOT EXISTS idx_sales_style_color ON sales_fact(style_color);
CREATE INDEX IF NOT EXISTS idx_sales_channel ON sales_fact(channel);
CREATE INDEX IF NOT EXISTS idx_sales_marketplace ON sales_fact(marketplace);
CREATE INDEX IF NOT EXISTS idx_sales_state ON sales_fact(state);
CREATE INDEX IF NOT EXISTS idx_sales_style_id ON sales_fact(style_id);

-- Returns Fact
CREATE TABLE IF NOT EXISTS returns_fact (
    id              BIGSERIAL PRIMARY KEY,
    date            DATE NOT NULL,
    internal_sku    TEXT,
    style_color     TEXT,
    channel         TEXT,
    qty             FLOAT DEFAULT 1,
    return_value    FLOAT,
    return_type     TEXT,
    order_id        TEXT,
    invoice_no      TEXT,
    state           TEXT,
    city            TEXT,
    source          TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT returns_fact_unique UNIQUE (order_id, internal_sku, date)
);
CREATE INDEX IF NOT EXISTS idx_returns_date ON returns_fact(date);
CREATE INDEX IF NOT EXISTS idx_returns_style_color ON returns_fact(style_color);
CREATE INDEX IF NOT EXISTS idx_returns_channel ON returns_fact(channel);
CREATE INDEX IF NOT EXISTS idx_returns_state ON returns_fact(state);

-- Inventory Fact (history, one row per style-color size per snapshot)
CREATE TABLE IF NOT EXISTS inventory_fact (
    snapshot_date   DATE NOT NULL,
    style_color     TEXT NOT NULL,
    size            TEXT NOT NULL,
    qty             INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (snapshot_date, style_color, size)
);
CREATE INDEX IF NOT EXISTS idx_inventory_style_color ON inventory_fact(style_color);
CREATE INDEX IF NOT EXISTS idx_inventory_snapshot_date ON inventory_fact(snapshot_date);

-- PLA Fact
CREATE TABLE IF NOT EXISTS pla_fact (
    id              BIGSERIAL PRIMARY KEY,
    upload_date     DATE,
    style_id        BIGINT,
    internal_sku    TEXT,
    style_color     TEXT,
    campaign_id     TEXT,
    campaign_name   TEXT,
    impressions     INTEGER,
    clicks          INTEGER,
    ctr             FLOAT,
    cvr             FLOAT,
    avg_cpc         FLOAT,
    spend           FLOAT,
    units_direct    INTEGER,
    units_indirect  INTEGER,
    revenue         FLOAT,
    roi             FLOAT,
    channel         TEXT DEFAULT 'Myntra',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_pla_upload_date ON pla_fact(upload_date);
CREATE INDEX IF NOT EXISTS idx_pla_style_color ON pla_fact(style_color);
CREATE INDEX IF NOT EXISTS idx_pla_campaign_id ON pla_fact(campaign_id);

-- Visibility Fact
CREATE TABLE IF NOT EXISTS visibility_fact (
    id                  BIGSERIAL PRIMARY KEY,
    period_start        DATE,
    period_end          DATE,
    style_id            BIGINT,
    internal_sku        TEXT,
    style_color         TEXT,
    mrp                 FLOAT,
    selling_price       FLOAT,
    discount_pct        FLOAT,
    units_sold          INTEGER,
    ros                 FLOAT,
    revenue             FLOAT,
    return_pct          FLOAT,
    consideration_pct   FLOAT,
    conversion_pct      FLOAT,
    list_page_count     INTEGER,
    pdp_count           INTEGER,
    channel             TEXT DEFAULT 'Myntra',
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_visibility_period ON visibility_fact(period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_visibility_style_color ON visibility_fact(style_color);
CREATE INDEX IF NOT EXISTS idx_visibility_style_id ON visibility_fact(style_id);

-- Replenishment Log
CREATE TABLE IF NOT EXISTS replenishment_log (
    id                  BIGSERIAL PRIMARY KEY,
    style_color         TEXT,
    replenishment_qty   INTEGER,
    replenishment_date  DATE DEFAULT CURRENT_DATE,
    uploaded_by         TEXT,
    notes               TEXT,
    status              TEXT DEFAULT 'planned',
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_replenishment_style_color ON replenishment_log(style_color);
CREATE INDEX IF NOT EXISTS idx_replenishment_date ON replenishment_log(replenishment_date);

-- User Roles. Supabase Auth owns authentication; this table owns app roles.
CREATE TABLE IF NOT EXISTS user_roles (
    user_id     UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email       TEXT UNIQUE NOT NULL,
    name        TEXT,
    role        TEXT DEFAULT 'viewer' CHECK (role IN ('super_admin','admin','manager','analyst','md','viewer')),
    is_active   BOOLEAN DEFAULT TRUE,
    last_login  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_user_roles_email ON user_roles(email);
CREATE INDEX IF NOT EXISTS idx_user_roles_role ON user_roles(role);

-- Upload Log
CREATE TABLE IF NOT EXISTS upload_log (
    id              BIGSERIAL PRIMARY KEY,
    file_type       TEXT CHECK (
        file_type IS NULL OR file_type IN (
            'myntra_orders',
            'unicommerce',
            'sales_master',
            'inventory',
            'pla',
            'visibility',
            'returns',
            'replenishment',
            'sku_mapping',
            'sale_grade_master'
        )
    ),
    file_name       TEXT,
    rows_processed  INTEGER DEFAULT 0,
    rows_inserted   INTEGER DEFAULT 0,
    rows_skipped    INTEGER DEFAULT 0,
    uploaded_by     TEXT,
    status          TEXT DEFAULT 'success',
    error_msg       TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_upload_log_file_type ON upload_log(file_type);
CREATE INDEX IF NOT EXISTS idx_upload_log_created_at ON upload_log(created_at);

CREATE OR REPLACE FUNCTION app_private.has_app_role(allowed_roles TEXT[])
RETURNS BOOLEAN
LANGUAGE SQL
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.user_roles
        WHERE user_id = auth.uid()
          AND is_active = TRUE
          AND role = ANY (allowed_roles)
    );
$$;

GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated;

ALTER TABLE sku_master_map ENABLE ROW LEVEL SECURITY;
ALTER TABLE sku_master ENABLE ROW LEVEL SECURITY;
ALTER TABLE category_overrides ENABLE ROW LEVEL SECURITY;
ALTER TABLE sales_fact ENABLE ROW LEVEL SECURITY;
ALTER TABLE returns_fact ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory_fact ENABLE ROW LEVEL SECURITY;
ALTER TABLE pla_fact ENABLE ROW LEVEL SECURITY;
ALTER TABLE visibility_fact ENABLE ROW LEVEL SECURITY;
ALTER TABLE replenishment_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE upload_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated users can read sku map"
ON sku_master_map FOR SELECT TO authenticated
USING (TRUE);
CREATE POLICY "Admins can write sku map"
ON sku_master_map FOR ALL TO authenticated
USING (app_private.has_app_role(ARRAY['super_admin','admin']))
WITH CHECK (app_private.has_app_role(ARRAY['super_admin','admin']));

CREATE POLICY "Authenticated users can read sku master"
ON sku_master FOR SELECT TO authenticated
USING (TRUE);
CREATE POLICY "Managers can write sku master"
ON sku_master FOR ALL TO authenticated
USING (app_private.has_app_role(ARRAY['super_admin','admin','manager']))
WITH CHECK (app_private.has_app_role(ARRAY['super_admin','admin','manager']));

CREATE POLICY "Authenticated users can read category overrides"
ON category_overrides FOR SELECT TO authenticated
USING (TRUE);
CREATE POLICY "Managers can write category overrides"
ON category_overrides FOR ALL TO authenticated
USING (app_private.has_app_role(ARRAY['super_admin','admin','manager']))
WITH CHECK (app_private.has_app_role(ARRAY['super_admin','admin','manager']));

CREATE POLICY "Authenticated users can read sales facts"
ON sales_fact FOR SELECT TO authenticated
USING (TRUE);
CREATE POLICY "Admins can write sales facts"
ON sales_fact FOR ALL TO authenticated
USING (app_private.has_app_role(ARRAY['super_admin','admin']))
WITH CHECK (app_private.has_app_role(ARRAY['super_admin','admin']));

CREATE POLICY "Authenticated users can read returns facts"
ON returns_fact FOR SELECT TO authenticated
USING (TRUE);
CREATE POLICY "Admins can write returns facts"
ON returns_fact FOR ALL TO authenticated
USING (app_private.has_app_role(ARRAY['super_admin','admin']))
WITH CHECK (app_private.has_app_role(ARRAY['super_admin','admin']));

CREATE POLICY "Authenticated users can read inventory"
ON inventory_fact FOR SELECT TO authenticated
USING (TRUE);
CREATE POLICY "Admins can write inventory"
ON inventory_fact FOR ALL TO authenticated
USING (app_private.has_app_role(ARRAY['super_admin','admin']))
WITH CHECK (app_private.has_app_role(ARRAY['super_admin','admin']));

CREATE POLICY "Authenticated users can read pla"
ON pla_fact FOR SELECT TO authenticated
USING (TRUE);
CREATE POLICY "Admins can write pla"
ON pla_fact FOR ALL TO authenticated
USING (app_private.has_app_role(ARRAY['super_admin','admin']))
WITH CHECK (app_private.has_app_role(ARRAY['super_admin','admin']));

CREATE POLICY "Authenticated users can read visibility"
ON visibility_fact FOR SELECT TO authenticated
USING (TRUE);
CREATE POLICY "Admins can write visibility"
ON visibility_fact FOR ALL TO authenticated
USING (app_private.has_app_role(ARRAY['super_admin','admin']))
WITH CHECK (app_private.has_app_role(ARRAY['super_admin','admin']));

CREATE POLICY "Authenticated users can read replenishment"
ON replenishment_log FOR SELECT TO authenticated
USING (TRUE);
CREATE POLICY "Managers can write replenishment"
ON replenishment_log FOR ALL TO authenticated
USING (app_private.has_app_role(ARRAY['super_admin','admin','manager']))
WITH CHECK (app_private.has_app_role(ARRAY['super_admin','admin','manager']));

CREATE POLICY "Users can read own role"
ON user_roles FOR SELECT TO authenticated
USING (user_id = auth.uid() OR app_private.has_app_role(ARRAY['super_admin','admin']));
CREATE POLICY "Admins can manage user roles"
ON user_roles FOR ALL TO authenticated
USING (app_private.has_app_role(ARRAY['super_admin','admin']))
WITH CHECK (app_private.has_app_role(ARRAY['super_admin','admin']));

CREATE POLICY "Authenticated users can read upload log"
ON upload_log FOR SELECT TO authenticated
USING (TRUE);
CREATE POLICY "Admins can write upload log"
ON upload_log FOR ALL TO authenticated
USING (app_private.has_app_role(ARRAY['super_admin','admin']))
WITH CHECK (app_private.has_app_role(ARRAY['super_admin','admin']));
