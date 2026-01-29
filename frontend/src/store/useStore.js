/**
 * FIXED: Zustand store with configurable API paths
 */
import { create } from 'zustand';
import { supabase } from '../lib/supabase';

// Get API base URL from environment variable
const API_BASE_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

const useStore = create((set, get) => ({
  // State
  auditLogs: [],
  policies: [],
  metrics: {
    totalDecisions: 0,
    allowRate: 0,
    blockRate: 0,
    flagRate: 0,
    activePolicies: 0,
  },
  realtimeConnected: false,
  isLoading: false,
  error: null,

  // Actions
  fetchAuditLogs: async (limit = 100) => {
    set({ isLoading: true, error: null });
    try {
      const { data, error } = await supabase
        .from('audit_logs')
        .select('*')
        .order('created_at', { ascending: false })
        .limit(limit);

      if (error) throw error;
      set({ auditLogs: data, isLoading: false });
    } catch (error) {
      set({ error: error.message, isLoading: false });
    }
  },

  fetchPolicies: async () => {
    set({ isLoading: true });
    try {
      const { data, error } = await supabase
        .from('policies')
        .select('*')
        .eq('is_active', true)
        .order('created_at', { ascending: false });

      if (error) throw error;
      set({ policies: data, isLoading: false });
    } catch (error) {
      set({ error: error.message, isLoading: false });
    }
  },

  fetchMetrics: async () => {
    try {
      // FIXED: Use configurable API base URL
      const response = await fetch(`${API_BASE_URL}/metrics`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token') || ''}`
        }
      });
      
      if (!response.ok) {
        throw new Error(`Failed to fetch metrics: ${response.status}`);
      }
      
      const data = await response.json();
      set({ metrics: data.metrics });
    } catch (error) {
      console.error('Failed to fetch metrics:', error);
      // Fallback to direct database query
      const { getSystemMetrics } = await import('../lib/supabase');
      const data = await getSystemMetrics();
      set({ metrics: data.metrics });
    }
  },

  subscribeToRealtime: () => {
    // Subscribe to audit log inserts
    const subscription = supabase
      .channel('audit-logs')
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'audit_logs',
        },
        (payload) => {
          // Prepend new log to existing logs
          set((state) => ({
            auditLogs: [payload.new, ...state.auditLogs.slice(0, 99)],
          }));
          
          // Update metrics
          get().updateMetricsOnNewLog(payload.new);
        }
      )
      .subscribe((status) => {
        set({ realtimeConnected: status === 'SUBSCRIBED' });
      });

    return () => {
      subscription.unsubscribe();
      set({ realtimeConnected: false });
    };
  },

  updateMetricsOnNewLog: (newLog) => {
    set((state) => {
      const total = state.metrics.totalDecisions + 1;
      const decision = newLog.decision;
      
      const newMetrics = { ...state.metrics, totalDecisions: total };
      
      // Update rates based on decision type
      switch (decision) {
        case 'ALLOW':
          newMetrics.allowRate = ((state.metrics.allowRate * state.metrics.totalDecisions) + 1) / total;
          newMetrics.allowCount = (state.metrics.allowCount || 0) + 1;
          break;
        case 'BLOCK':
          newMetrics.blockRate = ((state.metrics.blockRate * state.metrics.totalDecisions) + 1) / total;
          newMetrics.blockCount = (state.metrics.blockCount || 0) + 1;
          break;
        case 'FLAG':
          newMetrics.flagRate = ((state.metrics.flagRate * state.metrics.totalDecisions) + 1) / total;
          newMetrics.flagCount = (state.metrics.flagCount || 0) + 1;
          break;
      }
      
      return { metrics: newMetrics };
    });
  },

  createPolicy: async (policyData) => {
    set({ isLoading: true });
    try {
      // FIXED: Use configurable API base URL
      const response = await fetch(`${API_BASE_URL}/policy/analyze`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token') || ''}`
        },
        body: JSON.stringify(policyData),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create policy');
      }
      
      const result = await response.json();
      
      // Refresh policies after successful creation
      if (result.status === 'success') {
        await get().fetchPolicies();
      }
      
      set({ isLoading: false });
      return result;
    } catch (error) {
      set({ error: error.message, isLoading: false });
      return { status: 'error', message: error.message };
    }
  },

  updatePolicy: async (id, updates) => {
    set({ isLoading: true });
    try {
      const { error } = await supabase
        .from('policies')
        .update(updates)
        .eq('id', id);

      if (error) throw error;
      
      await get().fetchPolicies();
      set({ isLoading: false });
      return true;
    } catch (error) {
      set({ error: error.message, isLoading: false });
      return false;
    }
  },

  testInterception: async (interceptionData) => {
    set({ isLoading: true });
    try {
      // FIXED: Use configurable API base URL
      const response = await fetch(`${API_BASE_URL}/intercept`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token') || ''}`
        },
        body: JSON.stringify(interceptionData),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to test interception');
      }
      
      const result = await response.json();
      set({ isLoading: false });
      return result;
    } catch (error) {
      set({ error: error.message, isLoading: false });
      return { error: error.message };
    }
  },

  // Utility selectors
  getRecentBlocks: () => {
    const logs = get().auditLogs;
    return logs.filter(log => log.decision === 'BLOCK').slice(0, 10);
  },

  getDecisionStats: () => {
    const logs = get().auditLogs;
    const total = logs.length;
    if (total === 0) return { allow: 0, block: 0, flag: 0 };
    
    return {
      allow: logs.filter(log => log.decision === 'ALLOW').length / total,
      block: logs.filter(log => log.decision === 'BLOCK').length / total,
      flag: logs.filter(log => log.decision === 'FLAG').length / total,
    };
  },
}));

export default useStore;