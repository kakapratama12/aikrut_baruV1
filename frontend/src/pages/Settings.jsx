import React, { useState, useEffect } from 'react';
import { TopBar } from '../components/layout/TopBar';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { settingsAPI } from '../lib/api';
import { Globe, Save, Loader2, DollarSign, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../context/AuthContext';

export const Settings = () => {
  const { user } = useAuth();
  const [settings, setSettings] = useState({
    language: 'en'
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const res = await settingsAPI.get();
      setSettings({
        language: res.data.language || 'en'
      });
    } catch (error) {
      console.error('Failed to load settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await settingsAPI.update({
        language: settings.language
      });
      toast.success('Language settings saved');
      loadSettings();
    } catch (error) {
      toast.error('Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-pulse text-indigo-500">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen" data-testid="settings-page">
      <TopBar title="Settings" subtitle="Configure your preferences" />
      
      <div className="p-8 max-w-2xl">
        {/* Credit Balance Card */}
        <Card className="border-slate-100 shadow-soft mb-6 bg-gradient-to-br from-indigo-50 to-purple-50">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center">
                  <DollarSign className="w-6 h-6 text-white" />
                </div>
                <div>
                  <p className="text-sm text-slate-600">Available Credits</p>
                  <p className="text-3xl font-bold text-slate-900">
                    {user?.credits?.toFixed(2) || '0.00'}
                  </p>
                </div>
              </div>
              {user?.credits <= 0 && (
                <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-100 text-red-700 text-sm">
                  <AlertCircle className="w-4 h-4" />
                  <span>Please top up to use AI features</span>
                </div>
              )}
            </div>
            <p className="text-xs text-slate-500 mt-3">
              Credits are used for AI-powered features like CV analysis, job description generation, and more.
              Contact admin to top up your credits.
            </p>
          </CardContent>
        </Card>

        <div className="space-y-6">
          {/* Language Settings */}
          <Card className="border-slate-100 shadow-soft">
            <CardHeader>
              <CardTitle className="font-heading flex items-center gap-2">
                <Globe className="w-5 h-5 text-indigo-500" />
                Language Preferences
              </CardTitle>
              <CardDescription>
                Set your language for the application and AI-generated content
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="appLanguage">Application Language</Label>
                <Select
                  value={settings.language}
                  onValueChange={(v) => setSettings(prev => ({ ...prev, language: v }))}
                >
                  <SelectTrigger data-testid="language-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="en">English</SelectItem>
                    <SelectItem value="id">Indonesian (Bahasa Indonesia)</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-slate-500">
                  This language will be used for the interface and AI-generated analysis results
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Info Card */}
          <Card className="border-blue-100 bg-blue-50 shadow-soft">
            <CardContent className="pt-6">
              <div className="flex gap-3">
                <AlertCircle className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                <div className="text-sm text-blue-900">
                  <p className="font-medium mb-1">Administrator Managed Settings</p>
                  <p className="text-blue-700">
                    AI model configuration and API settings are managed by your administrator.
                    If you need assistance with these settings, please contact your admin.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Save Button */}
          <Button
            onClick={handleSave}
            disabled={saving}
            className="w-full bg-indigo-500 hover:bg-indigo-600 text-white rounded-full py-6"
            data-testid="save-settings-btn"
          >
            {saving ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="w-4 h-4 mr-2" />
                Save Settings
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
};
