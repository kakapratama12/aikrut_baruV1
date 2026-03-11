import React, { useState, useEffect } from 'react';
import { TopBar } from '../components/layout/TopBar';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Textarea } from '../components/ui/textarea';
import { Label } from '../components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { adminSettingsAPI } from '../lib/api';
import { 
  Settings, Save, Loader2, RotateCcw, FileText, Users, Briefcase, 
  ClipboardList, BarChart3, AlertTriangle, CheckCircle
} from 'lucide-react';
import { toast } from 'sonner';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '../components/ui/accordion';

const PROMPT_CONFIG = [
  {
    key: 'cv_parse_prompt',
    label: 'CV Parser Prompt',
    description: 'Used to extract name, email, and phone from uploaded CVs',
    icon: FileText,
    variables: ['{cv_text}'],
    category: 'talent'
  },
  {
    key: 'company_values_prompt',
    label: 'Company Values Generator',
    description: 'Generates structured company values from a culture narrative',
    icon: Users,
    variables: ['{narrative}', '{language_instruction}'],
    category: 'company'
  },
  {
    key: 'job_desc_title_prompt',
    label: 'Job Description (from Title)',
    description: 'Generates job description and requirements from job title only',
    icon: Briefcase,
    variables: ['{job_title}', '{language_instruction}'],
    category: 'job'
  },
  {
    key: 'job_desc_narrative_prompt',
    label: 'Job Description (from Narrative)',
    description: 'Generates job description from user-provided narrative',
    icon: Briefcase,
    variables: ['{job_title}', '{narrative}', '{language_instruction}'],
    category: 'job'
  },
  {
    key: 'playbook_prompt',
    label: 'Job Playbook Generator',
    description: 'Creates evaluation rubric with Character, Requirement, and Skill categories',
    icon: ClipboardList,
    variables: ['{job_title}', '{job_description}', '{job_requirements}', '{company_values}', '{language_instruction}'],
    category: 'job'
  },
  {
    key: 'job_fit_prompt',
    label: 'Job Fit Analysis',
    description: 'Evaluates candidates against job playbook and company values',
    icon: BarChart3,
    variables: [
      '{job_title}', '{job_description}', '{job_requirements}', '{company_values}',
      '{candidate_name}', '{candidate_evidence}',
      '{character_playbook}', '{requirement_playbook}', '{skill_playbook}',
      '{language_instruction}'
    ],
    category: 'analysis'
  }
];

export const AdminSettings = () => {
  const [settings, setSettings] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState('');

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const res = await adminSettingsAPI.get();
      setSettings(res.data);
    } catch (error) {
      console.error('Failed to load admin settings:', error);
      toast.error('Failed to load settings');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await adminSettingsAPI.update(settings);
      toast.success('Settings saved successfully');
    } catch (error) {
      toast.error('Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async (promptKey) => {
    if (!window.confirm('Reset this prompt to default? Your custom prompt will be lost.')) return;
    
    setResetting(promptKey);
    try {
      await adminSettingsAPI.resetPrompt(promptKey);
      await loadSettings();
      toast.success('Prompt reset to default');
    } catch (error) {
      toast.error('Failed to reset prompt');
    } finally {
      setResetting('');
    }
  };

  const updatePrompt = (key, value) => {
    setSettings(prev => ({ ...prev, [key]: value }));
  };

  const getPromptsByCategory = (category) => {
    return PROMPT_CONFIG.filter(p => p.category === category);
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-pulse text-indigo-500">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen" data-testid="admin-settings-page">
      <TopBar title="Super Admin Settings" subtitle="Configure AI prompts and system behavior" />
      
      <div className="p-8 max-w-5xl">
        {/* Warning Banner */}
        <Card className="border-amber-200 bg-amber-50 mb-6">
          <CardContent className="pt-6">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-600 mt-0.5" />
              <div>
                <p className="font-medium text-amber-800">Advanced Settings</p>
                <p className="text-sm text-amber-700 mt-1">
                  These prompts control how AI generates and evaluates content. Modifying them incorrectly may affect results quality.
                  Each prompt uses variables in curly braces (e.g., {'{job_title}'}) that get replaced with actual data.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Tabs defaultValue="analysis" className="space-y-6">
          <TabsList className="bg-slate-100 p-1 rounded-full">
            <TabsTrigger value="analysis" className="rounded-full px-6">
              <BarChart3 className="w-4 h-4 mr-2" />
              Analysis
            </TabsTrigger>
            <TabsTrigger value="job" className="rounded-full px-6">
              <Briefcase className="w-4 h-4 mr-2" />
              Job
            </TabsTrigger>
            <TabsTrigger value="talent" className="rounded-full px-6">
              <FileText className="w-4 h-4 mr-2" />
              Talent
            </TabsTrigger>
            <TabsTrigger value="company" className="rounded-full px-6">
              <Users className="w-4 h-4 mr-2" />
              Company
            </TabsTrigger>
          </TabsList>

          {['analysis', 'job', 'talent', 'company'].map(category => (
            <TabsContent key={category} value={category} className="space-y-4 animate-fade-in">
              {getPromptsByCategory(category).map(prompt => {
                const Icon = prompt.icon;
                return (
                  <Card key={prompt.key} className="border-slate-100 shadow-soft">
                    <CardHeader className="pb-3">
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-xl bg-indigo-50 flex items-center justify-center">
                            <Icon className="w-5 h-5 text-indigo-500" />
                          </div>
                          <div>
                            <CardTitle className="font-heading text-lg">{prompt.label}</CardTitle>
                            <CardDescription>{prompt.description}</CardDescription>
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleReset(prompt.key)}
                          disabled={resetting === prompt.key}
                          className="text-slate-600 hover:text-slate-700"
                        >
                          {resetting === prompt.key ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <RotateCcw className="w-4 h-4" />
                          )}
                          <span className="ml-1">Reset</span>
                        </Button>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {/* Available Variables */}
                      <div className="flex flex-wrap gap-2">
                        <span className="text-xs text-slate-600">Variables:</span>
                        {prompt.variables.map(v => (
                          <code key={v} className="text-xs bg-slate-100 px-2 py-0.5 rounded text-indigo-600">
                            {v}
                          </code>
                        ))}
                      </div>
                      
                      {/* Prompt Editor */}
                      <Textarea
                        value={settings[prompt.key] || ''}
                        onChange={(e) => updatePrompt(prompt.key, e.target.value)}
                        placeholder="Loading default prompt..."
                        rows={12}
                        className="font-mono text-sm"
                        data-testid={`prompt-${prompt.key}`}
                      />
                    </CardContent>
                  </Card>
                );
              })}
            </TabsContent>
          ))}
        </Tabs>

        {/* Save Button */}
        <div className="flex justify-end mt-6 sticky bottom-6">
          <Button
            onClick={handleSave}
            disabled={saving}
            className="bg-indigo-500 hover:bg-indigo-600 text-white rounded-full px-8 shadow-lg"
            data-testid="save-admin-settings-btn"
          >
            {saving ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="w-4 h-4 mr-2" />
                Save All Changes
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
};
