/**
 * Sidebar Component with navigation menu
 */
import React from 'react';
import { NavLink } from 'react-router-dom';
import { 
  LayoutDashboard, 
  Shield, 
  FileText, 
  BarChart3, 
  Settings,
  Zap,
  Users,
  Database,
  Globe
} from 'lucide-react';

const Sidebar = ({ collapsed, realtimeConnected }) => {
  const menuItems = [
    { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard', badge: null },
    { path: '/policies', icon: Shield, label: 'Policies', badge: null },
    { path: '/audit', icon: FileText, label: 'Audit Logs', badge: null },
    { path: '/agents', icon: Users, label: 'Agents', badge: null },
    { path: '/analytics', icon: BarChart3, label: 'Analytics', badge: 'New' },
    { path: '/integrations', icon: Globe, label: 'Integrations', badge: null },
    { path: '/database', icon: Database, label: 'Database', badge: null },
    { path: '/settings', icon: Settings, label: 'Settings', badge: null },
  ];

  const agentStatus = [
    { id: 'agent-a', name: 'Policy Architect', status: 'active', icon: Shield },
    { id: 'agent-b', name: 'Interceptor', status: 'active', icon: Zap },
    { id: 'agent-c', name: 'Ethical Reasoner', status: 'active', icon: Users },
    { id: 'agent-d', name: 'Logger', status: 'active', icon: Database },
  ];

  return (
    <aside className={`bg-gray-900 text-white h-screen sticky top-0 flex flex-col transition-all duration-300 ${collapsed ? 'w-16' : 'w-64'}`}>
      {/* Logo */}
      <div className={`p-6 border-b border-gray-800 ${collapsed ? 'text-center' : ''}`}>
        {collapsed ? (
          <div className="text-2xl font-bold text-blue-400">OG</div>
        ) : (
          <div>
            <h1 className="text-2xl font-bold text-white">OrchestraGuard</h1>
            <p className="text-gray-400 text-sm mt-1">Governance Mesh</p>
          </div>
        )}
      </div>

      {/* Main Navigation */}
      <nav className="flex-1 p-4 overflow-y-auto">
        <div className="space-y-1">
          {menuItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) => `
                flex items-center rounded-lg px-4 py-3 transition-all duration-200
                ${isActive 
                  ? 'bg-blue-600 text-white shadow-lg' 
                  : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                }
                ${collapsed ? 'justify-center' : ''}
              `}
            >
              <item.icon className={`h-5 w-5 ${collapsed ? '' : 'mr-3'}`} />
              {!collapsed && (
                <>
                  <span className="font-medium">{item.label}</span>
                  {item.badge && (
                    <span className="ml-auto bg-blue-500 text-xs px-2 py-1 rounded-full">
                      {item.badge}
                    </span>
                  )}
                </>
              )}
            </NavLink>
          ))}
        </div>

        {/* Agent Status (collapsed only shows icons) */}
        {!collapsed && (
          <div className="mt-8 pt-6 border-t border-gray-800">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">
              Agent Status
            </h3>
            <div className="space-y-3">
              {agentStatus.map((agent) => (
                <div
                  key={agent.id}
                  className="flex items-center justify-between p-3 rounded-lg bg-gray-800/50 hover:bg-gray-800 transition"
                >
                  <div className="flex items-center">
                    <div className={`h-2 w-2 rounded-full mr-3 ${
                      agent.status === 'active' ? 'bg-green-500' : 'bg-red-500'
                    }`} />
                    <span className="text-sm text-gray-300">{agent.name}</span>
                  </div>
                  <div className="text-xs px-2 py-1 rounded-full bg-gray-700 text-gray-300">
                    {agent.status}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Real-time Status */}
        <div className={`mt-8 p-4 rounded-lg bg-gray-800/30 ${collapsed ? 'text-center' : ''}`}>
          <div className="flex items-center justify-between">
            {!collapsed && (
              <div className="text-sm text-gray-400">Live Updates</div>
            )}
            <div className={`flex items-center ${collapsed ? 'justify-center' : ''}`}>
              <div className={`h-2 w-2 rounded-full mr-2 ${realtimeConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
              {!collapsed && (
                <span className="text-sm text-gray-300">
                  {realtimeConnected ? 'Connected' : 'Disconnected'}
                </span>
              )}
            </div>
          </div>
        </div>
      </nav>

      {/* Footer */}
      <div className={`p-4 border-t border-gray-800 ${collapsed ? 'text-center' : ''}`}>
        {collapsed ? (
          <div className="text-gray-400 text-sm">v2.0</div>
        ) : (
          <div>
            <div className="text-xs text-gray-400 mb-2">System Status</div>
            <div className="flex items-center justify-between">
              <div className="text-sm text-gray-300">Operational</div>
              <div className="text-xs text-gray-400">v2.0</div>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
};

export default Sidebar;