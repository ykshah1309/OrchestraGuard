/**
 * Complete Dashboard Component with Live Interception Feed
 */
import React, { useEffect, useState } from 'react';
import { BarChart3, Shield, AlertTriangle, CheckCircle, Zap, Users, Database, Settings } from 'lucide-react';
import useStore from '../store/useStore';
import AuditStream from '../components/AuditStream';
import PolicyCreator from '../components/PolicyCreator';
import MetricsCard from '../components/MetricsCard';

const Dashboard = () => {
  const {
    auditLogs,
    metrics,
    fetchAuditLogs,
    fetchMetrics,
    fetchPolicies,
    getRecentBlocks,
    getDecisionStats,
    isLoading,
    error,
    realtimeConnected
  } = useStore();

  const [activeTab, setActiveTab] = useState('overview');
  const [timeRange, setTimeRange] = useState('1h');

  useEffect(() => {
    // Initial data fetch
    fetchAuditLogs(50);
    fetchMetrics();
    fetchPolicies();

    // Set up auto-refresh every 30 seconds
    const interval = setInterval(() => {
      fetchMetrics();
    }, 30000);

    return () => clearInterval(interval);
  }, [fetchAuditLogs, fetchMetrics, fetchPolicies]);

  // Calculate derived metrics
  const decisionStats = getDecisionStats();
  const recentBlocks = getRecentBlocks();
  const blockRate = metrics.blockRate || 0;
  const totalDecisions = metrics.totalDecisions || 0;

  // Status color based on block rate
  const getStatusColor = (rate) => {
    if (rate < 0.05) return 'text-green-600 bg-green-50';
    if (rate < 0.15) return 'text-yellow-600 bg-yellow-50';
    return 'text-red-600 bg-red-50';
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">OrchestraGuard Dashboard</h1>
          <p className="text-gray-600 mt-2">Multi-Agent Governance Mesh - Real-time Monitoring</p>
        </div>
        <div className="flex items-center space-x-4">
          <div className={`px-4 py-2 rounded-full text-sm font-semibold ${getStatusColor(blockRate)}`}>
            <div className="flex items-center space-x-2">
              <div className={`w-2 h-2 rounded-full ${blockRate > 0.15 ? 'bg-red-500' : blockRate > 0.05 ? 'bg-yellow-500' : 'bg-green-500'}`}></div>
              <span>Block Rate: {(blockRate * 100).toFixed(1)}%</span>
            </div>
          </div>
          <div className={`px-3 py-1 rounded-full text-xs font-medium ${realtimeConnected ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
            {realtimeConnected ? '🟢 LIVE' : '🔴 OFFLINE'}
          </div>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricsCard
          title="Total Decisions"
          value={totalDecisions.toLocaleString()}
          icon={<BarChart3 className="h-6 w-6" />}
          trend="+12.5%"
          color="blue"
        />
        <MetricsCard
          title="Allowed"
          value={metrics.allowCount || 0}
          icon={<CheckCircle className="h-6 w-6" />}
          subtitle={`${(decisionStats.allow * 100).toFixed(1)}% of total`}
          color="green"
        />
        <MetricsCard
          title="Blocked"
          value={metrics.blockCount || 0}
          icon={<Shield className="h-6 w-6" />}
          subtitle={`${(decisionStats.block * 100).toFixed(1)}% of total`}
          color="red"
        />
        <MetricsCard
          title="Flagged"
          value={metrics.flagCount || 0}
          icon={<AlertTriangle className="h-6 w-6" />}
          subtitle={`${(decisionStats.flag * 100).toFixed(1)}% of total`}
          color="yellow"
        />
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          {['overview', 'live-feed', 'policies', 'agents'].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${activeTab === tab
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
            >
              {tab === 'overview' && 'Overview'}
              {tab === 'live-feed' && 'Live Interception Feed'}
              {tab === 'policies' && 'Policy Management'}
              {tab === 'agents' && 'Agent Status'}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="mt-6">
        {activeTab === 'overview' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left Column: Live Feed Preview */}
            <div className="lg:col-span-2">
              <div className="bg-white rounded-xl shadow p-6">
                <div className="flex items-center justify-between mb-6">
                  <h2 className="text-xl font-semibold text-gray-900">Recent Activity</h2>
                  <button
                    onClick={() => setActiveTab('live-feed')}
                    className="text-sm text-blue-600 hover:text-blue-800 font-medium"
                  >
                    View All →
                  </button>
                </div>
                <AuditStream limit={8} />
              </div>
            </div>

            {/* Right Column: Quick Actions & Stats */}
            <div className="space-y-6">
              {/* Policy Creator Card */}
              <div className="bg-white rounded-xl shadow p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Create Policy</h3>
                <p className="text-gray-600 text-sm mb-4">
                  Convert natural language policies to executable rules
                </p>
                <button
                  onClick={() => setActiveTab('policies')}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 px-4 rounded-lg transition duration-200"
                >
                  Launch Policy Architect
                </button>
              </div>

              {/* Recent Blocks */}
              <div className="bg-white rounded-xl shadow p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Recent Blocks</h3>
                {recentBlocks.length === 0 ? (
                  <p className="text-gray-500 text-sm">No blocks in the last hour</p>
                ) : (
                  <div className="space-y-3">
                    {recentBlocks.slice(0, 3).map((block) => (
                      <div key={block.id} className="border-l-4 border-red-500 pl-4 py-2">
                        <div className="flex justify-between">
                          <span className="text-sm font-medium text-gray-900">{block.source_agent}</span>
                          <span className="text-xs text-gray-500">
                            {new Date(block.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </span>
                        </div>
                        <p className="text-sm text-gray-600 truncate">{block.rationale}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* System Health */}
              <div className="bg-white rounded-xl shadow p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">System Health</h3>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <div className="w-3 h-3 rounded-full bg-green-500"></div>
                      <span className="text-sm font-medium text-gray-700">Agent A (Policy Architect)</span>
                    </div>
                    <span className="text-xs text-green-600">Active</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <div className="w-3 h-3 rounded-full bg-green-500"></div>
                      <span className="text-sm font-medium text-gray-700">Agent B (Interceptor)</span>
                    </div>
                    <span className="text-xs text-green-600">Active</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <div className="w-3 h-3 rounded-full bg-green-500"></div>
                      <span className="text-sm font-medium text-gray-700">Agent C (Ethical Reasoner)</span>
                    </div>
                    <span className="text-xs text-green-600">Active</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'live-feed' && (
          <div className="bg-white rounded-xl shadow">
            <div className="p-6 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-semibold text-gray-900">Live Interception Feed</h2>
                  <p className="text-gray-600 text-sm mt-1">
                    Real-time updates from Supabase Realtime. Updates automatically.
                  </p>
                </div>
                <div className="flex items-center space-x-4">
                  <select
                    value={timeRange}
                    onChange={(e) => setTimeRange(e.target.value)}
                    className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  >
                    <option value="1h">Last Hour</option>
                    <option value="24h">Last 24 Hours</option>
                    <option value="7d">Last 7 Days</option>
                    <option value="30d">Last 30 Days</option>
                  </select>
                  <button
                    onClick={() => fetchAuditLogs(100)}
                    className="bg-gray-100 hover:bg-gray-200 text-gray-800 font-medium py-2 px-4 rounded-lg text-sm transition duration-200"
                  >
                    Refresh
                  </button>
                </div>
              </div>
            </div>
            <div className="p-6">
              <AuditStream limit={50} showFilters={true} />
            </div>
          </div>
        )}

        {activeTab === 'policies' && (
          <div className="bg-white rounded-xl shadow p-6">
            <PolicyCreator />
          </div>
        )}

        {activeTab === 'agents' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Agent Status Cards */}
            {[
              {
                id: 'agent-a',
                name: 'Policy Architect',
                description: 'Converts natural language policies to executable JSON rules',
                status: 'active',
                uptime: '99.8%',
                lastActivity: '2 minutes ago'
              },
              {
                id: 'agent-b',
                name: 'Sentinel Interceptor',
                description: 'Captures and forwards agent actions for ethical review',
                status: 'active',
                uptime: '99.9%',
                lastActivity: 'Just now'
              },
              {
                id: 'agent-c',
                name: 'Ethical Reasoner',
                description: 'Evaluates actions against policies and makes decisions',
                status: 'active',
                uptime: '99.7%',
                lastActivity: '15 seconds ago'
              },
              {
                id: 'agent-d',
                name: 'Agentic Logger',
                description: 'Records all decisions and violations to audit log',
                status: 'active',
                uptime: '100%',
                lastActivity: 'Just now'
              }
            ].map((agent) => (
              <div key={agent.id} className="border border-gray-200 rounded-xl p-6">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900">{agent.name}</h3>
                    <p className="text-gray-600 text-sm mt-1">{agent.description}</p>
                  </div>
                  <div className={`px-3 py-1 rounded-full text-xs font-medium ${agent.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                    {agent.status.toUpperCase()}
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Uptime</span>
                    <span className="font-medium">{agent.uptime}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Last Activity</span>
                    <span className="font-medium">{agent.lastActivity}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Decisions Processed</span>
                    <span className="font-medium">{totalDecisions.toLocaleString()}</span>
                  </div>
                </div>
                <button className="w-full mt-6 bg-gray-100 hover:bg-gray-200 text-gray-800 font-medium py-2 px-4 rounded-lg text-sm transition duration-200">
                  View Details
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="fixed inset-0 bg-white bg-opacity-80 flex items-center justify-center z-50">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Loading dashboard data...</p>
          </div>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-6">
          <div className="flex items-center">
            <AlertTriangle className="h-6 w-6 text-red-600 mr-3" />
            <div>
              <h3 className="text-lg font-semibold text-red-800">Error Loading Dashboard</h3>
              <p className="text-red-700 mt-1">{error}</p>
              <button
                onClick={() => {
                  fetchAuditLogs();
                  fetchMetrics();
                }}
                className="mt-4 bg-red-600 hover:bg-red-700 text-white font-medium py-2 px-4 rounded-lg text-sm transition duration-200"
              >
                Retry
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;