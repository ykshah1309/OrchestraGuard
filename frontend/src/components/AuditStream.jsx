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
  Tool, 
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
                <Tool className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
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
          
          {/* Active filters indicator */}
          {(filters.decision !== 'all' || filters.sourceAgent || filters.targetTool || filters.search || filters.startDate || filters.endDate) && (
            <div className="mt-4 flex items-center space-x-2 text-sm text-gray-600">
              <span>Active filters:</span>
              {filters.decision !== 'all' && (
                <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-xs">
                  Decision: {filters.decision}
                </span>
              )}
              {filters.sourceAgent && (
                <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-xs">
                  Agent: {filters.sourceAgent}
                </span>
              )}
              {filters.search && (
                <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-xs">
                  Search: {filters.search}
                </span>
              )}
            </div>
          )}
        </div>
      )}

      {/* Logs Count */}
      <div className="flex items-center justify-between">
        <div className="text-sm text-gray-600">
          Showing {filteredLogs.length} of {auditLogs.length} audit logs
        </div>
        <button
          onClick={() => fetchAuditLogs(limit)}
          className="text-sm text-blue-600 hover:text-blue-800 font-medium"
        >
          Refresh
        </button>
      </div>

      {/* Audit Logs List */}
      <div className="space-y-3">
        {filteredLogs.length === 0 ? (
          <div className="text-center py-12">
            <div className="text-gray-400 mb-4">
              {auditLogs.length === 0 ? (
                <>
                  <div className="text-6xl mb-4">📊</div>
                  <p className="text-lg font-medium text-gray-900 mb-2">No audit logs yet</p>
                  <p className="text-gray-600">Intercept some actions to see them appear here in real-time.</p>
                </>
              ) : (
                <>
                  <div className="text-6xl mb-4">🔍</div>
                  <p className="text-lg font-medium text-gray-900 mb-2">No matching logs</p>
                  <p className="text-gray-600">Try adjusting your filters to see more results.</p>
                </>
              )}
            </div>
          </div>
        ) : (
          filteredLogs.map((log) => (
            <div
              key={log.id}
              className={`bg-white border rounded-lg transition-all duration-200 hover:shadow-md ${
                expandedLogId === log.id ? 'border-blue-300 shadow-sm' : 'border-gray-200'
              }`}
            >
              {/* Log Header */}
              <div
                className="p-4 cursor-pointer"
                onClick={() => setExpandedLogId(expandedLogId === log.id ? null : log.id)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-3 mb-2">
                      {getDecisionIcon(log.decision)}
                      <div className={`px-2 py-1 rounded-full text-xs font-medium ${getDecisionColor(log.decision)}`}>
                        {log.decision}
                      </div>
                      <div className="text-sm text-gray-500">
                        <span className="font-medium">{log.source_agent}</span>
                        <span className="mx-2">→</span>
                        <span className="font-medium">{log.target_tool}</span>
                      </div>
                    </div>
                    
                    <p className="text-gray-800 line-clamp-2">{log.rationale}</p>
                    
                    <div className="flex items-center space-x-4 mt-3 text-xs text-gray-500">
                      <div className="flex items-center">
                        <Clock className="h-3 w-3 mr-1" />
                        {formatTimestamp(log.created_at)}
                      </div>
                      {log.applied_rules && log.applied_rules.length > 0 && (
                        <div className="flex items-center">
                          <span className="mr-1">Rules:</span>
                          <div className="flex flex-wrap gap-1">
                            {log.applied_rules.slice(0, 2).map((rule, idx) => (
                              <span key={idx} className="px-1.5 py-0.5 bg-gray-100 text-gray-700 rounded text-xs">
                                {rule}
                              </span>
                            ))}
                            {log.applied_rules.length > 2 && (
                              <span className="px-1.5 py-0.5 bg-gray-100 text-gray-700 rounded text-xs">
                                +{log.applied_rules.length - 2} more
                              </span>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                  
                  <div className="ml-4">
                    {expandedLogId === log.id ? (
                      <ChevronUp className="h-5 w-5 text-gray-400" />
                    ) : (
                      <ChevronDown className="h-5 w-5 text-gray-400" />
                    )}
                  </div>
                </div>
              </div>
              
              {/* Expanded Details */}
              {expandedLogId === log.id && (
                <div className="px-4 pb-4 border-t border-gray-100 pt-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Rationale Details */}
                    <div>
                      <h4 className="text-sm font-medium text-gray-900 mb-2">Rationale</h4>
                      <p className="text-sm text-gray-700 bg-gray-50 p-3 rounded-lg">
                        {log.rationale}
                      </p>
                    </div>
                    
                    {/* Metadata */}
                    <div>
                      <h4 className="text-sm font-medium text-gray-900 mb-2">Details</h4>
                      <div className="space-y-2 text-sm">
                        <div className="flex justify-between">
                          <span className="text-gray-600">Action ID:</span>
                          <code className="text-gray-900 bg-gray-100 px-2 py-1 rounded">
                            {log.action_id.substring(0, 8)}...
                          </code>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-600">Timestamp:</span>
                          <span className="text-gray-900">
                            {new Date(log.created_at).toLocaleString()}
                          </span>
                        </div>
                        {log.metadata && (
                          <div>
                            <span className="text-gray-600">Metadata:</span>
                            <pre className="mt-1 text-xs bg-gray-50 p-2 rounded overflow-x-auto">
                              {JSON.stringify(log.metadata, null, 2)}
                            </pre>
                          </div>
                        )}
                      </div>
                    </div>
                    
                    {/* Applied Rules */}
                    {log.applied_rules && log.applied_rules.length > 0 && (
                      <div className="md:col-span-2">
                        <h4 className="text-sm font-medium text-gray-900 mb-2">Applied Rules</h4>
                        <div className="flex flex-wrap gap-2">
                          {log.applied_rules.map((rule, idx) => (
                            <span
                              key={idx}
                              className="px-3 py-1.5 bg-blue-50 text-blue-700 rounded-lg text-sm font-medium"
                            >
                              {rule}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                  
                  {/* JSON View */}
                  <div className="mt-4">
                    <details>
                      <summary className="text-sm font-medium text-gray-900 cursor-pointer hover:text-blue-600">
                        View Raw JSON
                      </summary>
                      <pre className="mt-2 text-xs bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto">
                        {JSON.stringify(log, null, 2)}
                      </pre>
                    </details>
                  </div>
                </div>
              )}
            </div>
          ))
        )}
      </div>
      
      {/* Load More */}
      {filteredLogs.length > 0 && filteredLogs.length < auditLogs.length && (
        <div className="text-center">
          <button
            onClick={() => fetchAuditLogs(auditLogs.length + 20)}
            className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-800 rounded-lg font-medium"
          >
            Load More
          </button>
        </div>
      )}
    </div>
  );
};

export default AuditStream;