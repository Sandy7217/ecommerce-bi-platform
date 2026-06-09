CREATE TABLE IF NOT EXISTS targets (
    id BIGSERIAL PRIMARY KEY,
    month DATE NOT NULL,
    channel TEXT NOT NULL DEFAULT 'ALL',
    target_value BIGINT NOT NULL,
    target_qty INTEGER,
    created_by TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(month, channel)
);

CREATE INDEX IF NOT EXISTS idx_targets_month ON targets(month);
CREATE INDEX IF NOT EXISTS idx_targets_channel ON targets(channel);

INSERT INTO targets (month, channel, target_value, target_qty)
VALUES ('2026-05-01', 'ALL', 50000000, 0)
ON CONFLICT (month, channel) DO UPDATE
SET target_value = EXCLUDED.target_value,
    target_qty = EXCLUDED.target_qty;
