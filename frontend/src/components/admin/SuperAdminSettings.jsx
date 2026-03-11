import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Key, Cpu, Save, Loader2, Eye, EyeOff, CheckCircle, DollarSign } from 'lucide-react';
import { toast } from 'sonner';
import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

const AI_MODELS = [
  { value: 'openai/gpt-4o', label: 'GPT-4o (Recommended)' },
  { value: 'openai/gpt-4o-mini', label: 'GPT-4o Mini (Faster)' },
  { value: 'openai/gpt-4-turbo', label: 'GPT-4 Turbo' },
  { value: 'anthropic/claude-3.5-sonnet', label: 'Claude 3.5 Sonnet' },
  { value: 'anthropic/claude-3-opus', label: 'Claude 3 Opus' },
  { value: 'google/gemini-pro-1.5', label: 'Gemini Pro 1.5' },
  { value: 'meta-llama/llama-3-70b-instruct', label: 'Llama 3 70B' },
];

export const SuperAdminSettings = () => {
  const [settings, setSettings] = useState({
    openrouter_api_key: '',
    model_name: 'openai/gpt-4o-mini',
    default_credits_new_user: 100.0,
    openrouter_api_key_masked: ''
  });
  const [creditRates, setCreditRates] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);
  const [newApiKey, setNewApiKey] = useState('');

  useEffect(() => {
    loadSettings();
  }, []);

  const getAuthHeaders = () => {
    const token = localStorage.getItem('admin_token');
    return {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    };
  };

  const loadSettings = async () => {
    try {
      const [settingsRes, ratesRes] = await Promise.all([
        axios.get(`${API_URL}/api/admin/settings`, getAuthHeaders()),
        axios.get(`${API_URL}/api/admin/credit-rates`, getAuthHeaders())
      ]);
      
      setSettings(settingsRes.data);
      setCreditRates(ratesRes.data.rates);
    } catch (error) {
      console.error('Failed to load settings:', error);
      toast.error('Failed to load settings');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveSettings = async () => {
    setSaving(true);
    try {
      const updateData = {
        model_name: settings.model_name,
        default_credits_new_user: parseFloat(settings.default_credits_new_user)
      };
      
      if (newApiKey) {
        updateData.openrouter_api_key = newApiKey;
      }
      
      await axios.put(`${API_URL}/api/admin/settings`, updateData, getAuthHeaders());
      toast.success('Settings saved successfully');
      setNewApiKey('');
      loadSettings();
    } catch (error) {
      toast.error('Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveCreditRates = async () => {
    setSaving(true);
    try {
      await axios.put(
        `${API_URL}/api/admin/credit-rates`,
        { rates: creditRates },
        getAuthHeaders()
      );
      toast.success('Credit rates saved successfully');
    } catch (error) {
      toast.error('Failed to save credit rates');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-pulse text-purple-600">Loading settings...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* API Configuration */}
      <Card className="border-slate-100 shadow-soft">
        <CardHeader>
          <CardTitle className="font-heading flex items-center gap-2">
            <Key className="w-5 h-5 text-purple-500" />
            OpenRouter API Configuration
          </CardTitle>
          <CardDescription>
            Configure the global OpenRouter API key for all AI features
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {settings.openrouter_api_key_masked && (
            <div className="flex items-center gap-2 p-3 rounded-lg bg-green-50 text-green-700 text-sm">
              <CheckCircle className="w-4 h-4" />
              API key configured: {settings.openrouter_api_key_masked}
            </div>
          )}
          
          <div className="space-y-2">
            <Label htmlFor="apiKey">
              {settings.openrouter_api_key_masked ? 'Update API Key' : 'API Key'}
            </Label>
            <div className="relative">
              <Input
                id="apiKey"
                type={showApiKey ? 'text' : 'password'}
                value={newApiKey}
                onChange={(e) => setNewApiKey(e.target.value)}
                placeholder={settings.openrouter_api_key_masked ? 'Enter new key to update' : 'sk-or-...'}
                className="pr-10"
              />
              <button
                type="button"
                onClick={() => setShowApiKey(!showApiKey)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-600"
              >
                {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            <p className="text-xs text-slate-600">
              Get your API key from{' '}
              <a 
                href="https://openrouter.ai/keys" 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-purple-600 hover:underline"
              >
                openrouter.ai/keys
              </a>
            </p>
          </div>
        </CardContent>
      </Card>

      {/* AI Model Selection */}
      <Card className="border-slate-100 shadow-soft">
        <CardHeader>
          <CardTitle className="font-heading flex items-center gap-2">
            <Cpu className="w-5 h-5 text-purple-500" />
            AI Model Selection
          </CardTitle>
          <CardDescription>
            Select the default AI model for all operations
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="modelName">Model Name</Label>
            <Input
              id="modelName"
              value={settings.model_name}
              onChange={(e) => setSettings(prev => ({ ...prev, model_name: e.target.value }))}
              placeholder="e.g., openai/gpt-4o or anthropic/claude-3.5-sonnet"
            />
            <p className="text-xs text-slate-600">
              Browse available models at{' '}
              <a 
                href="https://openrouter.ai/models" 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-purple-600 hover:underline"
              >
                openrouter.ai/models
              </a>
            </p>
          </div>
          
          <div className="space-y-2">
            <Label className="text-slate-600 text-sm">Quick Select</Label>
            <div className="flex flex-wrap gap-2">
              {AI_MODELS.map(model => (
                <button
                  key={model.value}
                  type="button"
                  onClick={() => setSettings(prev => ({ ...prev, model_name: model.value }))}
                  className={`px-3 py-1.5 text-xs rounded-full border transition-all ${
                    settings.model_name === model.value
                      ? 'bg-purple-100 border-purple-300 text-purple-700'
                      : 'bg-white border-slate-200 text-slate-600 hover:border-purple-200 hover:bg-purple-50'
                  }`}
                >
                  {model.label}
                </button>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Default Credits */}
      <Card className="border-slate-100 shadow-soft">
        <CardHeader>
          <CardTitle className="font-heading flex items-center gap-2">
            <DollarSign className="w-5 h-5 text-purple-500" />
            Default Credits for New Users
          </CardTitle>
          <CardDescription>
            Set the default credit amount given to newly approved users
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <Label htmlFor="defaultCredits">Default Credits</Label>
            <Input
              id="defaultCredits"
              type="number"
              step="0.01"
              value={settings.default_credits_new_user}
              onChange={(e) => setSettings(prev => ({ ...prev, default_credits_new_user: e.target.value }))}
            />
            <p className="text-xs text-slate-600">
              This amount will be automatically assigned when you approve a new user
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Credit Rates */}
      <Card className="border-slate-100 shadow-soft">
        <CardHeader>
          <CardTitle className="font-heading flex items-center gap-2">
            <DollarSign className="w-5 h-5 text-purple-500" />
            Credit Rate Multipliers
          </CardTitle>
          <CardDescription>
            Set the margin multiplier for different AI operations (multiplied by OpenRouter cost)
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Object.entries(creditRates).map(([operation, rate]) => (
              <div key={operation} className="space-y-2">
                <Label htmlFor={operation} className="text-sm">
                  {operation.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                </Label>
                <Input
                  id={operation}
                  type="number"
                  step="0.1"
                  value={rate}
                  onChange={(e) => setCreditRates(prev => ({ ...prev, [operation]: parseFloat(e.target.value) }))}
                  className="h-9"
                />
              </div>
            ))}
          </div>
          <p className="text-xs text-slate-600 mt-4">
            Example: A multiplier of 1.5 means users pay 1.5x the actual OpenRouter cost
          </p>
        </CardContent>
      </Card>

      {/* Save Buttons */}
      <div className="flex gap-4">
        <Button
          onClick={handleSaveSettings}
          disabled={saving}
          className="flex-1 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white rounded-full py-6"
        >
          {saving ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              <Save className="w-4 h-4 mr-2" />
              Save API & Model Settings
            </>
          )}
        </Button>
        
        <Button
          onClick={handleSaveCreditRates}
          disabled={saving}
          className="flex-1 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white rounded-full py-6"
        >
          {saving ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              <Save className="w-4 h-4 mr-2" />
              Save Credit Rates
            </>
          )}
        </Button>
      </div>
    </div>
  );
};
