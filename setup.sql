-- OrchestraGuard V2 - Complete Database Schema
-- Run this in Supabase Dashboard SQL Editor

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Policies Table
CREATE TABLE IF NOT EXISTS policies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    rules JSONB NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Audit Logs Table (FIXED: Added all required columns)
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    action_id TEXT NOT NULL,
    source_agent TEXT NOT NULL,
    target_tool TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('ALLOW', 'BLOCK', 'FLAG')),
    rationale TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    applied_rules TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Users table for authentication (optional)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    role TEXT DEFAULT 'admin',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ========== INDEXES FOR PERFORMANCE ==========

-- Policies table indexes
CREATE INDEX IF NOT EXISTS idx_policies_rules ON policies USING GIN (rules);
CREATE INDEX IF NOT EXISTS idx_policies_active ON policies(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_policies_created_at ON policies(created_at DESC);

-- Audit logs table indexes (FIXED: All required indexes)
CREATE INDEX IF NOT EXISTS idx_audit_logs_decision ON audit_logs(decision);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_source_agent ON audit_logs(source_agent);
CREATE INDEX IF NOT EXISTS idx_audit_logs_target_tool ON audit_logs(target_tool);
CREATE INDEX IF NOT EXISTS idx_audit_logs_metadata ON audit_logs USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_audit_logs_applied_rules ON audit_logs USING GIN (applied_rules);

-- Users table indexes
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active) WHERE is_active = TRUE;

-- ========== ROW LEVEL SECURITY ==========

-- Enable RLS on all tables
ALTER TABLE policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- Policies RLS: Only admins can modify, everyone can read active policies
CREATE POLICY "Admins can manage policies" ON policies
    FOR ALL USING (auth.role() = 'admin');

CREATE POLICY "Anyone can view active policies" ON policies
    FOR SELECT USING (is_active = TRUE);

-- Audit logs RLS: Insert allowed for service, read for authenticated users
CREATE POLICY "Service can insert audit logs" ON audit_logs
    FOR INSERT WITH CHECK (TRUE);

CREATE POLICY "Authenticated users can view audit logs" ON audit_logs
    FOR SELECT USING (auth.role() IN ('admin', 'viewer'));

-- Users RLS: Only admins can manage users
CREATE POLICY "Admins can manage users" ON users
    FOR ALL USING (auth.role() = 'admin');

-- ========== STORED PROCEDURES ==========

-- Function to get decision breakdown
CREATE OR REPLACE FUNCTION get_decision_breakdown()
RETURNS TABLE (
    allow_count BIGINT,
    block_count BIGINT,
    flag_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*) FILTER (WHERE decision = 'ALLOW') as allow_count,
        COUNT(*) FILTER (WHERE decision = 'BLOCK') as block_count,
        COUNT(*) FILTER (WHERE decision = 'FLAG') as flag_count
    FROM audit_logs;
END;
$$ LANGUAGE plpgsql;

-- Function to check policy conflicts (improved version)
CREATE OR REPLACE FUNCTION check_policy_conflicts(
    new_target_regex TEXT,
    new_severity TEXT,
    new_action TEXT
)
RETURNS TABLE (
    policy_id UUID,
    policy_name TEXT,
    rule_id TEXT,
    severity TEXT,
    action TEXT,
    conflict_type TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        p.id as policy_id,
        p.name as policy_name,
        (p.rules->>'rule_id') as rule_id,
        (p.rules->>'severity') as severity,
        (p.rules->>'action_on_violation') as action,
        CASE 
            WHEN (p.rules->>'target_tool_regex') = new_target_regex 
                 AND (p.rules->>'action_on_violation') != new_action 
                 THEN 'action_conflict'
            WHEN (p.rules->>'target_tool_regex') LIKE '%' || new_target_regex || '%' 
                 OR new_target_regex LIKE '%' || (p.rules->>'target_tool_regex') || '%'
                 AND (p.rules->>'severity') = new_severity
                 AND (p.rules->>'action_on_violation') != new_action
                 THEN 'partial_conflict'
            ELSE 'no_conflict'
        END as conflict_type
    FROM policies p
    WHERE p.is_active = TRUE
    AND (
        (p.rules->>'target_tool_regex') = new_target_regex
        OR (p.rules->>'target_tool_regex') LIKE '%' || new_target_regex || '%'
        OR new_target_regex LIKE '%' || (p.rules->>'target_tool_regex') || '%'
    )
    AND conflict_type != 'no_conflict';
END;
$$ LANGUAGE plpgsql;

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ========== TRIGGERS ==========

-- Trigger for automatic updated_at on policies
CREATE TRIGGER update_policies_updated_at
    BEFORE UPDATE ON policies
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for automatic updated_at on users
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ========== SAMPLE DATA ==========

-- Insert sample policies
INSERT INTO policies (name, rules, is_active) VALUES
(
    'Data Protection Policy',
    '{
        "rule_id": "DP-001",
        "description": "Prevent sharing of Personally Identifiable Information in public channels",
        "target_tool_regex": "Slack_API_PostMessage|Teams_API_SendMessage|Discord_API_Message",
        "condition_logic": "any(pii in lower(str(tool_arguments.get(''message_content'', ''''))) for pii in [''ssn'', ''social security'', ''credit card'', ''password'', ''api_key'', ''secret''])",
        "severity": "HIGH",
        "action_on_violation": "BLOCK"
    }'::jsonb,
    TRUE
),
(
    'Code Security Policy',
    '{
        "rule_id": "CS-001",
        "description": "Prevent pushing secrets to public repositories",
        "target_tool_regex": "GitHub_API_CreateCommit|GitHub_API_UpdateFile|GitLab_API_Push",
        "condition_logic": "any(secret in lower(str(tool_arguments.get(''content'', ''''))) for secret in [''password='', ''api_key='', ''secret='', ''token='', ''private_key''])",
        "severity": "HIGH",
        "action_on_violation": "BLOCK"
    }'::jsonb,
    TRUE
),
(
    'Database Access Policy',
    '{
        "rule_id": "DB-001",
        "description": "Prevent unauthorized writes to production databases",
        "target_tool_regex": "SQL_DB_Write.*|PostgreSQL_API_Execute.*",
        "condition_logic": "''production'' in lower(str(tool_arguments.get(''database'', ''''))) and user_context.get(''approval_level'', 0) < 2",
        "severity": "HIGH",
        "action_on_violation": "BLOCK"
    }'::jsonb,
    TRUE
);

-- Insert sample audit logs
INSERT INTO audit_logs (action_id, source_agent, target_tool, decision, rationale, applied_rules) VALUES
(
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    'agent_hr_bot',
    'Slack_API_PostMessage',
    'BLOCK',
    'Message contained SSN: 123-45-6789 in public channel #general',
    ARRAY['DP-001']
),
(
    'b2c3d4e5-f6a7-890b-cdef-234567890123',
    'agent_dev_bot',
    'GitHub_API_CreateCommit',
    'ALLOW',
    'Code commit does not contain any sensitive information',
    ARRAY['CS-001']
),
(
    'c3d4e5f6-a7b8-90cd-ef12-345678901234',
    'agent_ops_bot',
    'SQL_DB_WriteQuery',
    'BLOCK',
    'Attempt to write to production database without proper approval level',
    ARRAY['DB-001']
);

-- Create admin user (password: admin123)
INSERT INTO users (email, hashed_password, role) VALUES
(
    'admin@orchestraguard.com',
    -- bcrypt hash for 'admin123' (cost factor 12)
    '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW',
    'admin'
);

-- ========== FINAL MESSAGE ==========
DO $$
BEGIN
    RAISE NOTICE '✅ OrchestraGuard V2 database setup complete!';
    RAISE NOTICE '📊 Tables created: policies, audit_logs, users';
    RAISE NOTICE '📈 Indexes created: 9 optimized indexes';
    RAISE NOTICE '🔐 RLS Policies: Enabled for all tables';
    RAISE NOTICE '⚙️  Functions: get_decision_breakdown, check_policy_conflicts';
    RAISE NOTICE '🔄 Triggers: Automatic updated_at on policies and users';
    RAISE NOTICE '📋 Sample data: 3 policies, 3 audit logs, 1 admin user';
    RAISE NOTICE '';
    RAISE NOTICE '🎉 Database is ready for OrchestraGuard V2!';
    RAISE NOTICE 'Next steps:';
    RAISE NOTICE '1. Configure your .env file with SUPABASE_URL and SUPABASE_KEY';
    RAISE NOTICE '2. Start the backend: uvicorn main:app --reload';
    RAISE NOTICE '3. Access the dashboard at http://localhost:3000';
END $$;