/**
 * FIXED: PolicyEditor Component - Uses store for API calls, no window.location.reload
 */
import React, { useState, useEffect } from 'react';
import { Code, AlertCircle, Check, X, Save, Trash2, Eye, EyeOff } from 'lucide-react';
import useStore from '../store/useStore';

const PolicyEditor = () => {
  const { policies, createPolicy, updatePolicy, fetchPolicies, isLoading } = useStore();
  
  const [selectedPolicy, setSelectedPolicy] = useState(null);
  const [editedRules, setEditedRules] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [viewMode, setViewMode] = useState('form'); // 'form' or 'json'
  const [jsonValid, setJsonValid] = useState(true);

  // Initialize with first policy
  useEffect(() => {
    if (policies.length > 0 && !selectedPolicy) {
      const firstPolicy = policies[0];
      setSelectedPolicy(firstPolicy);
      setEditedRules(JSON.stringify(firstPolicy.rules, null, 2));
    }
  }, [policies, selectedPolicy]);

  const handlePolicySelect = (policy) => {
    setSelectedPolicy(policy);
    setEditedRules(JSON.stringify(policy.rules, null, 2));
    setIsEditing(false);
    setError('');
    setSuccess('');
  };

  const handleEditToggle = () => {
    if (isEditing) {
      // Cancel edit
      setEditedRules(JSON.stringify(selectedPolicy.rules, null, 2));
      setError('');
    }
    setIsEditing(!isEditing);
  };

  const handleSave = async () => {
    try {
      // Validate JSON
      const parsedRules = JSON.parse(editedRules);
      
      // Prepare update data
      const updateData = {
        name: selectedPolicy.name,
        rules: parsedRules,
        is_active: selectedPolicy.is_active
      };
      
      // Call update via store
      const success = await updatePolicy(selectedPolicy.id, updateData);
      
      if (success) {
        setSuccess('Policy updated successfully!');
        setError('');
        
        // Refresh policies from store (no page reload)
        await fetchPolicies();
        
        // Find and select the updated policy
        const updatedPolicies = policies.map(p => 
          p.id === selectedPolicy.id ? { ...p, ...updateData } : p
        );
        const updatedPolicy = updatedPolicies.find(p => p.id === selectedPolicy.id);
        setSelectedPolicy(updatedPolicy);
        
        // Exit edit mode after delay
        setTimeout(() => setIsEditing(false), 1500);
      } else {
        throw new Error('Failed to update policy');
      }
    } catch (err) {
      setError(`Invalid JSON or save failed: ${err.message}`);
      setJsonValid(false);
    }
  };

  const handleToggleActive = async () => {
    if (!selectedPolicy) return;
    
    try {
      const newStatus = !selectedPolicy.is_active;
      const updateData = { is_active: newStatus };
      
      const success = await updatePolicy(selectedPolicy.id, updateData);
      
      if (success) {
        setSelectedPolicy({ ...selectedPolicy, is_active: newStatus });
        setSuccess(`Policy ${newStatus ? 'activated' : 'deactivated'}!`);
        
        // Refresh policies
        await fetchPolicies();
      }
    } catch (err) {
      setError(`Failed to update status: ${err.message}`);
    }
  };

  const validateJson = (jsonString) => {
    try {
      JSON.parse(jsonString);
      setJsonValid(true);
      return true;
    } catch (e) {
      setJsonValid(false);
      return false;
    }
  };

  const handleJsonChange = (value) => {
    setEditedRules(value);
    validateJson(value);
  };

  const formatJson = () => {
    try {
      const parsed = JSON.parse(editedRules);
      setEditedRules(JSON.stringify(parsed, null, 2));
      setJsonValid(true);
    } catch (e) {
      setError('Cannot format invalid JSON');
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Left Column: Policy List */}
      <div className="lg:col-span-1">
        <div className="bg-white rounded-xl shadow p-6">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-semibold text-gray-900">Policies</h3>
            <span className="text-sm text-gray-500">
              {policies.length} active
            </span>
          </div>
          
          <div className="space-y-3 max-h-96 overflow-y-auto">
            {policies.length === 0 ? (
              <div className="text-center py-8">
                <Code className="h-12 w-12 text-gray-300 mx-auto" />
                <p className="text-gray-500 mt-4">No policies created yet</p>
              </div>
            ) : (
              policies.map((policy) => (
                <div
                  key={policy.id}
                  onClick={() => handlePolicySelect(policy)}
                  className={`
                    p-4 border rounded-lg cursor-pointer transition
                    ${selectedPolicy?.id === policy.id
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                    }
                  `}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center space-x-2">
                        <h4 className="font-medium text-gray-900">{policy.name}</h4>
                        {policy.is_active ? (
                          <span className="px-2 py-1 bg-green-100 text-green-800 text-xs font-medium rounded-full">
                            Active
                          </span>
                        ) : (
                          <span className="px-2 py-1 bg-gray-100 text-gray-800 text-xs font-medium rounded-full">
                            Inactive
                          </span>
                        )}
                      </div>
                      <div className="mt-2 space-y-1">
                        <div className="text-sm text-gray-600">
                          <span className="font-medium">Rule:</span>{' '}
                          <code className="bg-gray-100 px-2 py-1 rounded text-xs">
                            {policy.rules?.rule_id || 'N/A'}
                          </code>
                        </div>
                        <p className="text-sm text-gray-600 line-clamp-2">
                          {policy.rules?.description || 'No description'}
                        </p>
                      </div>
                    </div>
                  </div>
                  <div className="mt-3 flex items-center text-xs text-gray-500">
                    <span>Created: {new Date(policy.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Right Column: Policy Editor */}
      <div className="lg:col-span-2">
        <div className="bg-white rounded-xl shadow p-6">
          {!selectedPolicy ? (
            <div className="text-center py-12">
              <div className="text-gray-400 mb-4">
                <div className="text-6xl mb-4">📋</div>
                <p className="text-lg font-medium text-gray-900 mb-2">Select a Policy</p>
                <p className="text-gray-600">Choose a policy from the list to view and edit its rules.</p>
              </div>
            </div>
          ) : (
            <>
              {/* Policy Header */}
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h3 className="text-xl font-semibold text-gray-900">{selectedPolicy.name}</h3>
                  <p className="text-gray-600 text-sm mt-1">
                    Rule ID: <code className="bg-gray-100 px-2 py-1 rounded">{selectedPolicy.rules?.rule_id}</code>
                    <span className="mx-2">•</span>
                    Severity: <span className="font-medium">{selectedPolicy.rules?.severity}</span>
                    <span className="mx-2">•</span>
                    Action: <span className="font-medium">{selectedPolicy.rules?.action_on_violation}</span>
                  </p>
                </div>
                
                <div className="flex items-center space-x-3">
                  <button
                    onClick={() => setViewMode(viewMode === 'form' ? 'json' : 'form')}
                    className="flex items-center space-x-2 px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  >
                    {viewMode === 'form' ? (
                      <>
                        <Code className="h-4 w-4" />
                        <span>JSON View</span>
                      </>
                    ) : (
                      <>
                        <Eye className="h-4 w-4" />
                        <span>Form View</span>
                      </>
                    )}
                  </button>
                  
                  <button
                    onClick={handleToggleActive}
                    className={`px-4 py-2 rounded-lg font-medium text-sm ${
                      selectedPolicy.is_active
                        ? 'bg-red-100 text-red-700 hover:bg-red-200'
                        : 'bg-green-100 text-green-700 hover:bg-green-200'
                    }`}
                  >
                    {selectedPolicy.is_active ? 'Deactivate' : 'Activate'}
                  </button>
                  
                  <button
                    onClick={handleEditToggle}
                    className={`px-4 py-2 rounded-lg font-medium text-sm ${
                      isEditing
                        ? 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                        : 'bg-blue-100 text-blue-700 hover:bg-blue-200'
                    }`}
                  >
                    {isEditing ? 'Cancel Edit' : 'Edit Rules'}
                  </button>
                </div>
              </div>

              {/* Success/Error Messages */}
              {success && (
                <div className="mb-6 bg-green-50 border border-green-200 rounded-xl p-4">
                  <div className="flex items-center">
                    <Check className="h-5 w-5 text-green-600 mr-3" />
                    <div>
                      <p className="text-green-800 font-medium">{success}</p>
                    </div>
                  </div>
                </div>
              )}
              
              {error && (
                <div className="mb-6 bg-red-50 border border-red-200 rounded-xl p-4">
                  <div className="flex items-center">
                    <X className="h-5 w-5 text-red-600 mr-3" />
                    <div>
                      <p className="text-red-800 font-medium">{error}</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Rule Editor */}
              <div className="space-y-6">
                {/* JSON Editor */}
                {viewMode === 'json' ? (
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <label className="block text-sm font-medium text-gray-700">
                        Rule Configuration (JSON)
                      </label>
                      <button
                        onClick={formatJson}
                        className="text-sm text-blue-600 hover:text-blue-800"
                      >
                        Format JSON
                      </button>
                    </div>
                    
                    <div className="relative">
                      <textarea
                        value={editedRules}
                        onChange={(e) => handleJsonChange(e.target.value)}
                        readOnly={!isEditing}
                        rows={20}
                        className={`w-full font-mono text-sm p-4 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition resize-none ${
                          !jsonValid ? 'border-red-300' : 'border-gray-300'
                        } ${!isEditing ? 'bg-gray-50' : 'bg-white'}`}
                      />
                      
                      {!jsonValid && (
                        <div className="absolute top-2 right-2">
                          <div className="flex items-center text-red-600 text-sm">
                            <AlertCircle className="h-4 w-4 mr-1" />
                            Invalid JSON
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  /* Form View */
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* Rule ID */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Rule ID
                      </label>
                      <input
                        type="text"
                        value={selectedPolicy.rules?.rule_id || ''}
                        readOnly={!isEditing}
                        className="w-full border border-gray-300 rounded-lg px-4 py-3 bg-gray-50"
                      />
                    </div>
                    
                    {/* Severity */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Severity
                      </label>
                      <select
                        value={selectedPolicy.rules?.severity || 'MEDIUM'}
                        readOnly={!isEditing}
                        className="w-full border border-gray-300 rounded-lg px-4 py-3 bg-gray-50"
                      >
                        <option value="HIGH">High</option>
                        <option value="MEDIUM">Medium</option>
                        <option value="LOW">Low</option>
                      </select>
                    </div>
                    
                    {/* Target Tool Regex */}
                    <div className="md:col-span-2">
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Target Tool Regex
                      </label>
                      <input
                        type="text"
                        value={selectedPolicy.rules?.target_tool_regex || ''}
                        readOnly={!isEditing}
                        className="w-full border border-gray-300 rounded-lg px-4 py-3 font-mono text-sm bg-gray-50"
                      />
                      <p className="text-sm text-gray-500 mt-1">
                        Regular expression to match target tools (e.g., "Slack_API_.*" or "GitHub_API_Create.*")
                      </p>
                    </div>
                    
                    {/* Condition Logic */}
                    <div className="md:col-span-2">
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Condition Logic
                      </label>
                      <textarea
                        value={selectedPolicy.rules?.condition_logic || ''}
                        readOnly={!isEditing}
                        rows={6}
                        className="w-full border border-gray-300 rounded-lg px-4 py-3 font-mono text-sm bg-gray-50"
                      />
                      <p className="text-sm text-gray-500 mt-1">
                        Python-evaluatable condition that returns True/False. Use variables: tool_arguments, user_context
                      </p>
                    </div>
                    
                    {/* Description */}
                    <div className="md:col-span-2">
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Description
                      </label>
                      <textarea
                        value={selectedPolicy.rules?.description || ''}
                        readOnly={!isEditing}
                        rows={3}
                        className="w-full border border-gray-300 rounded-lg px-4 py-3 bg-gray-50"
                      />
                    </div>
                  </div>
                )}

                {/* Save Button */}
                {isEditing && (
                  <div className="flex items-center justify-between pt-6 border-t border-gray-200">
                    <div className="text-sm text-gray-500">
                      {jsonValid ? '✓ JSON is valid' : '✗ JSON is invalid'}
                    </div>
                    <button
                      onClick={handleSave}
                      disabled={!jsonValid || isLoading}
                      className={`px-6 py-3 rounded-lg font-medium text-white ${
                        jsonValid && !isLoading
                          ? 'bg-blue-600 hover:bg-blue-700'
                          : 'bg-gray-400 cursor-not-allowed'
                      }`}
                    >
                      {isLoading ? (
                        <div className="flex items-center">
                          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                          Saving...
                        </div>
                      ) : (
                        <div className="flex items-center">
                          <Save className="h-4 w-4 mr-2" />
                          Save Changes
                        </div>
                      )}
                    </button>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default PolicyEditor;