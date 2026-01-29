/**
 * Supabase client configuration for the frontend
 */
import { createClient } from '@supabase/supabase-js';

// Get environment variables with fallbacks for development
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'https://your-project.supabase.co';
const supabaseKey = import.meta.env.VITE_SUPABASE_KEY || 'your-anon-key';

// Validate environment variables
if (!supabaseUrl || !supabaseKey) {
  console.error('Missing Supabase environment variables!');
  console.error('VITE_SUPABASE_URL:', supabaseUrl ? 'Set' : 'Missing');
  console.error('VITE_SUPABASE_KEY:', supabaseKey ? 'Set' : 'Missing');
}

// Create Supabase client
export const supabase = createClient(supabaseUrl, supabaseKey, {
  auth: {
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: true
  },
  realtime: {
    params: {
      eventsPerSecond: 10
    }
  }
});

// Helper function to check if user is authenticated
export const isAuthenticated = async () => {
  const { data: { session } } = await supabase.auth.getSession();
  return !!session;
};

// Helper function to get current user
export const getCurrentUser = async () => {
  const { data: { user } } = await supabase.auth.getUser();
  return user;
};

// Helper function to sign in
export const signIn = async (email, password) => {
  const { data, error } = await supabase.auth.signInWithPassword({
    email,
    password
  });
  
  if (error) throw error;
  return data;
};

// Helper function to sign out
export const signOut = async () => {
  const { error } = await supabase.auth.signOut();
  if (error) throw error;
};

// Subscribe to real-time changes
export const subscribeToAuditLogs = (callback) => {
  return supabase
    .channel('audit-logs-channel')
    .on(
      'postgres_changes',
      {
        event: 'INSERT',
        schema: 'public',
        table: 'audit_logs'
      },
      (payload) => {
        callback(payload.new);
      }
    )
    .subscribe();
};

// Fetch recent audit logs
export const fetchRecentAuditLogs = async (limit = 50) => {
  const { data, error } = await supabase
    .from('audit_logs')
    .select('*')
    .order('created_at', { ascending: false })
    .limit(limit);
  
  if (error) throw error;
  return data;
};

// Fetch active policies
export const fetchActivePolicies = async () => {
  const { data, error } = await supabase
    .from('policies')
    .select('*')
    .eq('is_active', true)
    .order('created_at', { ascending: false });
  
  if (error) throw error;
  return data;
};

// Create new policy
export const createPolicy = async (policyData) => {
  const { data, error } = await supabase
    .from('policies')
    .insert([policyData])
    .select();
  
  if (error) throw error;
  return data[0];
};

// Update policy
export const updatePolicy = async (id, updates) => {
  const { data, error } = await supabase
    .from('policies')
    .update(updates)
    .eq('id', id)
    .select();
  
  if (error) throw error;
  return data[0];
};

// Get system metrics
export const getSystemMetrics = async () => {
  try {
    // Try to call backend API
    const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';
    const response = await fetch(`${backendUrl}/metrics`);
    
    if (!response.ok) {
      throw new Error(`Backend API returned ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Failed to fetch metrics from backend:', error);
    
    // Fallback to direct Supabase queries
    const [totalRes, allowRes, blockRes, flagRes, policiesRes] = await Promise.all([
      supabase.from('audit_logs').select('count', { count: 'exact', head: true }),
      supabase.from('audit_logs').select('count', { count: 'exact', head: true }).eq('decision', 'ALLOW'),
      supabase.from('audit_logs').select('count', { count: 'exact', head: true }).eq('decision', 'BLOCK'),
      supabase.from('audit_logs').select('count', { count: 'exact', head: true }).eq('decision', 'FLAG'),
      supabase.from('policies').select('count', { count: 'exact', head: true }).eq('is_active', true)
    ]);
    
    const total = totalRes.count || 0;
    const allowCount = allowRes.count || 0;
    const blockCount = blockRes.count || 0;
    const flagCount = flagRes.count || 0;
    const activePolicies = policiesRes.count || 0;
    
    return {
      metrics: {
        total_decisions: total,
        allow_count: allowCount,
        block_count: blockCount,
        flag_count: flagCount,
        allow_rate: total > 0 ? allowCount / total : 0,
        block_rate: total > 0 ? blockCount / total : 0,
        flag_rate: total > 0 ? flagCount / total : 0,
        active_policies: activePolicies
      }
    };
  }
};