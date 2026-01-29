/**
 * Header Component with navigation and user profile
 */
import React, { useState } from 'react';
import { Menu, X, Bell, User, LogOut, Settings, HelpCircle } from 'lucide-react';
import { signOut } from '../lib/supabase';

const Header = ({ sidebarCollapsed, setSidebarCollapsed }) => {
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);

  const handleSignOut = async () => {
    try {
      await signOut();
      window.location.href = '/login';
    } catch (error) {
      console.error('Sign out error:', error);
    }
  };

  const notifications = [
    { id: 1, title: 'Policy Created', message: 'Data Protection Policy has been created', time: '2 min ago', read: false },
    { id: 2, title: 'Block Alert', message: 'Agent blocked from sharing SSN in Slack', time: '15 min ago', read: false },
    { id: 3, title: 'System Update', message: 'Database backup completed successfully', time: '1 hour ago', read: true },
  ];

  const unreadCount = notifications.filter(n => !n.read).length;

  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-50">
      <div className="px-6 py-4">
        <div className="flex items-center justify-between">
          {/* Left side: Menu toggle and title */}
          <div className="flex items-center space-x-4">
            <button
              onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
              className="p-2 rounded-lg hover:bg-gray-100 transition"
              aria-label="Toggle sidebar"
            >
              {sidebarCollapsed ? (
                <Menu className="h-5 w-5 text-gray-600" />
              ) : (
                <X className="h-5 w-5 text-gray-600" />
              )}
            </button>
            
            <div className="hidden md:block">
              <h1 className="text-xl font-semibold text-gray-900">OrchestraGuard</h1>
              <p className="text-xs text-gray-500">Multi-Agent Governance Dashboard</p>
            </div>
          </div>

          {/* Right side: Notifications and user menu */}
          <div className="flex items-center space-x-3">
            {/* Notifications */}
            <div className="relative">
              <button
                onClick={() => setNotificationsOpen(!notificationsOpen)}
                className="p-2 rounded-lg hover:bg-gray-100 relative transition"
                aria-label="Notifications"
              >
                <Bell className="h-5 w-5 text-gray-600" />
                {unreadCount > 0 && (
                  <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full h-5 w-5 flex items-center justify-center">
                    {unreadCount}
                  </span>
                )}
              </button>

              {/* Notifications dropdown */}
              {notificationsOpen && (
                <>
                  <div
                    className="fixed inset-0 z-40"
                    onClick={() => setNotificationsOpen(false)}
                  />
                  <div className="absolute right-0 mt-2 w-80 bg-white rounded-xl shadow-lg border border-gray-200 z-50">
                    <div className="p-4 border-b border-gray-200">
                      <div className="flex items-center justify-between">
                        <h3 className="font-semibold text-gray-900">Notifications</h3>
                        <button className="text-sm text-blue-600 hover:text-blue-800">
                          Mark all as read
                        </button>
                      </div>
                    </div>
                    
                    <div className="max-h-96 overflow-y-auto">
                      {notifications.length === 0 ? (
                        <div className="p-8 text-center">
                          <Bell className="h-12 w-12 text-gray-300 mx-auto" />
                          <p className="text-gray-500 mt-2">No notifications</p>
                        </div>
                      ) : (
                        notifications.map((notification) => (
                          <div
                            key={notification.id}
                            className={`p-4 border-b border-gray-100 hover:bg-gray-50 transition ${!notification.read ? 'bg-blue-50' : ''}`}
                          >
                            <div className="flex justify-between">
                              <div className="font-medium text-gray-900">{notification.title}</div>
                              <div className="text-xs text-gray-500">{notification.time}</div>
                            </div>
                            <p className="text-sm text-gray-600 mt-1">{notification.message}</p>
                            {!notification.read && (
                              <div className="mt-2">
                                <span className="inline-block h-2 w-2 rounded-full bg-blue-500"></span>
                                <span className="text-xs text-blue-600 ml-2">Unread</span>
                              </div>
                            )}
                          </div>
                        ))
                      )}
                    </div>
                    
                    <div className="p-4 border-t border-gray-200">
                      <button className="w-full text-center text-sm text-blue-600 hover:text-blue-800 font-medium">
                        View all notifications
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>

            {/* Help */}
            <button
              className="p-2 rounded-lg hover:bg-gray-100 transition"
              aria-label="Help"
            >
              <HelpCircle className="h-5 w-5 text-gray-600" />
            </button>

            {/* Settings */}
            <button
              className="p-2 rounded-lg hover:bg-gray-100 transition"
              aria-label="Settings"
            >
              <Settings className="h-5 w-5 text-gray-600" />
            </button>

            {/* User menu */}
            <div className="relative">
              <button
                onClick={() => setUserMenuOpen(!userMenuOpen)}
                className="flex items-center space-x-3 p-2 rounded-lg hover:bg-gray-100 transition"
                aria-label="User menu"
              >
                <div className="h-8 w-8 rounded-full bg-blue-100 flex items-center justify-center">
                  <User className="h-4 w-4 text-blue-600" />
                </div>
                <div className="hidden md:block text-left">
                  <div className="text-sm font-medium text-gray-900">Admin User</div>
                  <div className="text-xs text-gray-500">admin@orchestraguard.com</div>
                </div>
              </button>

              {/* User dropdown */}
              {userMenuOpen && (
                <>
                  <div
                    className="fixed inset-0 z-40"
                    onClick={() => setUserMenuOpen(false)}
                  />
                  <div className="absolute right-0 mt-2 w-64 bg-white rounded-xl shadow-lg border border-gray-200 z-50">
                    <div className="p-4 border-b border-gray-200">
                      <div className="flex items-center space-x-3">
                        <div className="h-10 w-10 rounded-full bg-blue-100 flex items-center justify-center">
                          <User className="h-5 w-5 text-blue-600" />
                        </div>
                        <div>
                          <div className="font-semibold text-gray-900">Admin User</div>
                          <div className="text-sm text-gray-500">admin@orchestraguard.com</div>
                        </div>
                      </div>
                    </div>
                    
                    <div className="p-2">
                      <button className="w-full flex items-center space-x-3 px-4 py-3 rounded-lg hover:bg-gray-100 text-left transition">
                        <User className="h-4 w-4 text-gray-600" />
                        <span className="text-sm text-gray-700">Profile Settings</span>
                      </button>
                      
                      <button className="w-full flex items-center space-x-3 px-4 py-3 rounded-lg hover:bg-gray-100 text-left transition">
                        <Settings className="h-4 w-4 text-gray-600" />
                        <span className="text-sm text-gray-700">Account Settings</span>
                      </button>
                      
                      <button
                        onClick={handleSignOut}
                        className="w-full flex items-center space-x-3 px-4 py-3 rounded-lg hover:bg-gray-100 text-left transition text-red-600"
                      >
                        <LogOut className="h-4 w-4" />
                        <span className="text-sm font-medium">Sign Out</span>
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;