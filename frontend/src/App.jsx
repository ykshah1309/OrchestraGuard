/**
 * OrchestraGuard Dashboard Hub - Main React App
 */
import React, { useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import useStore from './store/useStore';
import Dashboard from './components/Dashboard';
import PolicyEditor from './components/PolicyEditor';
import AuditStream from './components/AuditStream';
import Sidebar from './components/Sidebar';
import Header from './components/Header';

function App() {
  const { subscribeToRealtime, realtimeConnected } = useStore();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  useEffect(() => {
    // Subscribe to realtime updates
    const unsubscribe = subscribeToRealtime();
    
    // Cleanup on unmount
    return () => {
      if (unsubscribe) unsubscribe();
    };
  }, [subscribeToRealtime]);

  return (
    <Router>
      <div className="min-h-screen bg-gray-50">
        <Toaster position="top-right" />
        
        {/* Header */}
        <Header 
          sidebarCollapsed={sidebarCollapsed}
          setSidebarCollapsed={setSidebarCollapsed}
        />
        
        <div className="flex">
          {/* Sidebar */}
          <Sidebar 
            collapsed={sidebarCollapsed}
            realtimeConnected={realtimeConnected}
          />
          
          {/* Main Content */}
          <div className={`flex-1 transition-all duration-300 ${sidebarCollapsed ? 'ml-16' : 'ml-64'}`}>
            <div className="p-6">
              <Routes>
                <Route path="/" element={<Navigate to="/dashboard" />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/policies" element={<PolicyEditor />} />
                <Route path="/audit" element={<AuditStream />} />
                <Route path="/settings" element={<div>Settings (Coming Soon)</div>} />
              </Routes>
            </div>
          </div>
        </div>
        
        {/* Connection Status */}
        <div className={`fixed bottom-4 right-4 px-4 py-2 rounded-full text-sm font-semibold ${
          realtimeConnected 
            ? 'bg-green-100 text-green-800 border border-green-300' 
            : 'bg-red-100 text-red-800 border border-red-300'
        }`}>
          {realtimeConnected ? '🟢 Live' : '🔴 Disconnected'}
        </div>
      </div>
    </Router>
  );
}

export default App;