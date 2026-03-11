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
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '../components/ui/alert-dialog';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '../components/ui/accordion';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '../components/ui/dropdown-menu';
import { Switch } from '../components/ui/switch';
import { jobsAPI } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { Sparkles, Save, Loader2, ArrowLeft, Trash2, Plus, Users, Target, Wrench, FileText, PenLine, Zap, ListChecks } from 'lucide-react';
import { toast } from 'sonner';

const formatCurrencyInput = (val) => {
  if (!val) return '';
  // Allow only digits and hyphen
  let cleaned = val.replace(/[^\d-]/g, '');
  const parts = cleaned.split('-');
  if (parts.length > 1) {
    const p1 = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    const p2 = parts[1].replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    return `${p1} - ${p2}`;
  }
  return cleaned.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
};

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
    description: '',
    requirements: '',
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

          // Helper to convert legacy JSON objects to strings if they exist
          const flattenLegacyObject = (obj) => {
            if (!obj) return '';
            if (typeof obj === 'string') return obj;
            try {
              if (typeof obj === 'object') {
                return Object.entries(obj)
                  .map(([k, v]) => `${k.replace(/_/g, ' ').toUpperCase()}:\n${v}`)
                  .join('\n\n');
              }
            } catch { return String(obj); }
            return String(obj);
          };

          setForm({
            title: String(data.title || ''),
            description: flattenLegacyObject(data.description),
            requirements: flattenLegacyObject(data.requirements),
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
          description: '',
          requirements: '',
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

      setForm(prev => ({
        ...prev,
        description: res.data.description || '',
        requirements: res.data.requirements || ''
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

  const handleToneRefinement = async (mode) => {
    if (!form.title.trim()) {
      toast.error('Enter a job title first');
      return;
    }

    const currentContext = `
Job Description:
${form.description}

Requirements & Qualifications:
${form.requirements}
`.trim();

    if (!form.description.trim() && !form.requirements.trim()) {
      toast.error('Please generate from scratch or enter some details first.');
      return;
    }

    setGenerating(true);
    try {
      const res = await jobsAPI.generateDescription(form.title, currentContext, mode);

      setForm(prev => ({
        ...prev,
        description: res.data.description || '',
        requirements: res.data.requirements || ''
      }));

      toast.success('Job details refined successfully!');
    } catch (error) {
      console.error('Refine error:', error);
      toast.error(error.response?.data?.detail || 'Failed to refine description');
    } finally {
      setGenerating(false);
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

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-pulse text-indigo-500">Loading...</div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col overflow-hidden" data-testid="job-edit-page">
      <TopBar
        title={isNew ? 'Create Job' : 'Edit Job'}
        subtitle={form.title || 'New position'}
      />

      <div className="px-6 pt-4">
        <div className="flex items-center justify-between mb-3">
          <Button
            variant="ghost"
            onClick={() => navigate('/jobs')}
            className=""
            data-testid="back-btn"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Jobs
          </Button>
        </div>

        <Tabs defaultValue="details">
          <TabsList className="bg-slate-100 p-1 rounded-full border border-slate-200 mb-4 shrink-0">
            <TabsTrigger
              value="details"
              className="rounded-full px-6 py-2 transition-all data-[state=active]:bg-indigo-600 data-[state=active]:text-white data-[state=active]:shadow-md font-medium"
            >
              <FileText className="w-4 h-4 mr-2" />
              Job Details
            </TabsTrigger>
            <TabsTrigger
              value="playbook"
              className="rounded-full px-6 py-2 transition-all data-[state=active]:bg-indigo-600 data-[state=active]:text-white data-[state=active]:shadow-md font-medium"
            >
              <ListChecks className="w-4 h-4 mr-2" />
              Evaluation Playbook
            </TabsTrigger>
          </TabsList>

          <TabsContent value="details" className="animate-fade-in mt-0">
            <div className="flex flex-col lg:flex-row gap-4" style={{ height: 'calc(100vh - 270px)' }}>
              {/* Left Column: Job Info */}
              <div className="w-full lg:w-1/4 rounded-xl border border-slate-100 bg-white shadow-sm overflow-y-auto p-6">
                <div className="mb-1.5">
                  <div className="font-semibold leading-none tracking-tight font-heading">Job Information</div>
                  <div className="text-sm text-muted-foreground mt-1.5">Basic details about the position</div>
                </div>
                <div className="space-y-5 pt-0">
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
                    <div className="relative">
                      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-600 font-medium pb-px">IDR</span>
                      <Input
                        id="salary"
                        value={form.salary_range}
                        onChange={(e) => setForm(prev => ({ ...prev, salary_range: formatCurrencyInput(e.target.value) }))}
                        placeholder="8,000,000 - 15,000,000"
                        className="pl-12"
                        data-testid="job-salary"
                      />
                    </div>
                  </div>
                </div>
              </div>
              <div className="w-full lg:w-3/4 rounded-xl border border-slate-100 bg-white shadow-sm overflow-hidden p-4 flex flex-col">
                <div className="flex items-center justify-between shrink-0 mb-4 pb-4 border-b border-slate-100">
                  <div>
                    <h3 className="text-base font-semibold text-slate-800">Role Structure</h3>
                    <p className="text-sm text-slate-500 mt-1">Define the details and requirements of the job.</p>
                  </div>
                  <div className="flex items-center gap-4">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          disabled={generating}
                          className="text-indigo-600 border-indigo-200 hover:text-indigo-700 hover:bg-indigo-50 h-8 text-xs font-medium"
                          data-testid="generate-desc-dropdown-btn"
                        >
                          {generating ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Sparkles className="w-3 h-3 mr-1" />}
                          {generating ? 'Processing...' : 'AI Generate'}
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-56">
                        <DropdownMenuItem onClick={() => setShowGenerateDialog(true)} className="cursor-pointer py-2">
                          <Sparkles className="w-4 h-4 mr-2 text-indigo-500" /> Generate from Scratch
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => handleToneRefinement('improve')} className="cursor-pointer py-2">
                          <PenLine className="w-4 h-4 mr-2 text-blue-500" /> Improve Existing Text
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => handleToneRefinement('concise')} className="cursor-pointer py-2">
                          <Zap className="w-4 h-4 mr-2 text-amber-500" /> Make More Concise
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => handleToneRefinement('detailed')} className="cursor-pointer py-2">
                          <FileText className="w-4 h-4 mr-2 text-emerald-500" /> Make More Detailed
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </div>

                <div className="flex-1 overflow-y-auto pr-2 space-y-6 animate-fade-in">
                  <div className="space-y-2">
                    <Label htmlFor="job-description" className="text-sm font-semibold text-slate-800">Job Description *</Label>
                    <Textarea
                      id="job-description"
                      value={form.description}
                      onChange={(e) => setForm(prev => ({ ...prev, description: e.target.value }))}
                      placeholder="Enter the full job description (e.g., About the role, Key responsibilities, What you'll do)..."
                      className="min-h-[250px] resize-y"
                    />
                  </div>
                  <div className="space-y-2 pb-6">
                    <Label htmlFor="job-requirements" className="text-sm font-semibold text-slate-800">Requirements & Qualifications</Label>
                    <Textarea
                      id="job-requirements"
                      value={form.requirements}
                      onChange={(e) => setForm(prev => ({ ...prev, requirements: e.target.value }))}
                      placeholder="Enter the requirements (e.g., Required experience, Required skills, Qualifications, Nice-to-haves)..."
                      className="min-h-[250px] resize-y"
                    />
                  </div>
                </div>
              </div>
            </div>
          </TabsContent>

          {/* Playbook Tab */}
          <TabsContent value="playbook" className="animate-fade-in mt-0">
            <div className="flex flex-col lg:flex-row gap-4" style={{ height: 'calc(100vh - 270px)' }}>
              {/* Left Column: AI Generator */}
              <div className="w-full lg:w-1/4 overflow-y-auto">
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
                      <p className="text-sm text-slate-600 mt-2">Save the job first to enable playbook generation</p>
                    )}
                  </CardContent>
                </Card>
              </div>

              {/* Right Column: Playbook Categories */}
              <div className="w-full lg:w-3/4 overflow-y-auto space-y-6">
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
                          <p className="text-sm text-slate-600 text-center py-4">No criteria defined</p>
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
                                      <Label className="text-sm text-slate-600 w-20">Weight:</Label>
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
                                        <span className="text-sm font-medium text-slate-600">%</span>
                                      </div>
                                    </div>
                                  </div>
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => removePlaybookItem(category, index)}
                                    className="text-slate-500 hover:text-red-500"
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
              </div>
            </div>
          </TabsContent >
        </Tabs >

        {/* Generate Description Dialog */}
        < Dialog open={showGenerateDialog} onOpenChange={setShowGenerateDialog} >
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
                    <FileText className={`w-5 h-5 ${generateMode === 'title' ? 'text-indigo-600' : 'text-slate-600'}`} />
                  </div>
                  <div>
                    <p className="font-medium text-slate-900">Generate from Job Title</p>
                    <p className="text-sm text-slate-600 mt-1">
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
                    <PenLine className={`w-5 h-5 ${generateMode === 'narrative' ? 'text-indigo-600' : 'text-slate-600'}`} />
                  </div>
                  <div className="flex-1">
                    <p className="font-medium text-slate-900">Generate from Narrative</p>
                    <p className="text-sm text-slate-600 mt-1">
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
        </Dialog >

        {/* Global Sticky Action Footer */}
        < div className="fixed bottom-0 left-0 right-0 lg:left-64 bg-white/80 backdrop-blur-md border-t border-slate-200 p-4 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.05)] z-40 flex justify-between items-center sm:px-8" >
          <div>
            {!isNew && (
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button
                    variant="ghost"
                    className="text-red-600 hover:text-red-700 hover:bg-red-50 rounded-full"
                    data-testid="delete-job-btn-footer"
                  >
                    {deleting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Trash2 className="w-4 h-4 mr-2" />}
                    Delete Job
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
                    <AlertDialogDescription>
                      This action cannot be undone. This will permanently delete the job "{form.title}" and remove its data from our servers.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction onClick={handleDelete} className="bg-red-600 hover:bg-red-700 text-white">Delete</AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            )}
          </div>
          <div className="flex items-center gap-4">
            <Button
              onClick={handleSave}
              disabled={saving}
              className="bg-indigo-500 hover:bg-indigo-600 text-white rounded-full shadow-soft px-8"
              data-testid="save-job-btn-footer"
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
        </div >
      </div >
    </div >
  );
};
