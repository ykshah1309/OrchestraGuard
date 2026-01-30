/**
 * AuditStream Component - Real-time Audit Log Feed
 */
import React, { useState, useEffect } from 'react';
import { 
  CheckCircle, 
  XCircle, 
  AlertTriangle, 
  Clock, 
  User, 
  Wrench, 
  Filter,
  ChevronDown,
  ChevronUp,
  Search,
  Calendar
} from 'lucide-react';
import useStore from '../store/useStore';

const AuditStream = ({ limit = 20, showFilters = false }) => {
  const { auditLogs, fetchAuditLogs, isLoading } = useStore();
  
  const [expandedLogId, setExpandedLogId] = useState(null);
  const [filters, setFilters] = useState({
    decision: 'all',
    sourceAgent: '',
    targetTool: '',
    startDate: '',
    endDate: '',
    search: ''
  });
  
  const [filteredLogs, setFilteredLogs] = useState([]);

  useEffect(() => {
    if (auditLogs.length === 0) {
      fetchAuditLogs(limit);
    }
  }, [auditLogs.length, fetchAuditLogs, limit]);

  useEffect(() => {
    // Apply filters
    let result = auditLogs;
    
    if (filters.decision !== 'all') {
      result = result.filter(log => log.decision === filters.decision);
    }
    
    if (filters.sourceAgent) {
      result = result.filter(log => 
        log.source_agent.toLowerCase().includes(filters.sourceAgent.toLowerCase())
      );
    }
    
    if (filters.targetTool) {
      result = result.filter(log => 
        log.target_tool.toLowerCase().includes(filters.targetTool.toLowerCase())
      );
    }
    
    if (filters.search) {
      const searchLower = filters.search.toLowerCase();
      result = result.filter(log => 
        log.rationale.toLowerCase().includes(searchLower) ||
        log.source_agent.toLowerCase().includes(searchLower) ||
        log.target_tool.toLowerCase().includes(searchLower) ||
        (log.applied_rules && log.applied_rules.some(rule => 
          rule.toLowerCase().includes(searchLower)
        ))
      );
    }
    
    // Date filtering
    if (filters.startDate) {
      const startDate = new Date(filters.startDate);
      result = result.filter(log => new Date(log.created_at) >= startDate);
    }
    
    if (filters.endDate) {
      const endDate = new Date(filters.endDate);
      endDate.setHours(23, 59, 59, 999);
      result = result.filter(log => new Date(log.created_at) <= endDate);
    }
    
    setFilteredLogs(result.slice(0, limit));
  }, [auditLogs, filters, limit]);

  const getDecisionIcon = (decision) => {
    switch (decision) {
      case 'ALLOW':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'BLOCK':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'FLAG':
        return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
      default:
        return null;
    }
  };

  const getDecisionColor = (decision) => {
    switch (decision) {
      case 'ALLOW':
        return 'text-green-700 bg-green-50 border-green-200';
      case 'BLOCK':
        return 'text-red-700 bg-red-50 border-red-200';
      case 'FLAG':
        return 'text-yellow-700 bg-yellow-50 border-yellow-200';
      default:
        return 'text-gray-700 bg-gray-50 border-gray-200';
    }
  };

  const formatTimestamp = (timestamp) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) {
      return 'Just now';
    } else if (diffMins < 60) {
      return `${diffMins} min${diffMins > 1 ? 's' : ''} ago`;
    } else if (diffHours < 24) {
      return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    } else if (diffDays < 7) {
      return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
    } else {
      return date.toLocaleDateString();
    }
  };

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  const clearFilters = () => {
    setFilters({
      decision: 'all',
      sourceAgent: '',
      targetTool: '',
      startDate: '',
      endDate: '',
      search: ''
    });
  };

  if (isLoading && auditLogs.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading audit logs...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      {showFilters && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-2">
              <Filter className="h-5 w-5 text-gray-500" />
              <h3 className="font-medium text-gray-900">Filters</h3>
            </div>
            <button
              onClick={clearFilters}
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              Clear all
            </button>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Decision Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Decision
              </label>
              <select
                value={filters.decision}
                onChange={(e) => handleFilterChange('decision', e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              >
                <option value="all">All Decisions</option>
                <option value="ALLOW">Allowed</option>
                <option value="BLOCK">Blocked</option>
                <option value="FLAG">Flagged</option>
              </select>
            </div>
            
            {/* Source Agent Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Source Agent
              </label>
              <div className="relative">
                <User className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  value={filters.sourceAgent}
                  onChange={(e) => handleFilterChange('sourceAgent', e.target.value)}
                  placeholder="Filter by agent..."
                  className="w-full border border-gray-300 rounded-lg pl-10 pr-3 py-2 text-sm"
                />
              </div>
            </div>
            
            {/* Target Tool Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Target Tool
              </label>
              <div className="relative">
                <Wrench className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  value={filters.targetTool}
                  onChange={(e) => handleFilterChange('targetTool', e.target.value)}
                  placeholder="Filter by tool..."
                  className="w-full border border-gray-300 rounded-lg pl-10 pr-3 py-2 text-sm"
                />
              </div>
            </div>
            
            {/* Search Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Search
              </label>
              <div className="relative">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  value={filters.search}
                  onChange={(e) => handleFilterChange('search', e.target.value)}
                  placeholder="Search in logs..."
                  className="w-full border border-gray-300 rounded-lg pl-10 pr-3 py-2 text-sm"
                />
              </div>
            </div>
            
            {/* Date Filters */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Start Date
              </label>
              <div className="relative">
                <Calendar className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
                <input
                  type="date"
                  value={filters.startDate}
                  onChange={(e) => handleFilterChange('startDate', e.target.value)}
                  className="w-full border border-gray-300 rounded-lg pl-10 pr-3 py-2 text-sm"
                />
              </div>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                End Date
              </label>
              <div className="relative">
                <Calendar className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
                <input
                  type="date"
                  value={filters.endDate}
                  onChange={(e) => handleFilterChange('endDate', e.target.value)}
                  className="w-full border border-gray-300 rounded-lg pl-10 pr-3 py-2 text-sm"
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Log Feed */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Agent</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Tool</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Rationale</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Time</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Details</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filteredLogs.length === 0 ? (
                <tr>
                  <td colSpan="6" className="px-6 py-12 text-center text-gray-500">
                    No audit logs found matching your criteria.
                  </td>
                </tr>
              ) : (
                filteredLogs.map((log) => (
                  <React.Fragment key={log.id}>
                    <tr className={`hover:bg-gray-50 transition-colors ${expandedLogId === log.id ? 'bg-blue-50/30' : ''}`}>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${getDecisionColor(log.decision)}`}>
                          {getDecisionIcon(log.decision)}
                          <span className="ml-1.5">{log.decision}</span>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        {log.source_agent}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        <code className="bg-gray-100 px-2 py-0.5 rounded text-xs">{log.target_tool}</code>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500 max-w-xs truncate">
                        {log.rationale}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        <div className="flex items-center">
                          <Clock className="h-3 w-3 mr-1.5 text-gray-400" />
                          {formatTimestamp(log.created_at)}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <button
                          onClick={() => setExpandedLogId(expandedLogId === log.id ? null : log.id)}
                          className="text-blue-600 hover:text-blue-900"
                        >
                          {expandedLogId === log.id ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
                        </button>
                      </td>
                    </tr>
                    {expandedLogId === log.id && (
                      <tr>
                        <td colSpan="6" className="px-6 py-4 bg-gray-50 border-t border-b border-gray-200">
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div>
                              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Full Rationale</h4>
                              <p className="text-sm text-gray-800 bg-white p-3 rounded border border-gray-200">
                                {log.rationale}
                              </p>
                              
                              {log.applied_rules && log.applied_rules.length > 0 && (
                                <div className="mt-4">
                                  <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Applied Rules</h4>
                                  <div className="flex flex-wrap gap-2">
                                    {log.applied_rules.map((rule, idx) => (
                                      <span key={idx} className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs font-mono">
                                        {rule}
                                      </span>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                            <div>
                              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Tool Arguments</h4>
                              <pre className="text-xs text-gray-800 bg-white p-3 rounded border border-gray-200 overflow-x-auto max-h-40">
                                {JSON.stringify(log.metadata?.tool_arguments || log.metadata || {}, null, 2)}
                              </pre>
                              
                              <div className="mt-4 grid grid-cols-2 gap-4">
                                <div>
                                  <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">Action ID</h4>
                                  <p className="text-xs font-mono text-gray-600 truncate">{log.action_id}</p>
                                </div>
                                <div>
                                  <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">Severity</h4>
                                  <span className={`text-xs font-medium ${
                                    log.severity === 'HIGH' ? 'text-red-600' : 
                                    log.severity === 'MEDIUM' ? 'text-yellow-600' : 'text-blue-600'
                                  }`}>
                                    {log.severity || 'LOW'}
                                  </span>
                                </div>
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default AuditStream;