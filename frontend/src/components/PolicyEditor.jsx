/**
 * Policy Creator Component - Calls Policy Architect endpoint
 */
import React, { useState } from 'react';
import { Upload, Code, AlertCircle, Check, X } from 'lucide-react';
import useStore from '../store/useStore';
import PolicyEditor from './PolicyEditor';

const PolicyCreator = () => {
  const { createPolicy, policies, isLoading } = useStore();
  
  const [activeTab, setActiveTab] = useState('create');
  const [policyText, setPolicyText] = useState('');
  const [policyName, setPolicyName] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [uploadedFile, setUploadedFile] = useState(null);

  const handleFileUpload = (event) => {
    const file = event.target.files[0];
    if (!file) return;

    if (file.type === 'application/pdf') {
      setError('PDF parsing requires backend processing. Please paste text instead.');
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      setPolicyText(e.target.result);
      setPolicyName(file.name.replace(/\.[^/.]+$/, ''));
      setUploadedFile(file.name);
    };
    reader.readAsText(file);
  };

  const handleAnalyzePolicy = async () => {
    if (!policyText.trim()) {
      setError('Please enter policy text or upload a file');
      return;
    }

    if (!policyName.trim()) {
      setError('Please enter a policy name');
      return;
    }

    setError('');
    setResult(null);

    try {
      const response = await fetch('http://localhost:8000/policy/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({
          policy_text: policyText,
          policy_name: policyName,
          source_document_type: uploadedFile ? 'file' : 'text'
        })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Policy analysis failed');
      }

      setResult(data);
      
      // Refresh policies list
      setTimeout(() => {
        window.location.reload(); // In production, use proper state update
      }, 1500);

    } catch (err) {
      setError(err.message);
    }
  };

  const examplePolicies = [
    {
      name: 'Data Protection',
      text: 'Do not allow sharing of Personally Identifiable Information (PII) including Social Security Numbers, credit card numbers, and passwords in public channels. All PII must be encrypted when stored.'
    },
    {
      name: 'Code Security',
      text: 'Prevent committing secrets or API keys to version control. All production database writes require Level 2 approval. Deployment to production environment requires peer review.'
    },
    {
      name: 'Communication Policy',
      text: 'No sensitive financial information in Slack channels. All customer data must be shared only in encrypted channels. Executive communications require archival.'
    }
  ];

  const loadExample = (example) => {
    setPolicyText(example.text);
    setPolicyName(example.name);
    setError('');
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Policy Architect</h2>
        <p className="text-gray-600 mt-2">
          Convert natural language governance requirements into executable JSON rules
        </p>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          {['create', 'edit', 'browse'].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`py-3 px-1 border-b-2 font-medium ${activeTab === tab
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
            >
              {tab === 'create' && 'Create Policy'}
              {tab === 'edit' && 'Edit Rules'}
              {tab === 'browse' && 'Browse Policies'}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="mt-6">
        {activeTab === 'create' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left Column: Input */}
            <div className="lg:col-span-2 space-y-6">
              {/* Policy Name */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Policy Name
                </label>
                <input
                  type="text"
                  value={policyName}
                  onChange={(e) => setPolicyName(e.target.value)}
                  placeholder="e.g., Data Protection Policy v2.0"
                  className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition"
                />
              </div>

              {/* Policy Text Area */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-sm font-medium text-gray-700">
                    Policy Text (Natural Language)
                  </label>
                  <div className="flex items-center space-x-4">
                    <label className="flex items-center space-x-2 text-sm text-blue-600 hover:text-blue-800 cursor-pointer">
                      <Upload className="h-4 w-4" />
                      <span>Upload File</span>
                      <input
                        type="file"
                        accept=".txt,.md,.pdf"
                        onChange={handleFileUpload}
                        className="hidden"
                      />
                    </label>
                    <button
                      onClick={() => setPolicyText('')}
                      className="text-sm text-gray-500 hover:text-gray-700"
                    >
                      Clear
                    </button>
                  </div>
                </div>
                
                {uploadedFile && (
                  <div className="mb-3 px-4 py-2 bg-blue-50 text-blue-700 rounded-lg text-sm">
                    📎 Uploaded: {uploadedFile}
                  </div>
                )}

                <textarea
                  value={policyText}
                  onChange={(e) => setPolicyText(e.target.value)}
                  placeholder="Paste your governance requirements here. For example: 'Do not allow sharing of SSNs in public channels. All production database writes require approval.'"
                  rows={12}
                  className="w-full border border-gray-300 rounded-lg px-4 py-3 font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition resize-none"
                />
              </div>

              {/* Quick Examples */}
              <div>
                <p className="text-sm font-medium text-gray-700 mb-3">Quick Examples:</p>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  {examplePolicies.map((example, idx) => (
                    <button
                      key={idx}
                      onClick={() => loadExample(example)}
                      className="text-left p-4 border border-gray-200 rounded-lg hover:border-blue-300 hover:bg-blue-50 transition"
                    >
                      <div className="font-medium text-gray-900">{example.name}</div>
                      <div className="text-sm text-gray-600 mt-1 line-clamp-3">
                        {example.text.substring(0, 100)}...
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Right Column: Actions & Preview */}
            <div className="space-y-6">
              {/* Analyze Button */}
              <button
                onClick={handleAnalyzePolicy}
                disabled={isLoading || !policyText.trim()}
                className={`w-full py-4 px-6 rounded-xl font-semibold text-white transition duration-200 ${isLoading || !policyText.trim()
                    ? 'bg-gray-400 cursor-not-allowed'
                    : 'bg-blue-600 hover:bg-blue-700'
                  }`}
              >
                {isLoading ? (
                  <div className="flex items-center justify-center">
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-3"></div>
                    Analyzing Policy...
                  </div>
                ) : (
                  'Analyze & Convert to Rules'
                )}
              </button>

              {/* How It Works */}
              <div className="bg-gray-50 rounded-xl p-6">
                <h3 className="font-semibold text-gray-900 mb-3">How It Works</h3>
                <div className="space-y-3">
                  <div className="flex items-start space-x-3">
                    <div className="w-6 h-6 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-xs font-bold">
                      1
                    </div>
                    <div>
                      <div className="font-medium text-gray-900">Natural Language Input</div>
                      <div className="text-sm text-gray-600">Describe your governance requirements in plain English</div>
                    </div>
                  </div>
                  <div className="flex items-start space-x-3">
                    <div className="w-6 h-6 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-xs font-bold">
                      2
                    </div>
                    <div>
                      <div className="font-medium text-gray-900">AI Analysis</div>
                      <div className="text-sm text-gray-600">Agent A (Policy Architect) converts to executable rules</div>
                    </div>
                  </div>
                  <div className="flex items-start space-x-3">
                    <div className="w-6 h-6 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-xs font-bold">
                      3
                    </div>
                    <div>
                      <div className="font-medium text-gray-900">Conflict Detection</div>
                      <div className="text-sm text-gray-600">System checks for conflicts with existing policies</div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Result Preview */}
              {result && (
                <div className={`rounded-xl p-6 ${result.status === 'success' ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}>
                  <div className="flex items-start">
                    {result.status === 'success' ? (
                      <Check className="h-6 w-6 text-green-600 mr-3 flex-shrink-0" />
                    ) : (
                      <X className="h-6 w-6 text-red-600 mr-3 flex-shrink-0" />
                    )}
                    <div>
                      <h3 className={`font-semibold ${result.status === 'success' ? 'text-green-800' : 'text-red-800'}`}>
                        {result.status === 'success' ? 'Policy Created Successfully' : 'Policy Creation Failed'}
                      </h3>
                      <div className="mt-2 space-y-2">
                        {result.policy_id && (
                          <div className="text-sm">
                            <span className="text-gray-600">Policy ID:</span>{' '}
                            <code className="bg-white px-2 py-1 rounded text-sm">{result.policy_id}</code>
                          </div>
                        )}
                        {result.rules_created > 0 && (
                          <div className="text-sm">
                            <span className="text-gray-600">Rules Created:</span>{' '}
                            <span className="font-medium">{result.rules_created}</span>
                          </div>
                        )}
                        {result.conflicts_detected && result.conflicts_detected.length > 0 && (
                          <div className="text-sm">
                            <span className="text-gray-600">Conflicts Detected:</span>{' '}
                            <span className="font-medium text-yellow-600">{result.conflicts_detected.length}</span>
                          </div>
                        )}
                        {result.message && (
                          <p className="text-sm text-gray-700 mt-2">{result.message}</p>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Error Display */}
              {error && (
                <div className="bg-red-50 border border-red-200 rounded-xl p-6">
                  <div className="flex items-start">
                    <AlertCircle className="h-6 w-6 text-red-600 mr-3 flex-shrink-0" />
                    <div>
                      <h3 className="font-semibold text-red-800">Error</h3>
                      <p className="text-red-700 text-sm mt-1">{error}</p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'edit' && (
          <PolicyEditor />
        )}

        {activeTab === 'browse' && (
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            <div className="p-6 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">Active Policies</h3>
              <p className="text-gray-600 text-sm mt-1">
                {policies.length} active policies in the system
              </p>
            </div>
            
            <div className="divide-y divide-gray-200">
              {policies.length === 0 ? (
                <div className="p-12 text-center">
                  <Code className="h-12 w-12 text-gray-300 mx-auto" />
                  <p className="text-gray-500 mt-4">No policies created yet</p>
                  <button
                    onClick={() => setActiveTab('create')}
                    className="mt-4 text-blue-600 hover:text-blue-800 font-medium"
                  >
                    Create your first policy →
                  </button>
                </div>
              ) : (
                policies.map((policy) => (
                  <div key={policy.id} className="p-6 hover:bg-gray-50 transition">
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="flex items-center space-x-3">
                          <h4 className="font-semibold text-gray-900">{policy.name}</h4>
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
                            <span className="font-medium">Rule ID:</span>{' '}
                            <code className="bg-gray-100 px-2 py-1 rounded text-xs">
                              {policy.rules?.rule_id || 'N/A'}
                            </code>
                          </div>
                          <p className="text-sm text-gray-600">{policy.rules?.description || 'No description'}</p>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <button className="text-sm text-blue-600 hover:text-blue-800 font-medium">
                          Edit
                        </button>
                        <button className="text-sm text-red-600 hover:text-red-800 font-medium">
                          Deactivate
                        </button>
                      </div>
                    </div>
                    <div className="mt-4 flex items-center text-sm text-gray-500">
                      <span>Created: {new Date(policy.created_at).toLocaleDateString()}</span>
                      <span className="mx-2">•</span>
                      <span>Target: {policy.rules?.target_tool_regex || 'All tools'}</span>
                      <span className="mx-2">•</span>
                      <span>Severity: {policy.rules?.severity || 'MEDIUM'}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default PolicyCreator;