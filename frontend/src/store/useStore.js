/**
 * Zustand store for OrchestraGuard Frontend
 * Lightweight, non-boilerplate state management
 */
import { create } from 'zustand';
import { supabase } from '../lib/supabase';

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
      // Fetch metrics from backend API
      const response = await fetch('/api/metrics');
      const metrics = await response.json();
      set({ metrics });
    } catch (error) {
      console.error('Failed to fetch metrics:', error);
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
      .subscribe();

    set({ realtimeConnected: true });
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
          break;
        case 'BLOCK':
          newMetrics.blockRate = ((state.metrics.blockRate * state.metrics.totalDecisions) + 1) / total;
          break;
        case 'FLAG':
          newMetrics.flagRate = ((state.metrics.flagRate * state.metrics.totalDecisions) + 1) / total;
          break;
      }
      
      return { metrics: newMetrics };
    });
  },

  createPolicy: async (policyData) => {
    set({ isLoading: true });
    try {
      const response = await fetch('/api/policies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(policyData),
      });

      if (!response.ok) throw new Error('Failed to create policy');
      
      // Refresh policies
      await get().fetchPolicies();
      set({ isLoading: false });
      return true;
    } catch (error) {
      set({ error: error.message, isLoading: false });
      return false;
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