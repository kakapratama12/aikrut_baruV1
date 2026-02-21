import React, { useState, useEffect } from 'react';
import { TopBar } from '../components/layout/TopBar';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Slider } from '../components/ui/slider';
import { companyAPI } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { Building2, Sparkles, Plus, Trash2, Save, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

export const Company = () => {
  const [company, setCompany] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [narrative, setNarrative] = useState('');

  const [form, setForm] = useState({
    name: '',
    description: '',
    industry: '',
    website: '',
    values: []
  });

  const { user, updateUser, refreshUser } = useAuth();

  useEffect(() => {
    loadCompany();
  }, []);

  const loadCompany = async () => {
    try {
      const res = await companyAPI.get();
      if (res.data) {
        setCompany(res.data);
        setForm({
          name: res.data.name || '',
          description: res.data.description || '',
          industry: res.data.industry || '',
          website: res.data.website || '',
          values: res.data.values || []
        });
      }
    } catch (error) {
      console.error('Failed to load company:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!form.name.trim()) {
      toast.error('Company name is required');
      return;
    }

    setSaving(true);
    try {
      if (company) {
        await companyAPI.update(form);
        toast.success('Company updated');
      } else {
        const res = await companyAPI.create(form);
        setCompany(res.data);
        updateUser({ ...user, company_id: res.data.id });
        toast.success('Company created');
      }
      loadCompany();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const handleGenerateValues = async () => {
    if (!narrative.trim()) {
      toast.error('Please describe your company culture');
      return;
    }

    setGenerating(true);
    try {
      const res = await companyAPI.generateValues(narrative);
      setForm(prev => ({ ...prev, values: res.data.values }));
      toast.success('Values generated! Review and adjust weights.');
      setNarrative('');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to generate values');
    } finally {
      setGenerating(false);
      // Refresh credits after AI generation
      await refreshUser();
    }
  };

  const addValue = () => {
    setForm(prev => ({
      ...prev,
      values: [...prev.values, { id: crypto.randomUUID(), name: '', description: '', weight: 0 }]
    }));
  };

  const removeValue = (id) => {
    setForm(prev => ({
      ...prev,
      values: prev.values.filter(v => v.id !== id)
    }));
  };

  const updateValue = (id, field, value) => {
    setForm(prev => ({
      ...prev,
      values: prev.values.map(v => v.id === id ? { ...v, [field]: value } : v)
    }));
  };

  const totalWeight = form.values.reduce((sum, v) => sum + (v.weight || 0), 0);
  const isWeightValid = Math.abs(totalWeight - 100) < 0.1;

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-pulse text-indigo-500">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen" data-testid="company-page">
      <TopBar title="Company Settings" subtitle="Manage your company profile and values" />

      <div className="p-8 max-w-4xl">
        <Tabs defaultValue="general" className="space-y-6">
          <TabsList className="bg-slate-100 p-1 rounded-full">
            <TabsTrigger value="general" className="rounded-full px-6">General Info</TabsTrigger>
            <TabsTrigger value="values" className="rounded-full px-6">Company Culture</TabsTrigger>
          </TabsList>

          {/* General Info Tab */}
          <TabsContent value="general" className="space-y-6 animate-fade-in">
            <Card className="border-slate-100 shadow-soft">
              <CardHeader>
                <CardTitle className="font-heading flex items-center gap-2">
                  <Building2 className="w-5 h-5 text-indigo-500" />
                  Company Information
                </CardTitle>
                <CardDescription>Basic details about your organization</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="name">Company Name *</Label>
                    <Input
                      id="name"
                      value={form.name}
                      onChange={(e) => setForm(prev => ({ ...prev, name: e.target.value }))}
                      placeholder="Acme Inc."
                      data-testid="company-name"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="industry">Industry</Label>
                    <Input
                      id="industry"
                      value={form.industry}
                      onChange={(e) => setForm(prev => ({ ...prev, industry: e.target.value }))}
                      placeholder="Technology"
                      data-testid="company-industry"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="website">Website</Label>
                  <Input
                    id="website"
                    value={form.website}
                    onChange={(e) => setForm(prev => ({ ...prev, website: e.target.value }))}
                    placeholder="https://acme.com"
                    data-testid="company-website"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="description">Description</Label>
                  <Textarea
                    id="description"
                    value={form.description}
                    onChange={(e) => setForm(prev => ({ ...prev, description: e.target.value }))}
                    placeholder="Tell us about your company..."
                    rows={4}
                    data-testid="company-description"
                  />
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Company Values Tab */}
          <TabsContent value="values" className="space-y-6 animate-fade-in">
            {/* AI Generator Card */}
            <Card className="border-indigo-100 bg-gradient-to-r from-indigo-50 to-purple-50">
              <CardHeader>
                <CardTitle className="font-heading flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-indigo-500" />
                  AI Value Generator
                </CardTitle>
                <CardDescription>Describe your company culture and let AI generate structured values</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <Textarea
                  value={narrative}
                  onChange={(e) => setNarrative(e.target.value)}
                  placeholder="Example: We value innovation and creative problem-solving. Our team believes in transparency and open communication. We prioritize work-life balance and employee wellbeing. Customer satisfaction is at the heart of everything we do..."
                  rows={4}
                  data-testid="values-narrative"
                />
                <Button
                  onClick={handleGenerateValues}
                  disabled={generating || !narrative.trim()}
                  className="bg-indigo-500 hover:bg-indigo-600 text-white rounded-full"
                  data-testid="generate-values-btn"
                >
                  {generating ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Generating...
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4 mr-2" />
                      Generate Values
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>

            {/* Manual Values Card */}
            <Card className="border-slate-100 shadow-soft">
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="font-heading">Company Culture</CardTitle>
                  <CardDescription>
                    Define values used for candidate evaluation. Weights must total 100%.
                  </CardDescription>
                </div>
                <Button
                  onClick={addValue}
                  variant="outline"
                  size="sm"
                  className="rounded-full"
                  data-testid="add-value-btn"
                >
                  <Plus className="w-4 h-4 mr-1" />
                  Add Value
                </Button>
              </CardHeader>
              <CardContent className="space-y-6">
                {form.values.length === 0 ? (
                  <p className="text-sm text-slate-500 text-center py-8">
                    No values defined. Add manually or use AI generator.
                  </p>
                ) : (
                  <>
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                      {form.values.map((value, index) => (
                        <div key={value.id} className="p-4 rounded-xl bg-slate-50 flex flex-col h-full">
                          <div className="flex items-start gap-4 flex-1">
                            <div className="flex-1 space-y-3 flex flex-col h-full">
                              <Input
                                value={value.name}
                                onChange={(e) => updateValue(value.id, 'name', e.target.value)}
                                placeholder="Value name"
                                className="font-medium"
                                data-testid={`value-name-${index}`}
                              />
                              <Textarea
                                value={value.description}
                                onChange={(e) => updateValue(value.id, 'description', e.target.value)}
                                placeholder="Description"
                                rows={2}
                                data-testid={`value-desc-${index}`}
                              />
                              <div className="flex items-center gap-4 mt-auto pt-2">
                                <Label className="text-sm text-slate-500 w-16">Weight:</Label>
                                <Slider
                                  value={[value.weight || 0]}
                                  onValueChange={([v]) => updateValue(value.id, 'weight', v)}
                                  max={100}
                                  step={1}
                                  className="flex-1"
                                />
                                <div className="flex items-center gap-1 w-20">
                                  <Input
                                    type="number"
                                    min="0"
                                    max="100"
                                    value={value.weight === 0 ? '' : value.weight}
                                    onChange={(e) => {
                                      let v = parseInt(e.target.value, 10);
                                      if (isNaN(v)) v = 0;
                                      if (v > 100) v = 100;
                                      if (v < 0) v = 0;
                                      updateValue(value.id, 'weight', v);
                                    }}
                                    className="h-8 px-2 text-right font-medium"
                                  />
                                  <span className="text-sm font-medium text-slate-500">%</span>
                                </div>
                              </div>
                            </div>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => removeValue(value.id)}
                              className="text-slate-400 hover:text-red-500"
                              data-testid={`remove-value-${index}`}
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>                {/* Weight Validation */}
                    <div className={`flex items-center justify-between p-3 rounded-lg ${isWeightValid ? 'bg-green-50' : 'bg-red-50'}`}>
                      <span className={`text-sm ${isWeightValid ? 'text-green-700' : 'text-red-700'}`}>
                        Total Weight: {totalWeight.toFixed(0)}%
                      </span>
                      <span className={`text-xs ${isWeightValid ? 'text-green-600' : 'text-red-600'}`}>
                        {isWeightValid ? '✓ Valid' : 'Must equal 100%'}
                      </span>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Save Button */}
        <div className="flex justify-end mt-6">
          <Button
            onClick={handleSave}
            disabled={saving || (form.values.length > 0 && !isWeightValid)}
            className="bg-indigo-500 hover:bg-indigo-600 text-white rounded-full px-8"
            data-testid="save-company-btn"
          >
            {saving ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="w-4 h-4 mr-2" />
                Save Changes
              </>
            )}
          </Button>
        </div>
      </div>
    </div >
  );
};
