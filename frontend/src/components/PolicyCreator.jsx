/**
 * PolicyCreator Component - Converts natural language to executable rules
 */
import React, { useState } from 'react';
import { Sparkles, Shield, AlertCircle, Check, Loader2 } from 'lucide-react';
import useStore from '../store/useStore';

const PolicyCreator = () => {
  const { createPolicy, isLoading } = useStore();
  const [policyText, setPolicyText] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!policyText.trim()) return;

    setError(null);
    setResult(null);

    const response = await createPolicy({ policy_text: policyText });

    if (response.status === 'success') {
      setResult(response);
      setPolicyText('');
    } else {
      setError(response.message || 'Failed to create policy');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center space-x-2 mb-4">
        <Sparkles className="h-6 w-6 text-blue-500" />
        <h2 className="text-xl font-semibold text-gray-900">Policy Architect</h2>
      </div>

      <p className="text-gray-600 text-sm">
        Describe your security policy in natural language. Agent A will analyze it and generate executable rules.
      </p>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <textarea
            value={policyText}
            onChange={(e) => setPolicyText(e.target.value)}
            placeholder="e.g., Block any Slack messages that contain credit card numbers or API keys."
            className="w-full h-32 p-4 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
            disabled={isLoading}
          />
        </div>

        <button
          type="submit"
          disabled={isLoading || !policyText.trim()}
          className={`w-full flex items-center justify-center space-x-2 py-3 px-4 rounded-xl font-medium transition duration-200 ${
            isLoading || !policyText.trim()
              ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
              : 'bg-blue-600 text-white hover:bg-blue-700 shadow-lg shadow-blue-200'
          }`}
        >
          {isLoading ? (
            <>
              <Loader2 className="h-5 w-5 animate-spin" />
              <span>Analyzing Policy...</span>
            </>
          ) : (
            <>
              <Shield className="h-5 w-5" />
              <span>Generate & Deploy Policy</span>
            </>
          )}
        </button>
      </form>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start space-x-3">
          <AlertCircle className="h-5 w-5 text-red-500 mt-0.5" />
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {result && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-4 space-y-3">
          <div className="flex items-center space-x-2">
            <Check className="h-5 w-5 text-green-500" />
            <h3 className="font-medium text-green-900">Policy Created Successfully</h3>
          </div>
          <div className="text-sm text-green-800 space-y-1">
            <p><span className="font-semibold">Policy ID:</span> {result.policy_id}</p>
            <p><span className="font-semibold">Rules Created:</span> {result.rules_created}</p>
            <p>{result.message}</p>
          </div>
        </div>
      )}

      <div className="mt-8 p-4 bg-blue-50 rounded-xl border border-blue-100">
        <h4 className="text-sm font-semibold text-blue-900 mb-2">Examples:</h4>
        <ul className="text-xs text-blue-800 space-y-2 list-disc pl-4">
          <li>"Prevent any agent from writing to the production database without a level 2 approval."</li>
          <li>"Flag any GitHub commits that contain strings looking like private keys or tokens."</li>
          <li>"Block all outgoing emails to domains other than @company.com."</li>
        </ul>
      </div>
    </div>
  );
};

export default PolicyCreator;