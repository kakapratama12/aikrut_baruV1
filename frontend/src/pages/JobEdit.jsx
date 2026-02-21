import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { TopBar } from '../components/layout/TopBar';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Slider } from '../components/ui/slider';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { jobsAPI } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { Sparkles, Save, Loader2, ArrowLeft, Trash2, Plus, Users, Target, Wrench, FileText, PenLine } from 'lucide-react';
import { toast } from 'sonner';

export const JobEdit = () => {
  const { refreshUser } = useAuth();
  const { id } = useParams();
  const isNew = id === 'new';
  const navigate = useNavigate();

  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [generatingPlaybook, setGeneratingPlaybook] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [showGenerateDialog, setShowGenerateDialog] = useState(false);
  const [generateMode, setGenerateMode] = useState('title'); // 'title' or 'narrative'
  const [narrative, setNarrative] = useState('');

  const [form, setForm] = useState({
    title: '',
    description: {
      about_the_role: '',
      key_responsibilities: '',
      what_you_will_do: ''
    },
    requirements: {
      required_experience: '',
      required_skills: '',
      qualifications: '',
      nice_to_have: ''
    },
    location: '',
    employment_type: 'full-time',
    salary_range: '',
    playbook: null
  });

  useEffect(() => {
    const loadData = async () => {
      if (!isNew) {
        setLoading(true);
        try {
          const res = await jobsAPI.get(id);
          const data = res.data;

          // Helper to parse legacy strings into new object format
          const parseLegacyText = (text) => {
            if (typeof text === 'object' && text !== null) return text;
            try { return JSON.parse(text); } catch { return text; }
          };

          const rawDesc = parseLegacyText(data.description);
          const rawReq = parseLegacyText(data.requirements);

          setForm({
            title: String(data.title || ''),
            description: {
              about_the_role: rawDesc?.about_the_role || (typeof rawDesc === 'string' ? rawDesc : ''),
              key_responsibilities: rawDesc?.key_responsibilities || '',
              what_you_will_do: rawDesc?.what_you_will_do || ''
            },
            requirements: {
              required_experience: rawReq?.required_experience || (typeof rawReq === 'string' ? rawReq : ''),
              required_skills: rawReq?.required_skills || '',
              qualifications: rawReq?.qualifications || '',
              nice_to_have: rawReq?.nice_to_have || ''
            },
            location: String(data.location || ''),
            employment_type: data.employment_type || 'full-time',
            salary_range: String(data.salary_range || ''),
            playbook: data.playbook || null
          });
        } catch (error) {
          console.error('Failed to load job:', error);
          toast.error('Failed to load job');
          navigate('/jobs');
        } finally {
          setLoading(false);
        }
      } else {
        // Reset form for new job
        setLoading(false);
        setForm({
          title: '',
          description: {
            about_the_role: '',
            key_responsibilities: '',
            what_you_will_do: ''
          },
          requirements: {
            required_experience: '',
            required_skills: '',
            qualifications: '',
            nice_to_have: ''
          },
          location: '',
          employment_type: 'full-time',
          salary_range: '',
          playbook: null
        });
      }
    };

    loadData();
  }, [id, isNew, navigate]);

  const handleSave = async () => {
    if (!form.title.trim()) {
      toast.error('Job title is required');
      return;
    }
    // Check if at least "about the role" is filled
    if (!form.description?.about_the_role?.trim()) {
      toast.error('Job description (About the Role) is required');
      return;
    }

    setSaving(true);
    try {
      // Ensure all fields are properly typed before sending
      const jobData = {
        title: String(form.title || ''),
        description: form.description,
        requirements: form.requirements,
        location: String(form.location || ''),
        employment_type: form.employment_type || 'full-time',
        salary_range: String(form.salary_range || ''),
        playbook: form.playbook || null
      };

      if (isNew) {
        const res = await jobsAPI.create(jobData);
        toast.success('Job created');
        navigate(`/jobs/${res.data.id}`);
      } else {
        await jobsAPI.update(id, jobData);
        toast.success('Job updated');
      }
    } catch (error) {
      console.error('Save error:', error);
      toast.error(error.response?.data?.detail || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm('Are you sure you want to delete this job?')) return;

    setDeleting(true);
    try {
      await jobsAPI.delete(id);
      toast.success('Job deleted');
      navigate('/jobs');
    } catch (error) {
      toast.error('Failed to delete job');
    } finally {
      setDeleting(false);
    }
  };

  const handleGenerateDescription = async () => {
    if (generateMode === 'title' && !form.title.trim()) {
      toast.error('Enter a job title first');
      return;
    }
    if (generateMode === 'narrative' && !narrative.trim()) {
      toast.error('Enter a job description narrative first');
      return;
    }

    setGenerating(true);
    try {
      const context = generateMode === 'narrative' ? narrative : '';
      const res = await jobsAPI.generateDescription(form.title || 'Job Position', context);

      console.log('API Response:', res.data); // Debug log

      // Recursive helper to flatten any value to string
      const flattenToString = (val, depth = 0) => {
        if (depth > 5) return String(val); // Prevent infinite recursion
        if (val === null || val === undefined) return '';
        if (typeof val === 'string') return val;
        if (typeof val === 'number' || typeof val === 'boolean') return String(val);
        if (Array.isArray(val)) {
          return val.map((item, i) => {
            const flat = flattenToString(item, depth + 1);
            return flat ? flat : '';
          }).filter(Boolean).join('\n');
        }
        if (typeof val === 'object') {
          // Try to extract text from common keys
          const textKeys = ['text', 'content', 'value', 'description', 'name', 'title'];
          for (const key of textKeys) {
            if (val[key] && typeof val[key] === 'string') {
              return val[key];
            }
          }
          // Otherwise, format as key-value pairs
          const entries = Object.entries(val);
          if (entries.length > 0) {
            return entries.map(([k, v]) => {
              const flat = flattenToString(v, depth + 1);
              return flat ? `${k}: ${flat}` : '';
            }).filter(Boolean).join('\n');
          }
          return '';
        }
        return String(val);
      };

      // Handle response
      let newDescription = {
        about_the_role: '',
        key_responsibilities: '',
        what_you_will_do: ''
      };

      let newRequirements = {
        required_experience: '',
        required_skills: '',
        qualifications: '',
        nice_to_have: ''
      };

      if (res.data && res.data.description && typeof res.data.description === 'object') {
        newDescription = { ...newDescription, ...res.data.description };
      }
      if (res.data && res.data.requirements && typeof res.data.requirements === 'object') {
        newRequirements = { ...newRequirements, ...res.data.requirements };
      }

      setForm(prev => ({
        ...prev,
        description: newDescription,
        requirements: newRequirements
      }));

      toast.success('Job description generated!');
      setShowGenerateDialog(false);
      setNarrative('');
    } catch (error) {
      console.error('Generate error:', error);
      toast.error(error.response?.data?.detail || 'Failed to generate description');
    } finally {
      setGenerating(false);
      // Refresh credits after AI generation
      await refreshUser();
    }
  };

  const handleGeneratePlaybook = async () => {
    if (isNew) {
      toast.error('Save the job first before generating playbook');
      return;
    }

    setGeneratingPlaybook(true);
    try {
      const res = await jobsAPI.generatePlaybook(id);
      setForm(prev => ({ ...prev, playbook: res.data.playbook }));
      toast.success('Playbook generated!');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to generate playbook');
    } finally {
      setGeneratingPlaybook(false);
      // Refresh credits after AI generation
      await refreshUser();
    }
  };

  const updatePlaybookItem = (category, index, field, value) => {
    setForm(prev => ({
      ...prev,
      playbook: {
        ...prev.playbook,
        [category]: prev.playbook[category].map((item, i) =>
          i === index ? { ...item, [field]: value } : item
        )
      }
    }));
  };

  const addPlaybookItem = (category) => {
    setForm(prev => ({
      ...prev,
      playbook: {
        ...prev.playbook,
        [category]: [...(prev.playbook?.[category] || []), { id: crypto.randomUUID(), name: '', description: '', weight: 0 }]
      }
    }));
  };

  const removePlaybookItem = (category, index) => {
    setForm(prev => ({
      ...prev,
      playbook: {
        ...prev.playbook,
        [category]: prev.playbook[category].filter((_, i) => i !== index)
      }
    }));
  };

  const getCategoryWeight = (category) => {
    return (form.playbook?.[category] || []).reduce((sum, item) => sum + (item.weight || 0), 0);
  };

  const getCategoryIcon = (category) => {
    switch (category) {
      case 'character': return Users;
      case 'requirement': return Target;
      case 'skill': return Wrench;
      default: return Users;
    }
  };

  const updateNestedField = (parent, field, value) => {
    setForm(prev => ({
      ...prev,
      [parent]: {
        ...prev[parent],
        [field]: value
      }
    }));
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-pulse text-indigo-500">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen" data-testid="job-edit-page">
      <TopBar
        title={isNew ? 'Create Job' : 'Edit Job'}
        subtitle={form.title || 'New position'}
      />

      <div className="p-8 max-w-4xl">
        <Button
          variant="ghost"
          onClick={() => navigate('/jobs')}
          className="mb-6"
          data-testid="back-btn"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Jobs
        </Button>

        <Tabs defaultValue="details" className="space-y-6">
          <TabsList className="bg-slate-100 p-1 rounded-full">
            <TabsTrigger value="details" className="rounded-full px-6">Job Details</TabsTrigger>
            <TabsTrigger value="playbook" className="rounded-full px-6">Evaluation Playbook</TabsTrigger>
          </TabsList>

          {/* Job Details Tab */}
          <TabsContent value="details" className="space-y-6 animate-fade-in">
            <Card className="border-slate-100 shadow-soft">
              <CardHeader>
                <CardTitle className="font-heading">Job Information</CardTitle>
                <CardDescription>Basic details about the position</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="title">Job Title *</Label>
                    <Input
                      id="title"
                      value={form.title}
                      onChange={(e) => setForm(prev => ({ ...prev, title: e.target.value }))}
                      placeholder="Software Engineer"
                      data-testid="job-title"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="location">Location</Label>
                    <Input
                      id="location"
                      value={form.location}
                      onChange={(e) => setForm(prev => ({ ...prev, location: e.target.value }))}
                      placeholder="Remote / New York"
                      data-testid="job-location"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="type">Employment Type</Label>
                    <Select
                      value={form.employment_type}
                      onValueChange={(v) => setForm(prev => ({ ...prev, employment_type: v }))}
                    >
                      <SelectTrigger data-testid="job-type">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="full-time">Full-time</SelectItem>
                        <SelectItem value="part-time">Part-time</SelectItem>
                        <SelectItem value="contract">Contract</SelectItem>
                        <SelectItem value="internship">Internship</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="salary">Salary Range</Label>
                    <Input
                      id="salary"
                      value={form.salary_range}
                      onChange={(e) => setForm(prev => ({ ...prev, salary_range: e.target.value }))}
                      placeholder="$80,000 - $120,000"
                      data-testid="job-salary"
                    />
                  </div>
                </div>

                <div className="space-y-6 pt-4 border-t border-slate-100">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-lg font-semibold text-slate-800">Job Description</h3>
                      <p className="text-sm text-slate-500">Provide rich narrative and clear responsibilities.</p>
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setShowGenerateDialog(true)}
                      disabled={generating}
                      className="text-indigo-600 hover:text-indigo-700 bg-indigo-50 hover:bg-indigo-100"
                      data-testid="generate-desc-btn"
                    >
                      {generating ? (
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      ) : (
                        <Sparkles className="w-4 h-4 mr-2" />
                      )}
                      Generate All with AI
                    </Button>
                  </div>

                  <div className="space-y-4 pl-4 border-l-2 border-indigo-100">
                    <div className="space-y-2">
                      <Label htmlFor="about_the_role">About the Role *</Label>
                      <Textarea
                        id="about_the_role"
                        value={form.description.about_the_role}
                        onChange={(e) => updateNestedField('description', 'about_the_role', e.target.value)}
                        placeholder="2-4 narrative sentences explaining the role's purpose and value..."
                        rows={3}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="key_responsibilities">Key Responsibilities</Label>
                      <Textarea
                        id="key_responsibilities"
                        value={form.description.key_responsibilities}
                        onChange={(e) => updateNestedField('description', 'key_responsibilities', e.target.value)}
                        placeholder="Detail the daily impact. Start with numbers (1., 2.) for main points..."
                        rows={4}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="what_you_will_do">What You'll Do</Label>
                      <Textarea
                        id="what_you_will_do"
                        value={form.description.what_you_will_do}
                        onChange={(e) => updateNestedField('description', 'what_you_will_do', e.target.value)}
                        placeholder="Narrative sentences followed by detailed bullet points..."
                        rows={4}
                      />
                    </div>
                  </div>
                </div>

                <div className="space-y-6 pt-4 border-t border-slate-100">
                  <div>
                    <h3 className="text-lg font-semibold text-slate-800">Requirements</h3>
                    <p className="text-sm text-slate-500">Specify what success looks like for candidates.</p>
                  </div>

                  <div className="space-y-4 pl-4 border-l-2 border-purple-100">
                    <div className="space-y-2">
                      <Label htmlFor="required_experience">Required Experience</Label>
                      <Textarea
                        id="required_experience"
                        value={form.requirements.required_experience}
                        onChange={(e) => updateNestedField('requirements', 'required_experience', e.target.value)}
                        placeholder="Years of experience, specific industries, or past roles..."
                        rows={3}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="required_skills">Required Skills</Label>
                      <Textarea
                        id="required_skills"
                        value={form.requirements.required_skills}
                        onChange={(e) => updateNestedField('requirements', 'required_skills', e.target.value)}
                        placeholder="Technical tools, methodologies, or hard skills required..."
                        rows={3}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="qualifications">Qualifications</Label>
                      <Textarea
                        id="qualifications"
                        value={form.requirements.qualifications}
                        onChange={(e) => updateNestedField('requirements', 'qualifications', e.target.value)}
                        placeholder="Degrees, certifications, or educational background..."
                        rows={2}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="nice_to_have">Nice-to-haves</Label>
                      <Textarea
                        id="nice_to_have"
                        value={form.requirements.nice_to_have}
                        onChange={(e) => updateNestedField('requirements', 'nice_to_have', e.target.value)}
                        placeholder="Bonus skills or experiences that would make a candidate stand out..."
                        rows={2}
                      />
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Playbook Tab */}
          <TabsContent value="playbook" className="space-y-6 animate-fade-in">
            {/* AI Generator */}
            <Card className="border-indigo-100 bg-gradient-to-r from-indigo-50 to-purple-50">
              <CardHeader>
                <CardTitle className="font-heading flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-indigo-500" />
                  AI Playbook Generator
                </CardTitle>
                <CardDescription>
                  Generate evaluation criteria based on the job description
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Button
                  onClick={handleGeneratePlaybook}
                  disabled={generatingPlaybook || isNew}
                  className="bg-indigo-500 hover:bg-indigo-600 text-white rounded-full"
                  data-testid="generate-playbook-btn"
                >
                  {generatingPlaybook ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Generating...
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4 mr-2" />
                      Generate Playbook
                    </>
                  )}
                </Button>
                {isNew && (
                  <p className="text-sm text-slate-500 mt-2">Save the job first to enable playbook generation</p>
                )}
              </CardContent>
            </Card>

            {/* Playbook Categories */}
            {['character', 'requirement', 'skill'].map((category) => {
              const Icon = getCategoryIcon(category);
              const items = form.playbook?.[category] || [];
              const totalWeight = getCategoryWeight(category);
              const isValid = items.length === 0 || Math.abs(totalWeight - 100) < 0.1;

              return (
                <Card key={category} className="border-slate-100 shadow-soft">
                  <CardHeader className="flex flex-row items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-indigo-50 flex items-center justify-center">
                        <Icon className="w-5 h-5 text-indigo-500" />
                      </div>
                      <div>
                        <CardTitle className="font-heading capitalize">{category}</CardTitle>
                        <CardDescription>
                          {category === 'character' && 'Personality traits, soft skills, cultural fit'}
                          {category === 'requirement' && 'Education, experience, certifications'}
                          {category === 'skill' && 'Technical abilities, tools, domain expertise'}
                        </CardDescription>
                      </div>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => addPlaybookItem(category)}
                      className="rounded-full"
                      data-testid={`add-${category}-btn`}
                    >
                      <Plus className="w-4 h-4 mr-1" />
                      Add
                    </Button>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {items.length === 0 ? (
                      <p className="text-sm text-slate-500 text-center py-4">No criteria defined</p>
                    ) : (
                      <>
                        {items.map((item, index) => (
                          <div key={item.id} className="p-4 rounded-xl bg-slate-50 space-y-3">
                            <div className="flex items-start gap-4">
                              <div className="flex-1 space-y-3">
                                <Input
                                  value={item.name}
                                  onChange={(e) => updatePlaybookItem(category, index, 'name', e.target.value)}
                                  placeholder="Criterion name"
                                  className="font-medium"
                                />
                                <Textarea
                                  value={item.description}
                                  onChange={(e) => updatePlaybookItem(category, index, 'description', e.target.value)}
                                  placeholder="What to evaluate"
                                  rows={2}
                                />
                                <div className="flex items-center gap-4">
                                  <Label className="text-sm text-slate-500 w-20">Weight:</Label>
                                  <Slider
                                    value={[item.weight || 0]}
                                    onValueChange={([v]) => updatePlaybookItem(category, index, 'weight', v)}
                                    max={100}
                                    step={1}
                                    className="flex-1"
                                  />
                                  <div className="flex items-center gap-1 w-24">
                                    <Input
                                      type="number"
                                      min="0"
                                      max="100"
                                      value={item.weight === 0 ? '' : item.weight}
                                      onChange={(e) => {
                                        let v = parseInt(e.target.value, 10);
                                        if (isNaN(v)) v = 0;
                                        if (v > 100) v = 100;
                                        if (v < 0) v = 0;
                                        updatePlaybookItem(category, index, 'weight', v);
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
                                onClick={() => removePlaybookItem(category, index)}
                                className="text-slate-400 hover:text-red-500"
                              >
                                <Trash2 className="w-4 h-4" />
                              </Button>
                            </div>
                          </div>
                        ))}

                        <div className={`flex items-center justify-between p-3 rounded-lg ${isValid ? 'bg-green-50' : 'bg-red-50'}`}>
                          <span className={`text-sm ${isValid ? 'text-green-700' : 'text-red-700'}`}>
                            Total Weight: {totalWeight.toFixed(0)}%
                          </span>
                          <span className={`text-xs ${isValid ? 'text-green-600' : 'text-red-600'}`}>
                            {isValid ? '✓ Valid' : 'Must equal 100%'}
                          </span>
                        </div>
                      </>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </TabsContent>
        </Tabs>

        {/* Action Buttons */}
        <div className="flex justify-between mt-6">
          {!isNew && (
            <Button
              variant="outline"
              onClick={handleDelete}
              disabled={deleting}
              className="text-red-600 hover:text-red-700 hover:bg-red-50"
              data-testid="delete-job-btn"
            >
              {deleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4 mr-2" />}
              Delete Job
            </Button>
          )}
          <div className="flex-1" />
          <Button
            onClick={handleSave}
            disabled={saving}
            className="bg-indigo-500 hover:bg-indigo-600 text-white rounded-full px-8"
            data-testid="save-job-btn"
          >
            {saving ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="w-4 h-4 mr-2" />
                {isNew ? 'Create Job' : 'Save Changes'}
              </>
            )}
          </Button>
        </div>

        {/* Generate Description Dialog */}
        <Dialog open={showGenerateDialog} onOpenChange={setShowGenerateDialog}>
          <DialogContent className="sm:max-w-lg">
            <DialogHeader>
              <DialogTitle className="font-heading flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-indigo-500" />
                Generate Job Description
              </DialogTitle>
              <DialogDescription>
                Choose how you want to generate the job description and requirements
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 pt-4">
              {/* Option 1: Based on Title */}
              <div
                onClick={() => setGenerateMode('title')}
                className={`p-4 rounded-xl border-2 cursor-pointer transition-all ${generateMode === 'title'
                  ? 'border-indigo-500 bg-indigo-50'
                  : 'border-slate-200 hover:border-indigo-200'
                  }`}
                data-testid="generate-mode-title"
              >
                <div className="flex items-start gap-3">
                  <div className={`p-2 rounded-lg ${generateMode === 'title' ? 'bg-indigo-100' : 'bg-slate-100'}`}>
                    <FileText className={`w-5 h-5 ${generateMode === 'title' ? 'text-indigo-600' : 'text-slate-500'}`} />
                  </div>
                  <div>
                    <p className="font-medium text-slate-900">Generate from Job Title</p>
                    <p className="text-sm text-slate-500 mt-1">
                      AI will generate a standard job description based on the job title: <strong>{form.title || '(enter title first)'}</strong>
                    </p>
                  </div>
                </div>
              </div>

              {/* Option 2: Based on Narrative */}
              <div
                onClick={() => setGenerateMode('narrative')}
                className={`p-4 rounded-xl border-2 cursor-pointer transition-all ${generateMode === 'narrative'
                  ? 'border-indigo-500 bg-indigo-50'
                  : 'border-slate-200 hover:border-indigo-200'
                  }`}
                data-testid="generate-mode-narrative"
              >
                <div className="flex items-start gap-3">
                  <div className={`p-2 rounded-lg ${generateMode === 'narrative' ? 'bg-indigo-100' : 'bg-slate-100'}`}>
                    <PenLine className={`w-5 h-5 ${generateMode === 'narrative' ? 'text-indigo-600' : 'text-slate-500'}`} />
                  </div>
                  <div className="flex-1">
                    <p className="font-medium text-slate-900">Generate from Narrative</p>
                    <p className="text-sm text-slate-500 mt-1">
                      Describe the role in your own words and AI will create a structured job description
                    </p>
                  </div>
                </div>
              </div>

              {/* Narrative Input (only shown when narrative mode selected) */}
              {generateMode === 'narrative' && (
                <div className="space-y-2 animate-fade-in">
                  <Label htmlFor="narrative">Describe the role</Label>
                  <Textarea
                    id="narrative"
                    value={narrative}
                    onChange={(e) => setNarrative(e.target.value)}
                    placeholder="Example: We need a senior backend developer who will work on our microservices architecture. They should have experience with Python, FastAPI, and cloud technologies. The role involves designing APIs, optimizing database performance, and mentoring junior developers..."
                    rows={5}
                    data-testid="generate-narrative-input"
                  />
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex justify-end gap-3 pt-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowGenerateDialog(false);
                    setNarrative('');
                  }}
                  className="rounded-full"
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleGenerateDescription}
                  disabled={generating || (generateMode === 'title' && !form.title) || (generateMode === 'narrative' && !narrative.trim())}
                  className="bg-indigo-500 hover:bg-indigo-600 text-white rounded-full"
                  data-testid="generate-confirm-btn"
                >
                  {generating ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Generating...
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4 mr-2" />
                      Generate
                    </>
                  )}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
};
