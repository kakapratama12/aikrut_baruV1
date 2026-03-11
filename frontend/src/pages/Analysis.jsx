import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { TopBar } from '../components/layout/TopBar';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Checkbox } from '../components/ui/checkbox';
import { Progress } from '../components/ui/progress';
import { ScrollArea } from '../components/ui/scroll-area';
import { jobsAPI, candidatesAPI, analysisAPI } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import {
  BarChart3, Play, Loader2, Users, Target, Wrench,
  Search, CheckCircle, AlertCircle, ChevronLeft, ChevronRight,
  FileText, Trash2, UserX, Filter, Tag, X, Briefcase, Eye, Plus
} from 'lucide-react';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '../components/ui/popover';

// Layer 2 category groupings
const LAYER_2_CATEGORIES = {
  "Operations & Admin": [
    "GENERAL_OPERATIONS", "GENERAL_ADMINISTRATION", "HR_OPERATIONS",
    "TALENT_ACQUISITION", "LEARNING_DEVELOPMENT", "PAYROLL_COMPLIANCE",
    "ACCOUNTING_SUPPORT", "FINANCIAL_REPORTING", "FINANCIAL_CONTROL",
    "PROCUREMENT_VENDOR_MANAGEMENT", "LEGAL_COMPLIANCE"
  ],
  "Technology": [
    "SOFTWARE_DEVELOPMENT", "IT_OPERATIONS", "PROJECT_MANAGEMENT",
    "PRODUCT_MANAGEMENT", "QA_TESTING", "DATA_ANALYTICS", "DATA_ENGINEERING",
    "DEVOPS_CLOUD", "UI_UX_DESIGN"
  ],
  "Sales & Marketing": [
    "B2B_SALES", "B2C_SALES", "KEY_ACCOUNT_MANAGEMENT", "DIGITAL_MARKETING",
    "PERFORMANCE_MARKETING", "BRAND_CONTENT", "CUSTOMER_SUPPORT", "CUSTOMER_SUCCESS"
  ],
  "Supply Chain & Engineering": [
    "SUPPLY_CHAIN_MANAGEMENT", "LOGISTICS_OPERATIONS", "NON_IT_ENGINEERING",
    "RESEARCH_DEVELOPMENT"
  ]
};

export const Analysis = () => {
  const { refreshUser } = useAuth();
  const navigate = useNavigate();
  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState('');
  const [selectedJobData, setSelectedJobData] = useState(null);

  // Candidate data and selection
  const [allCandidates, setAllCandidates] = useState([]);
  const [filteredCandidates, setFilteredCandidates] = useState([]);
  const [selectedCandidates, setSelectedCandidates] = useState([]);
  const [candidatesMap, setCandidatesMap] = useState({});
  const [candidateSearch, setCandidateSearch] = useState('');

  // Tag-based filters (AND logic)
  const [tagLibrary, setTagLibrary] = useState(null);
  const [filterLayer1, setFilterLayer1] = useState([]);
  const [filterLayer2, setFilterLayer2] = useState([]);
  const [filterLayer3, setFilterLayer3] = useState('');
  const [filterLayer4, setFilterLayer4] = useState([]);
  const [showFilters, setShowFilters] = useState(false);

  // Popover states
  const [layer1PopoverOpen, setLayer1PopoverOpen] = useState(false);
  const [layer2PopoverOpen, setLayer2PopoverOpen] = useState(false);
  const [layer1Search, setLayer1Search] = useState('');
  const [layer2Search, setLayer2Search] = useState('');

  // Results
  const [results, setResults] = useState([]);
  const [minScore, setMinScore] = useState(0);
  const [selectedResults, setSelectedResults] = useState([]);

  // Loading states
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState({ current: 0, total: 0, status: '', candidateName: '' });

  // Detail view
  const [detailModalResult, setDetailModalResult] = useState(null);
  const [pdfDialogOpen, setPdfDialogOpen] = useState(false);
  const [selectedPdfCandidates, setSelectedPdfCandidates] = useState([]);
  const [generatingPdf, setGeneratingPdf] = useState(false);

  // Culture setup dialog
  const [showCultureDialog, setShowCultureDialog] = useState(false);
  const [pdfJobId, setPdfJobId] = useState('');
  const [pdfAvailableCandidates, setPdfAvailableCandidates] = useState([]);
  const [loadingPdfCandidates, setLoadingPdfCandidates] = useState(false);

  useEffect(() => {
    loadJobs();
    loadAllCandidates();
    loadTagLibrary();
  }, []);

  useEffect(() => {
    applyFilters();
  }, [allCandidates, filterLayer1, filterLayer2, filterLayer3, filterLayer4, candidateSearch]);

  useEffect(() => {
    if (selectedJob) {
      loadResults();
      loadJobData();
    }
  }, [selectedJob, minScore]);

  const loadJobs = async () => {
    try {
      const res = await jobsAPI.list();
      setJobs(res.data);
    } catch (error) {
      console.error('Failed to load jobs:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadJobData = async () => {
    if (!selectedJob) return;
    try {
      const res = await jobsAPI.get(selectedJob);
      setSelectedJobData(res.data);
    } catch (error) {
      console.error('Failed to load job:', error);
    }
  };

  const loadAllCandidates = async () => {
    try {
      const res = await candidatesAPI.list();
      const candidates = res.data || [];
      setAllCandidates(candidates);
      setFilteredCandidates(candidates);
      const map = {};
      candidates.forEach(c => { map[c.id] = c; });
      setCandidatesMap(map);
    } catch (error) {
      console.error('Failed to load candidates:', error);
    }
  };

  const loadTagLibrary = async () => {
    try {
      const res = await candidatesAPI.getTagLibrary();
      setTagLibrary(res.data);
    } catch (error) {
      console.error('Failed to load tag library:', error);
    }
  };

  const loadResults = async () => {
    try {
      const res = await analysisAPI.getForJob(selectedJob, minScore || null);
      setResults(res.data);
      setSelectedResults([]);
    } catch (error) {
      console.error('Failed to load results:', error);
    }
  };

  // Apply tag filters (AND logic)
  const applyFilters = () => {
    let filtered = [...allCandidates];

    // Search filter
    if (candidateSearch) {
      const search = candidateSearch.toLowerCase();
      filtered = filtered.filter(c =>
        c.name?.toLowerCase().includes(search) ||
        c.email?.toLowerCase().includes(search)
      );
    }

    // Layer 1 filter (Domain)
    if (filterLayer1.length > 0) {
      filtered = filtered.filter(c => {
        const candidateTags = (c.tags || []).filter(t => t.layer === 1).map(t => t.tag_value);
        return filterLayer1.every(f => candidateTags.includes(f));
      });
    }

    // Layer 2 filter (Job Family)
    if (filterLayer2.length > 0) {
      filtered = filtered.filter(c => {
        const candidateTags = (c.tags || []).filter(t => t.layer === 2).map(t => t.tag_value);
        return filterLayer2.every(f => candidateTags.includes(f));
      });
    }

    // Layer 3 filter (Skills - text search)
    if (filterLayer3) {
      const skillSearch = filterLayer3.toLowerCase();
      filtered = filtered.filter(c => {
        const candidateSkills = (c.tags || []).filter(t => t.layer === 3).map(t => t.tag_value.toLowerCase());
        return candidateSkills.some(s => s.includes(skillSearch));
      });
    }

    // Layer 4 filter (Scope)
    if (filterLayer4.length > 0) {
      filtered = filtered.filter(c => {
        const candidateTags = (c.tags || []).filter(t => t.layer === 4).map(t => t.tag_value);
        return filterLayer4.every(f => candidateTags.includes(f));
      });
    }

    setFilteredCandidates(filtered);
  };

  const clearFilters = () => {
    setFilterLayer1([]);
    setFilterLayer2([]);
    setFilterLayer3('');
    setFilterLayer4([]);
    setCandidateSearch('');
  };

  const hasActiveFilters = filterLayer1.length > 0 || filterLayer2.length > 0 || filterLayer3 || filterLayer4.length > 0;

  const toggleLayer1Tag = (tag) => {
    if (filterLayer1.includes(tag)) {
      setFilterLayer1(filterLayer1.filter(t => t !== tag));
    } else {
      setFilterLayer1([...filterLayer1, tag]);
    }
  };

  const toggleLayer2Tag = (tag) => {
    if (filterLayer2.includes(tag)) {
      setFilterLayer2(filterLayer2.filter(t => t !== tag));
    } else {
      setFilterLayer2([...filterLayer2, tag]);
    }
  };

  const toggleLayer4Tag = (tag) => {
    if (filterLayer4.includes(tag)) {
      setFilterLayer4(filterLayer4.filter(t => t !== tag));
    } else {
      setFilterLayer4([...filterLayer4, tag]);
    }
  };

  const toggleCandidate = (id) => {
    setSelectedCandidates(prev =>
      prev.includes(id) ? prev.filter(c => c !== id) : [...prev, id]
    );
  };

  const selectAllFiltered = () => {
    const filteredIds = filteredCandidates.map(c => c.id);
    const allSelected = filteredIds.every(id => selectedCandidates.includes(id));

    if (allSelected) {
      setSelectedCandidates(prev => prev.filter(id => !filteredIds.includes(id)));
    } else {
      setSelectedCandidates(prev => [...new Set([...prev, ...filteredIds])]);
    }
  };

  const toggleResultSelection = (id) => {
    setSelectedResults(prev =>
      prev.includes(id) ? prev.filter(r => r !== id) : [...prev, id]
    );
  };

  const selectAllResults = () => {
    if (selectedResults.length === results.length) {
      setSelectedResults([]);
    } else {
      setSelectedResults(results.map(r => r.id));
    }
  };

  const handleBulkDeleteResults = async () => {
    if (selectedResults.length === 0) return;

    if (!window.confirm(`Delete ${selectedResults.length} analysis result(s)? This cannot be undone.`)) return;

    setDeleting(true);
    try {
      await analysisAPI.bulkDelete(selectedResults);
      toast.success(`Deleted ${selectedResults.length} result(s)`);
      setSelectedResults([]);
      loadResults();
    } catch (error) {
      toast.error('Failed to delete results');
    } finally {
      setDeleting(false);
    }
  };

  const runAnalysis = async () => {
    if (!selectedJob) {
      toast.error('Select a job first');
      return;
    }
    if (selectedCandidates.length === 0) {
      toast.error('Select at least one candidate');
      return;
    }

    const job = jobs.find(j => j.id === selectedJob);
    if (!job?.playbook) {
      toast.error('The selected job needs a playbook. Generate one in Job settings.');
      return;
    }

    try {
      const response = await analysisAPI.runStream(selectedJob, selectedCandidates);

      // Handle non-streaming error responses (e.g. 400 from missing company culture)
      if (!response.ok) {
        const text = await response.text().catch(() => '');
        let errorMsg = `Analysis failed (${response.status})`;
        try {
          const errorData = JSON.parse(text);
          errorMsg = errorData?.detail || errorMsg;
        } catch (e) {
          errorMsg = text || errorMsg;
        }

        if (errorMsg.toLowerCase().includes('culture') || errorMsg.toLowerCase().includes('values')) {
          setShowCultureDialog(true);
        } else {
          toast.error(errorMsg);
        }
        return; // Exit without running cleanup
      }

      // Only show progress UI after confirming the stream started successfully
      setAnalyzing(true);
      setAnalysisProgress({ current: 0, total: selectedCandidates.length, status: 'starting', candidateName: '' });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n').filter(line => line.startsWith('data: '));

        for (const line of lines) {
          try {
            const data = JSON.parse(line.slice(6));

            if (data.type === 'progress') {
              setAnalysisProgress({
                current: data.current,
                total: data.total,
                status: data.status,
                candidateName: data.candidate_name || '',
                message: data.message
              });
            } else if (data.type === 'result') {
              setResults(prev => {
                const exists = prev.find(r => r.id === data.analysis.id);
                if (exists) return prev;
                return [...prev, data.analysis].sort((a, b) => b.final_score - a.final_score);
              });
              setAnalysisProgress(prev => ({
                ...prev,
                current: data.current,
                status: 'completed'
              }));
            } else if (data.type === 'error') {
              toast.error(`Failed to analyze: ${data.error}`);
              setAnalysisProgress(prev => ({
                ...prev,
                current: data.current,
                status: 'error'
              }));
            } else if (data.type === 'complete') {
              toast.success(`Analysis complete! ${data.total} candidate(s) processed.`);
            }
          } catch (e) {
            console.error('Parse error:', e);
          }
        }
      }

      // Successful completion cleanup
      setAnalyzing(false);
      setSelectedCandidates([]);
      await refreshUser();
      loadResults();
      loadAllCandidates();

    } catch (error) {
      toast.error(error.message || 'Analysis failed');
      setAnalyzing(false);
      // We do not clear selections or reload on error so the user doesn't lose their state
    }
  };

  // Load candidates with analysis results for selected PDF job
  const loadPdfCandidates = async (jobId) => {
    if (!jobId) {
      setPdfAvailableCandidates([]);
      return;
    }

    setLoadingPdfCandidates(true);
    try {
      // Get analysis results for this job
      const res = await analysisAPI.getForJob(jobId);
      const analysisResults = res.data || [];

      // Filter out deleted candidates and map to include analysis info
      const candidatesWithAnalysis = analysisResults
        .filter(result => candidatesMap[result.candidate_id]) // Only non-deleted
        .map(result => ({
          candidate_id: result.candidate_id,
          candidate_name: candidatesMap[result.candidate_id]?.name || result.candidate_name,
          final_score: result.final_score,
          created_at: result.created_at
        }))
        .sort((a, b) => b.final_score - a.final_score);

      setPdfAvailableCandidates(candidatesWithAnalysis);
    } catch (error) {
      console.error('Failed to load PDF candidates:', error);
      setPdfAvailableCandidates([]);
    } finally {
      setLoadingPdfCandidates(false);
    }
  };

  // Handle PDF job selection change
  const handlePdfJobChange = (jobId) => {
    setPdfJobId(jobId);
    setSelectedPdfCandidates([]);
    loadPdfCandidates(jobId);
  };

  const handleGeneratePDF = async () => {
    if (!pdfJobId) {
      toast.error('Please select a job');
      return;
    }
    if (selectedPdfCandidates.length === 0) {
      toast.error('Please select at least one candidate');
      return;
    }

    setGeneratingPdf(true);
    try {
      const response = await analysisAPI.generatePDF({
        job_id: pdfJobId,
        candidate_ids: selectedPdfCandidates
      });

      // Create a blob from the response and trigger download
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      const selectedJobName = jobs.find(j => j.id === pdfJobId)?.title || 'Report';
      link.download = `Analysis_Report_${selectedJobName.replace(/\s+/g, '_')}_${new Date().toISOString().split('T')[0]}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      toast.success('PDF report generated successfully');
      setPdfDialogOpen(false);
      setSelectedPdfCandidates([]);
      setPdfJobId('');
      setPdfAvailableCandidates([]);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to generate PDF');
    } finally {
      setGeneratingPdf(false);
    }
  };

  // Open PDF dialog and reset state
  const openPdfDialog = () => {
    setPdfJobId('');
    setSelectedPdfCandidates([]);
    setPdfAvailableCandidates([]);
    setPdfDialogOpen(true);
  };

  const getCandidateName = (result) => {
    const candidate = candidatesMap[result.candidate_id];
    if (candidate) return candidate.name;
    if (result.candidate_name) return `[Deleted] ${result.candidate_name}`;
    return '[Deleted] Unknown';
  };

  const isCandidateDeleted = (result) => !candidatesMap[result.candidate_id];

  const getCategoryIcon = (category) => {
    switch (category) {
      case 'character': return Users;
      case 'requirement': return Target;
      case 'skill': return Wrench;
      default: return BarChart3;
    }
  };

  const getScoreColor = (score) => {
    if (score >= 80) return 'text-green-600';
    if (score >= 60) return 'text-yellow-600';
    if (score >= 40) return 'text-orange-600';
    return 'text-red-600';
  };

  const getLayerColor = (layer) => {
    switch (layer) {
      case 1: return 'bg-blue-100 text-blue-700';
      case 2: return 'bg-purple-100 text-purple-700';
      case 3: return 'bg-green-100 text-green-700';
      case 4: return 'bg-orange-100 text-orange-700';
      default: return 'bg-slate-100 text-slate-700';
    }
  };

  // Filter Layer 1 tags by search
  const filteredLayer1Tags = (tagLibrary?.layers?.[1]?.tags || []).filter(tag =>
    tag.toLowerCase().includes(layer1Search.toLowerCase())
  );

  // Filter Layer 2 tags by search
  const getFilteredLayer2Categories = () => {
    const search = layer2Search.toLowerCase();
    const filtered = {};
    Object.entries(LAYER_2_CATEGORIES).forEach(([category, tags]) => {
      const matchingTags = tags.filter(tag =>
        tag.toLowerCase().includes(search) ||
        tag.replace(/_/g, ' ').toLowerCase().includes(search)
      );
      if (matchingTags.length > 0) {
        filtered[category] = matchingTags;
      }
    });
    return filtered;
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-pulse text-indigo-500">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100" data-testid="analysis-page">
      <TopBar />

      <div className="p-6">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-heading font-bold text-slate-900">Job Fit Analysis</h1>
          <p className="text-slate-600">AI-powered candidate evaluation with tag-based filtering</p>
        </div>

        {/* TOP SECTION: Job Selection + Candidate Selection */}
        <div className="grid grid-cols-12 gap-6 mb-6">
          {/* Left: Job Selection */}
          <div className="col-span-4">
            <Card className="h-full border-slate-200 shadow-sm">
              <CardHeader className="pb-3">
                <CardTitle className="font-heading text-lg flex items-center gap-2">
                  <Briefcase className="w-5 h-5 text-indigo-500" />
                  Select Job
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <Select value={selectedJob} onValueChange={setSelectedJob}>
                  <SelectTrigger data-testid="select-job" className="w-full">
                    <SelectValue placeholder="Choose a job position" />
                  </SelectTrigger>
                  <SelectContent>
                    {jobs.map(job => (
                      <SelectItem key={job.id} value={job.id}>
                        <div className="flex items-center gap-2">
                          <span>{job.title}</span>
                          {!job.playbook && (
                            <span className="text-xs text-amber-600">(no playbook)</span>
                          )}
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                {selectedJobData && (
                  <div className="space-y-3 pt-3 border-t border-slate-100">
                    <div>
                      <p className="text-xs text-slate-600 uppercase tracking-wide">Department</p>
                      <p className="text-sm font-medium">{selectedJobData.department || '-'}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-600 uppercase tracking-wide">Location</p>
                      <p className="text-sm font-medium">{selectedJobData.location || '-'}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-600 uppercase tracking-wide">Playbook</p>
                      <p className="text-sm font-medium">
                        {selectedJobData.playbook ? (
                          <span className="text-green-600 flex items-center gap-1">
                            <CheckCircle className="w-4 h-4" /> Ready
                          </span>
                        ) : (
                          <span className="text-amber-600 flex items-center gap-1">
                            <AlertCircle className="w-4 h-4" /> Not generated
                          </span>
                        )}
                      </p>
                    </div>
                  </div>
                )}

                {!selectedJob && (
                  <div className="text-center py-6 text-slate-500">
                    <Briefcase className="w-10 h-10 mx-auto mb-2 opacity-50" />
                    <p className="text-sm">Select a job to start analysis</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Right: Candidate Selection with Filters */}
          <div className="col-span-8">
            <Card className="h-full border-slate-200 shadow-sm">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="font-heading text-lg flex items-center gap-2">
                    <Users className="w-5 h-5 text-indigo-500" />
                    Filter & Select Candidates
                  </CardTitle>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-slate-600">
                      {selectedCandidates.length} selected / {filteredCandidates.length} shown / {allCandidates.length} total
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setShowFilters(!showFilters)}
                      className="text-slate-600"
                    >
                      <Filter className="w-4 h-4 mr-1" />
                      {showFilters ? 'Hide' : 'Show'} Filters
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Tag Filters */}
                {showFilters && (
                  <div className="p-4 bg-slate-50 rounded-xl space-y-4 border border-slate-100">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-slate-700 flex items-center gap-2">
                        <Tag className="w-4 h-4" />
                        Tag Filters (AND logic)
                      </span>
                      {hasActiveFilters && (
                        <Button variant="ghost" size="sm" onClick={clearFilters} className="text-slate-600 h-7">
                          <X className="w-3 h-3 mr-1" /> Clear All
                        </Button>
                      )}
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      {/* Layer 1: Domain - Popover Picker */}
                      <div>
                        <Label className="text-xs text-blue-600 mb-2 block">Layer 1: Domain</Label>
                        <div className="space-y-2">
                          {/* Selected chips */}
                          {filterLayer1.length > 0 && (
                            <div className="flex flex-wrap gap-1">
                              {filterLayer1.map(tag => (
                                <span
                                  key={tag}
                                  className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-blue-500 text-white"
                                >
                                  {tag.replace(/_/g, ' ')}
                                  <button onClick={() => toggleLayer1Tag(tag)} className="hover:bg-blue-600 rounded-full">
                                    <X className="w-3 h-3" />
                                  </button>
                                </span>
                              ))}
                            </div>
                          )}
                          {/* Add Filter Popover */}
                          <Popover open={layer1PopoverOpen} onOpenChange={setLayer1PopoverOpen}>
                            <PopoverTrigger asChild>
                              <Button variant="outline" size="sm" className="w-full justify-start text-slate-600">
                                <Plus className="w-3 h-3 mr-2" />
                                Add Domain Filter
                              </Button>
                            </PopoverTrigger>
                            <PopoverContent className="w-72 p-3" align="start">
                              <div className="space-y-3">
                                <Input
                                  placeholder="Search domains..."
                                  value={layer1Search}
                                  onChange={(e) => setLayer1Search(e.target.value)}
                                  className="h-8"
                                />
                                <ScrollArea className="h-48">
                                  <div className="space-y-1">
                                    {filteredLayer1Tags.map(tag => (
                                      <label
                                        key={tag}
                                        className="flex items-center gap-2 p-2 rounded hover:bg-slate-50 cursor-pointer"
                                      >
                                        <Checkbox
                                          checked={filterLayer1.includes(tag)}
                                          onCheckedChange={() => toggleLayer1Tag(tag)}
                                        />
                                        <span className="text-sm">{tag.replace(/_/g, ' ')}</span>
                                      </label>
                                    ))}
                                    {filteredLayer1Tags.length === 0 && (
                                      <p className="text-sm text-slate-500 text-center py-4">No matching domains</p>
                                    )}
                                  </div>
                                </ScrollArea>
                              </div>
                            </PopoverContent>
                          </Popover>
                        </div>
                      </div>

                      {/* Layer 2: Job Family - Categorized Popover */}
                      <div>
                        <Label className="text-xs text-purple-600 mb-2 block">Layer 2: Job Family</Label>
                        <div className="space-y-2">
                          {/* Selected chips */}
                          {filterLayer2.length > 0 && (
                            <div className="flex flex-wrap gap-1">
                              {filterLayer2.map(tag => (
                                <span
                                  key={tag}
                                  className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-purple-500 text-white"
                                >
                                  {tag.replace(/_/g, ' ')}
                                  <button onClick={() => toggleLayer2Tag(tag)} className="hover:bg-purple-600 rounded-full">
                                    <X className="w-3 h-3" />
                                  </button>
                                </span>
                              ))}
                            </div>
                          )}
                          {/* Add Filter Popover */}
                          <Popover open={layer2PopoverOpen} onOpenChange={setLayer2PopoverOpen}>
                            <PopoverTrigger asChild>
                              <Button variant="outline" size="sm" className="w-full justify-start text-slate-600">
                                <Plus className="w-3 h-3 mr-2" />
                                Add Job Family Filter
                              </Button>
                            </PopoverTrigger>
                            <PopoverContent className="w-80 p-3" align="start">
                              <div className="space-y-3">
                                <Input
                                  placeholder="Search job families..."
                                  value={layer2Search}
                                  onChange={(e) => setLayer2Search(e.target.value)}
                                  className="h-8"
                                />
                                <ScrollArea className="h-64">
                                  <div className="space-y-4">
                                    {Object.entries(getFilteredLayer2Categories()).map(([category, tags]) => (
                                      <div key={category}>
                                        <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">
                                          {category}
                                        </p>
                                        <div className="space-y-1">
                                          {tags.map(tag => (
                                            <label
                                              key={tag}
                                              className="flex items-center gap-2 p-2 rounded hover:bg-slate-50 cursor-pointer"
                                            >
                                              <Checkbox
                                                checked={filterLayer2.includes(tag)}
                                                onCheckedChange={() => toggleLayer2Tag(tag)}
                                              />
                                              <span className="text-sm">{tag.replace(/_/g, ' ')}</span>
                                            </label>
                                          ))}
                                        </div>
                                      </div>
                                    ))}
                                    {Object.keys(getFilteredLayer2Categories()).length === 0 && (
                                      <p className="text-sm text-slate-500 text-center py-4">No matching job families</p>
                                    )}
                                  </div>
                                </ScrollArea>
                              </div>
                            </PopoverContent>
                          </Popover>
                        </div>
                      </div>

                      {/* Layer 3: Skills (text search) */}
                      <div>
                        <Label className="text-xs text-green-600 mb-2 block">Layer 3: Skills</Label>
                        <Input
                          value={filterLayer3}
                          onChange={(e) => setFilterLayer3(e.target.value)}
                          placeholder="Search skills..."
                          className="h-9"
                        />
                      </div>

                      {/* Layer 4: Scope (buttons - only 3) */}
                      <div>
                        <Label className="text-xs text-orange-600 mb-2 block">Layer 4: Scope</Label>
                        <div className="flex flex-wrap gap-1">
                          {['OPERATIONAL', 'TACTICAL', 'STRATEGIC'].map(tag => (
                            <button
                              key={tag}
                              onClick={() => toggleLayer4Tag(tag)}
                              className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${filterLayer4.includes(tag)
                                ? 'bg-orange-500 text-white border-orange-500'
                                : 'bg-white text-orange-700 border-orange-200 hover:border-orange-400'
                                }`}
                            >
                              {tag}
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Search and Select All */}
                <div className="flex items-center gap-3">
                  <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                    <Input
                      value={candidateSearch}
                      onChange={(e) => setCandidateSearch(e.target.value)}
                      placeholder="Search by name or email..."
                      className="pl-9"
                      data-testid="candidate-search"
                    />
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={selectAllFiltered}
                    className="whitespace-nowrap"
                  >
                    {filteredCandidates.length > 0 && filteredCandidates.every(c => selectedCandidates.includes(c.id))
                      ? 'Deselect All'
                      : `Select All (${filteredCandidates.length})`}
                  </Button>
                </div>

                {/* Candidate List */}
                <ScrollArea className="h-[220px] border border-slate-100 rounded-lg">
                  {filteredCandidates.length === 0 ? (
                    <div className="text-center py-8 text-slate-500">
                      <Users className="w-10 h-10 mx-auto mb-2 opacity-50" />
                      <p className="text-sm">No candidates match the filters</p>
                    </div>
                  ) : (
                    <div className="divide-y divide-slate-50">
                      {filteredCandidates.map(candidate => (
                        <label
                          key={candidate.id}
                          className={`flex items-center gap-3 p-3 cursor-pointer transition-colors ${selectedCandidates.includes(candidate.id)
                            ? 'bg-indigo-50'
                            : 'hover:bg-slate-50'
                            }`}
                        >
                          <Checkbox
                            checked={selectedCandidates.includes(candidate.id)}
                            onCheckedChange={() => toggleCandidate(candidate.id)}
                          />
                          <div className="flex-1 min-w-0">
                            <p className="font-medium text-sm text-slate-900">{candidate.name}</p>
                            <p className="text-xs text-slate-600">{candidate.email}</p>
                          </div>
                          {/* Show candidate tags */}
                          <div className="flex flex-wrap gap-1 max-w-xs">
                            {(candidate.tags || []).slice(0, 4).map((tag, idx) => (
                              <span
                                key={idx}
                                className={`text-xs px-1.5 py-0.5 rounded ${getLayerColor(tag.layer)}`}
                                title={`${tag.layer_name}: ${tag.tag_value}`}
                              >
                                {tag.layer === 3 ? tag.tag_value : tag.tag_value.replace(/_/g, ' ').substring(0, 10)}
                              </span>
                            ))}
                            {(candidate.tags?.length || 0) > 4 && (
                              <span className="text-xs text-slate-500">+{candidate.tags.length - 4}</span>
                            )}
                          </div>
                          <span className="text-xs text-slate-500 flex items-center gap-1">
                            <FileText className="w-3 h-3" />
                            {candidate.evidence?.length || 0}
                          </span>
                        </label>
                      ))}
                    </div>
                  )}
                </ScrollArea>

                {/* Run Analysis Button */}
                <div className="flex items-center justify-between pt-2 border-t border-slate-100">
                  <div className="text-sm text-slate-600">
                    {selectedCandidates.length > 0 && selectedJob ? (
                      <span className="text-indigo-600 font-medium">
                        Ready to analyze {selectedCandidates.length} candidate(s)
                      </span>
                    ) : (
                      <span>Select a job and candidates to run analysis</span>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      onClick={() => setPdfDialogOpen(true)}
                      className="text-indigo-600 border-indigo-200 hover:bg-indigo-50"
                    >
                      <FileText className="w-4 h-4 mr-2" />
                      Download Report
                    </Button>
                    <Button
                      onClick={runAnalysis}
                      disabled={!selectedJob || selectedCandidates.length === 0 || analyzing}
                      className="bg-indigo-500 hover:bg-indigo-600 text-white rounded-full px-6"
                    >
                      {analyzing ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Analyzing...
                        </>
                      ) : (
                        <>
                          <Play className="w-4 h-4 mr-2" />
                          Run Analysis
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Analysis Progress */}
        {analyzing && (
          <Card className="mb-6 border-indigo-200 bg-indigo-50">
            <CardContent className="pt-6">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-indigo-700">
                    Analyzing {analysisProgress.candidateName || '...'}
                  </span>
                  <span className="text-sm text-indigo-600">
                    {analysisProgress.current} / {analysisProgress.total}
                  </span>
                </div>
                <Progress
                  value={(analysisProgress.current / analysisProgress.total) * 100}
                  className="h-2"
                />
                {analysisProgress.message && (
                  <p className="text-xs text-indigo-600">{analysisProgress.message}</p>
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {/* BOTTOM SECTION: Analysis Results */}
        <Card className="border-slate-200 shadow-sm">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="font-heading text-lg flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-indigo-500" />
                Analysis Results
                {selectedJob && results.length > 0 && (
                  <span className="text-sm font-normal text-slate-600">
                    ({results.length} results)
                  </span>
                )}
              </CardTitle>
              <div className="flex items-center gap-3">
                {/* Standalone Download Report Button */}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={openPdfDialog}
                  className="text-indigo-600 border-indigo-200 hover:bg-indigo-50"
                  data-testid="download-report-btn"
                >
                  <FileText className="w-4 h-4 mr-1" />
                  Download Report
                </Button>
                {results.length > 0 && (
                  <>
                    <div className="flex items-center gap-2">
                      <Label className="text-sm text-slate-600">Min Score:</Label>
                      <Input
                        type="number"
                        value={minScore}
                        onChange={(e) => setMinScore(Number(e.target.value))}
                        className="w-20 h-8"
                        min={0}
                        max={100}
                      />
                    </div>
                    {selectedResults.length > 0 && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleBulkDeleteResults}
                        disabled={deleting}
                        className="text-red-600 border-red-200 hover:bg-red-50"
                      >
                        {deleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4 mr-1" />}
                        Delete ({selectedResults.length})
                      </Button>
                    )}
                  </>
                )}
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {!selectedJob ? (
              <div className="text-center py-12 text-slate-500">
                <BarChart3 className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>Select a job to view analysis results</p>
              </div>
            ) : results.length === 0 ? (
              <div className="text-center py-12 text-slate-500">
                <Target className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>No analysis results yet</p>
                <p className="text-sm">Select candidates and run analysis</p>
              </div>
            ) : (
              <div className="space-y-2">
                {/* Results Header */}
                <div className="flex items-center gap-2 pb-2 border-b border-slate-100">
                  <Checkbox
                    checked={selectedResults.length === results.length && results.length > 0}
                    onCheckedChange={selectAllResults}
                  />
                  <div className="grid grid-cols-[3fr_2fr_2fr_2fr_2fr_1fr_1fr] gap-4 flex-1 text-xs font-medium text-slate-600 uppercase tracking-wide">
                    <div>Candidate</div>
                    <div className="text-center">Score</div>
                    <div className="text-center">Character</div>
                    <div className="text-center">Requirements</div>
                    <div className="text-center">Skills</div>
                    <div className="text-center">Culture</div>
                    <div className="text-center">Actions</div>
                  </div>
                </div>

                {/* Results List */}
                <ScrollArea className="h-[400px]">
                  <div className="space-y-1">
                    {results.map(result => (
                      <div
                        key={result.id}
                        className={`flex items-center gap-2 p-3 rounded-lg transition-colors ${selectedResults.includes(result.id) ? 'bg-indigo-50' : 'hover:bg-slate-50'
                          }`}
                      >
                        <Checkbox
                          checked={selectedResults.includes(result.id)}
                          onCheckedChange={() => toggleResultSelection(result.id)}
                        />
                        <div className="grid grid-cols-[3fr_2fr_2fr_2fr_2fr_1fr_1fr] gap-4 flex-1 items-center">
                          {/* Candidate Name */}
                          <div className="flex items-center gap-2">
                            {isCandidateDeleted(result) && (
                              <UserX className="w-4 h-4 text-red-400" />
                            )}
                            <div>
                              <p className={`font-medium text-sm ${isCandidateDeleted(result) ? 'text-slate-500' : 'text-slate-900'}`}>
                                {getCandidateName(result)}
                              </p>
                              <p className="text-xs text-slate-500">
                                {new Date(result.created_at).toLocaleDateString()}
                              </p>
                            </div>
                          </div>

                          {/* Final Score */}
                          <div className="text-center">
                            <span className={`text-lg font-bold ${getScoreColor(result.final_score)}`}>
                              {Math.round(result.final_score)}%
                            </span>
                          </div>

                          {/* Category Scores */}
                          {['character', 'requirement', 'skill'].map(category => {
                            const catResult = result.category_scores?.find(c => c.category === category);
                            const score = catResult?.score || 0;
                            return (
                              <div key={category} className="text-center">
                                <span className={`text-sm font-medium ${getScoreColor(score)}`}>
                                  {Math.round(score)}%
                                </span>
                              </div>
                            );
                          })}

                          {/* Company Culture Score */}
                          <div className="text-center">
                            <span className={`text-sm font-medium ${getScoreColor(result.company_values_alignment?.score || 0)}`}>
                              {Math.round(result.company_values_alignment?.score || 0)}%
                            </span>
                          </div>

                          {/* Actions */}
                          <div className="text-center">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setDetailModalResult(result)}
                              className="h-8 w-8 p-0"
                            >
                              <Eye className="w-4 h-4" />
                            </Button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Detail Modal */}
      <Dialog open={!!detailModalResult} onOpenChange={() => setDetailModalResult(null)}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-heading">
              Analysis Details: {detailModalResult && getCandidateName(detailModalResult)}
            </DialogTitle>
            <DialogDescription>
              Detailed breakdown of the job fit analysis
            </DialogDescription>
          </DialogHeader>

          {detailModalResult && (
            <div className="space-y-6 pt-4">
              {/* Overall Score */}
              <div className="text-center p-6 bg-slate-50 rounded-xl">
                <p className="text-sm text-slate-600 mb-2">Overall Job Fit Score</p>
                <p className={`text-5xl font-bold ${getScoreColor(detailModalResult.final_score)}`}>
                  {Math.round(detailModalResult.final_score)}%
                </p>
              </div>

              {/* AI Summary - MOVED TO TOP */}
              {detailModalResult.overall_reasoning && (
                <div className="p-4 bg-indigo-50 rounded-xl border-2 border-indigo-200">
                  <p className="text-sm font-medium text-indigo-700 mb-2">📋 AI Summary</p>
                  <p className="text-sm text-slate-700">{detailModalResult.overall_reasoning}</p>
                </div>
              )}

              {/* Strengths & Gaps - MOVED TO TOP */}
              <div className="grid grid-cols-2 gap-4">
                {detailModalResult.strengths && detailModalResult.strengths.length > 0 && (
                  <div className="p-4 bg-green-50 rounded-xl border-2 border-green-200">
                    <p className="text-sm font-medium text-green-700 mb-2">✅ Key Strengths</p>
                    <ul className="space-y-1">
                      {detailModalResult.strengths.map((s, idx) => (
                        <li key={idx} className="text-sm text-slate-700 flex items-start gap-2">
                          <CheckCircle className="w-4 h-4 text-green-500 mt-0.5 shrink-0" />
                          {s}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {detailModalResult.gaps && detailModalResult.gaps.length > 0 && (
                  <div className="p-4 bg-red-50 rounded-xl border-2 border-red-200">
                    <p className="text-sm font-medium text-red-700 mb-2">⚠️ Development Areas</p>
                    <ul className="space-y-1">
                      {detailModalResult.gaps.map((g, idx) => (
                        <li key={idx} className="text-sm text-slate-700 flex items-start gap-2">
                          <AlertCircle className="w-4 h-4 text-red-500 mt-0.5 shrink-0" />
                          {g}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              {/* Company Culture Alignment */}
              {detailModalResult.company_values_alignment && (
                <div className="p-4 bg-purple-50 rounded-xl border-2 border-purple-200">
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-sm font-medium text-purple-700">🏢 Company Culture Fit</p>
                    <span className={`text-lg font-bold ${getScoreColor(detailModalResult.company_values_alignment.score || 0)}`}>
                      {Math.round(detailModalResult.company_values_alignment.score || 0)}%
                    </span>
                  </div>
                  {detailModalResult.company_values_alignment.notes && (
                    <p className="text-sm text-slate-700 mb-3">{detailModalResult.company_values_alignment.notes}</p>
                  )}
                  {detailModalResult.company_values_alignment.breakdown && detailModalResult.company_values_alignment.breakdown.length > 0 && (
                    <div className="space-y-2 mt-2">
                      {detailModalResult.company_values_alignment.breakdown.map((item, idx) => (
                        <div key={idx} className="flex items-start gap-3 p-2 bg-white rounded">
                          <div className="flex-1">
                            <div className="flex items-center justify-between mb-1">
                              <p className="text-sm font-medium">{item.value_name}</p>
                              <span className={`text-sm font-bold ${getScoreColor(item.score)}`}>
                                {Math.round(item.score)}%
                              </span>
                            </div>
                            <p className="text-xs text-slate-600">{item.reasoning}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Category Breakdown - NOW AT BOTTOM */}
              <div className="border-t-2 border-slate-200 pt-4">
                <p className="text-sm font-medium text-slate-600 mb-3">📊 Detailed Category Breakdown</p>
                <div className="space-y-4">
                  {detailModalResult.category_scores?.map((catResult) => {
                    const Icon = getCategoryIcon(catResult.category);
                    return (
                      <div key={catResult.category} className="border border-slate-200 rounded-xl p-4">
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center gap-2">
                            <Icon className="w-5 h-5 text-indigo-500" />
                            <span className="font-medium capitalize">{catResult.category}</span>
                          </div>
                          <span className={`text-lg font-bold ${getScoreColor(catResult.score)}`}>
                            {Math.round(catResult.score)}%
                          </span>
                        </div>

                        {/* Breakdown Items */}
                        {catResult.breakdown && catResult.breakdown.length > 0 && (
                          <div className="space-y-2">
                            {catResult.breakdown.map((item, idx) => (
                              <div key={idx} className="flex items-start gap-3 p-3 bg-slate-50 rounded-lg">
                                <div className="flex-1">
                                  <div className="flex items-center justify-between mb-1">
                                    <p className="text-sm font-medium">{item.item_name}</p>
                                    <span className="text-xs text-slate-500">
                                      weight: {item.weight}
                                    </span>
                                  </div>
                                  <p className="text-xs text-slate-600">{item.reasoning}</p>
                                </div>
                                <span className={`text-sm font-bold ${getScoreColor(item.raw_score)}`}>
                                  {Math.round(item.raw_score)}%
                                </span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* PDF Generation Dialog - Two-step: Job Selection → Candidate Selection */}
      <Dialog open={pdfDialogOpen} onOpenChange={setPdfDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Generate PDF Report</DialogTitle>
            <DialogDescription>
              Select a job and choose candidates to include in the PDF report
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {/* Step 1: Job Selection */}
            <div className="space-y-2">
              <Label className="text-sm font-medium">Select Job</Label>
              <Select value={pdfJobId} onValueChange={handlePdfJobChange}>
                <SelectTrigger data-testid="pdf-job-select" className="w-full">
                  <SelectValue placeholder="Choose a job position" />
                </SelectTrigger>
                <SelectContent>
                  {jobs.map(job => (
                    <SelectItem key={job.id} value={job.id}>
                      {job.title}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Step 2: Candidate Selection (shown after job is selected) */}
            {pdfJobId && (
              <div className="space-y-3 pt-3 border-t border-slate-100">
                <div className="flex items-center justify-between">
                  <Label className="text-sm font-medium">Select Candidates</Label>
                  {pdfAvailableCandidates.length > 0 && (
                    <span className="text-xs text-slate-600">
                      {pdfAvailableCandidates.length} candidate(s) with analysis
                    </span>
                  )}
                </div>

                {loadingPdfCandidates ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="w-6 h-6 animate-spin text-indigo-500" />
                    <span className="ml-2 text-sm text-slate-600">Loading candidates...</span>
                  </div>
                ) : pdfAvailableCandidates.length === 0 ? (
                  <div className="text-center py-8 text-slate-500">
                    <Users className="w-10 h-10 mx-auto mb-2 opacity-50" />
                    <p className="text-sm">No analysis results found for this job</p>
                    <p className="text-xs mt-1">Run analysis on candidates first</p>
                  </div>
                ) : (
                  <>
                    {/* Select All */}
                    <div className="flex items-center gap-3 p-3 bg-slate-50 rounded-lg">
                      <Checkbox
                        checked={selectedPdfCandidates.length === pdfAvailableCandidates.length && selectedPdfCandidates.length > 0}
                        onCheckedChange={(checked) => {
                          if (checked) {
                            setSelectedPdfCandidates(pdfAvailableCandidates.map(c => c.candidate_id));
                          } else {
                            setSelectedPdfCandidates([]);
                          }
                        }}
                        data-testid="pdf-select-all"
                      />
                      <span className="font-medium text-sm">
                        Select All ({pdfAvailableCandidates.length} candidates)
                      </span>
                    </div>

                    {/* Candidate List */}
                    <div className="space-y-2 max-h-64 overflow-y-auto">
                      {pdfAvailableCandidates.map((candidate) => (
                        <div
                          key={candidate.candidate_id}
                          className="flex items-center gap-3 p-3 border border-slate-200 rounded-lg hover:bg-slate-50"
                        >
                          <Checkbox
                            checked={selectedPdfCandidates.includes(candidate.candidate_id)}
                            onCheckedChange={(checked) => {
                              if (checked) {
                                setSelectedPdfCandidates(prev => [...prev, candidate.candidate_id]);
                              } else {
                                setSelectedPdfCandidates(prev => prev.filter(id => id !== candidate.candidate_id));
                              }
                            }}
                            data-testid={`pdf-candidate-${candidate.candidate_id}`}
                          />
                          <div className="flex-1">
                            <p className="font-medium text-sm">{candidate.candidate_name}</p>
                            <p className="text-xs text-slate-600">
                              Analyzed: {new Date(candidate.created_at).toLocaleDateString()}
                            </p>
                          </div>
                          <span className={`text-lg font-bold ${getScoreColor(candidate.final_score)}`}>
                            {Math.round(candidate.final_score)}%
                          </span>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex items-center justify-between pt-4 border-t">
              <p className="text-sm text-slate-600">
                {selectedPdfCandidates.length} candidate(s) selected
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    setPdfDialogOpen(false);
                    setSelectedPdfCandidates([]);
                    setPdfJobId('');
                    setPdfAvailableCandidates([]);
                  }}
                  disabled={generatingPdf}
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleGeneratePDF}
                  disabled={generatingPdf || selectedPdfCandidates.length === 0 || !pdfJobId}
                  className="bg-indigo-500 hover:bg-indigo-600"
                  data-testid="generate-pdf-btn"
                >
                  {generatingPdf ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Generating...
                    </>
                  ) : (
                    <>
                      <FileText className="w-4 h-4 mr-2" />
                      Generate PDF
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Company Culture Required Dialog */}
      <Dialog open={showCultureDialog} onOpenChange={setShowCultureDialog}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="font-heading flex items-center gap-2">
              <AlertCircle className="w-5 h-5 text-amber-500" />
              Company Culture Required
            </DialogTitle>
            <DialogDescription>
              You need to set up your company culture values before running candidate analysis. Culture values are used to evaluate candidate alignment with your organization.
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-3 pt-4">
            <Button
              variant="outline"
              onClick={() => setShowCultureDialog(false)}
            >
              Cancel
            </Button>
            <Button
              className="bg-indigo-500 hover:bg-indigo-600 text-white"
              onClick={() => {
                setShowCultureDialog(false);
                navigate('/company');
              }}
            >
              Set Up Culture
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Analysis;
