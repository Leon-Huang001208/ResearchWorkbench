ALTER TABLE hot.model_budgets ADD COLUMN daily_max_calls integer NOT NULL DEFAULT 0 CHECK(daily_max_calls>=0);
ALTER TABLE hot.model_budgets ADD COLUMN daily_max_tokens bigint NOT NULL DEFAULT 0 CHECK(daily_max_tokens>=0);
ALTER TABLE hot.model_budgets ADD COLUMN daily_max_cost_micros bigint NOT NULL DEFAULT 0 CHECK(daily_max_cost_micros>=0);
ALTER TABLE hot.model_budgets ADD COLUMN quota_timezone text NOT NULL DEFAULT 'Asia/Shanghai';
ALTER TABLE hot.model_attempts ADD COLUMN day_key date NOT NULL DEFAULT (clock_timestamp() AT TIME ZONE 'Asia/Shanghai')::date;
ALTER TABLE hot.model_receipts ADD COLUMN cost_basis text NOT NULL DEFAULT 'provider'
CHECK(cost_basis IN ('provider','tariff-ceiling','synthetic'));
