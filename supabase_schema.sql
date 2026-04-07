-- Newsletter SaaS - Supabase Schema
-- Run this in Supabase SQL Editor

-- 1. Runs table (pipeline execution history)
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  countries JSONB DEFAULT '["KR","RU","VN","TH","PH","PK"]',
  date_str TEXT,
  status TEXT DEFAULT 'pending',
  current_phase TEXT DEFAULT '',
  phase_status JSONB DEFAULT '{}',
  errors JSONB DEFAULT '[]',
  newsletter_html JSONB DEFAULT '{}',
  audit_iterations INTEGER DEFAULT 0,
  total_collected INTEGER DEFAULT 0,
  total_filtered INTEGER DEFAULT 0,
  total_sent INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

-- 2. Settings table (schedule + recipients)
CREATE TABLE IF NOT EXISTS settings (
  id SERIAL PRIMARY KEY,
  frequency TEXT DEFAULT 'weekly',
  day_of_week TEXT DEFAULT 'Tuesday',
  time TEXT DEFAULT '09:00',
  countries JSONB DEFAULT '["KR","RU","VN","TH","PH","PK"]',
  is_active BOOLEAN DEFAULT true,
  country_recipients JSONB DEFAULT '[]',
  days INTEGER DEFAULT 30,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Run logs table (detailed phase logs)
CREATE TABLE IF NOT EXISTS run_logs (
  id SERIAL PRIMARY KEY,
  run_id TEXT REFERENCES runs(id),
  phase TEXT,
  level TEXT DEFAULT 'info',
  message TEXT,
  data JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS but allow all for now (service role)
ALTER TABLE runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE run_logs ENABLE ROW LEVEL SECURITY;

-- Allow all operations (anon key)
CREATE POLICY "Allow all on runs" ON runs FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all on settings" ON settings FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all on run_logs" ON run_logs FOR ALL USING (true) WITH CHECK (true);

-- Insert default settings
INSERT INTO settings (frequency, day_of_week, time, countries, is_active, days)
VALUES ('weekly', 'Tuesday', '09:00', '["KR","RU","VN","TH","PH","PK"]', true, 30)
ON CONFLICT DO NOTHING;
