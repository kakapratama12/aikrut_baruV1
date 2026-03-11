import React, { useState, useEffect, useRef } from 'react';
import { TopBar } from '../components/layout/TopBar';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { ScrollArea } from '../components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Checkbox } from '../components/ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { candidatesAPI } from '../lib/api';
import { 
  Users, Upload, Search, Mail, Phone, FileText, Trash2, Plus, Loader2, 
  Edit, RefreshCw, ChevronLeft, ChevronRight, Eye, Save, User, AlertTriangle,
  UserPlus, UserCheck, FolderArchive, GitMerge, ArrowRight, X, CheckCircle2,
  Replace, Copy, Tag, Sparkles, Brain
} from 'lucide-react';
import { EmptyState } from '../components/common/EmptyState';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../components/ui/dialog';

export const Candidates = () => {
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [showUploadDialog, setShowUploadDialog] = useState(false);
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [detailCandidate, setDetailCandidate] = useState(null);
  const [editMode, setEditMode] = useState(false);
  const [editForm, setEditForm] = useState({ name: '', email: '', phone: '' });
  const [savingEdit, setSavingEdit] = useState(false);
  const [reparsing, setReparsing] = useState(false);
  
  // ZIP upload state
  const [uploadMode, setUploadMode] = useState('pdf');
  const [zipUploading, setZipUploading] = useState(false);
  const [zipDuplicates, setZipDuplicates] = useState(null);
  const [showZipDuplicateDialog, setShowZipDuplicateDialog] = useState(false);
  const [pendingZipFile, setPendingZipFile] = useState(null);
  const [selectedMergeTarget, setSelectedMergeTarget] = useState(null);
  const zipInputRef = useRef(null);
  
  // BULK DUPLICATE HANDLER STATE
  const [bulkDuplicates, setBulkDuplicates] = useState([]); // Array of {file, extractedInfo, duplicates, evidence_preview}
  const [bulkDecisions, setBulkDecisions] = useState({}); // {fileIndex: {action: 'merge'|'create'|'replace', targetId: string}}
  const [showBulkDuplicateDialog, setShowBulkDuplicateDialog] = useState(false);
  const [processingBulk, setProcessingBulk] = useState(false);
  const [selectedBulkIndex, setSelectedBulkIndex] = useState(0);
  
  // Evidence view state
  const [expandedEvidence, setExpandedEvidence] = useState(null); // Index of expanded evidence
  
  // Evidence delete state
  const [deletingEvidence, setDeletingEvidence] = useState(null);
  
  // TALENT TAGGING STATE
  const [tagLibrary, setTagLibrary] = useState(null);
  const [extractingTags, setExtractingTags] = useState(false);
  const [showAddTagDialog, setShowAddTagDialog] = useState(false);
  const [addTagLayer, setAddTagLayer] = useState(1);
  const [addTagValue, setAddTagValue] = useState('');
  const [deletingTag, setDeletingTag] = useState(null);
  
  // Pagination
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  
  const fileInputRef = useRef(null);

  useEffect(() => {
    loadCandidates();
    loadTagLibrary();
  }, [searchTerm, page]);

  const loadTagLibrary = async () => {
    try {
      const res = await candidatesAPI.getTagLibrary();
      setTagLibrary(res.data);
    } catch (error) {
      console.error('Failed to load tag library:', error);
    }
  };

  const loadCandidates = async () => {
    setLoading(true);
    try {
      if (searchTerm) {
        const res = await candidatesAPI.search(searchTerm, page, 20);
        setCandidates(res.data.candidates || []);
        setTotalPages(res.data.pages || 1);
        setTotal(res.data.total || 0);
      } else {
        const res = await candidatesAPI.list();
        const allCandidates = res.data || [];
        setCandidates(allCandidates.slice((page - 1) * 20, page * 20));
        setTotalPages(Math.ceil(allCandidates.length / 20) || 1);
        setTotal(allCandidates.length);
      }
    } catch (error) {
      toast.error('Failed to load candidates');
    } finally {
      setLoading(false);
    }
  };

  // ==================== BULK PDF UPLOAD WITH DUPLICATE DETECTION ====================
  
  const handleFileSelect = async (event) => {
    const files = Array.from(event.target.files || []);
    if (files.length === 0) return;

    const pdfFiles = files.filter(f => f.name.toLowerCase().endsWith('.pdf'));
    if (pdfFiles.length === 0) {
      toast.error('Only PDF files are supported');
      return;
    }

    // If adding to existing candidate, skip duplicate check
    if (selectedCandidate) {
      await uploadFilesToExisting(pdfFiles, selectedCandidate.id);
      return;
    }

    // Process all files and collect duplicates
    await processFilesWithDuplicateDetection(pdfFiles);
  };

  const processFilesWithDuplicateDetection = async (files) => {
    setUploading(true);
    const duplicatesFound = [];
    let successCount = 0;

    try {
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        try {
          const res = await candidatesAPI.uploadCV(file, null, false, null);
          
          if (res.data.status === 'duplicate_warning') {
            duplicatesFound.push({
              file,
              fileIndex: i,
              extractedInfo: res.data.extracted_info,
              duplicates: res.data.duplicates,
              evidence_preview: res.data.evidence_preview
            });
          } else if (res.data.status === 'created') {
            successCount++;
            const evidenceTypes = res.data.evidence_types || ['cv'];
            toast.success(`Uploaded ${file.name}: ${res.data.evidence_added} evidence(s) (${evidenceTypes.join(', ')})`);
          }
        } catch (error) {
          toast.error(`Failed to upload ${file.name}: ${error.response?.data?.detail || 'Error'}`);
        }
      }

      // If duplicates found, show bulk handler
      if (duplicatesFound.length > 0) {
        setBulkDuplicates(duplicatesFound);
        // Initialize decisions
        const decisions = {};
        duplicatesFound.forEach((d, idx) => {
          decisions[idx] = { action: null, targetId: null };
        });
        setBulkDecisions(decisions);
        setSelectedBulkIndex(0);
        setShowBulkDuplicateDialog(true);
      }

      if (successCount > 0) {
        loadCandidates();
      }
      
      // Only close upload dialog if no duplicates
      if (duplicatesFound.length === 0) {
        setShowUploadDialog(false);
      }
    } catch (error) {
      toast.error('Upload failed');
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const uploadFilesToExisting = async (files, candidateId) => {
    setUploading(true);
    try {
      for (const file of files) {
        const res = await candidatesAPI.uploadCV(file, candidateId);
        const evidenceTypes = res.data.evidence_types || ['cv'];
        toast.success(`Uploaded ${file.name}: ${res.data.evidence_added || 1} evidence(s) (${evidenceTypes.join(', ')})`);
      }
      loadCandidates();
      // Refresh detail candidate if open
      if (detailCandidate && detailCandidate.id === candidateId) {
        const updated = await candidatesAPI.get(candidateId);
        setDetailCandidate(updated.data);
      }
      setShowUploadDialog(false);
      setSelectedCandidate(null);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  // ==================== BULK DUPLICATE ACTIONS ====================

  const handleBulkDecision = (index, action, targetId = null) => {
    setBulkDecisions(prev => ({
      ...prev,
      [index]: { action, targetId }
    }));
  };

  const handleBatchAction = (action) => {
    const newDecisions = { ...bulkDecisions };
    bulkDuplicates.forEach((dup, idx) => {
      if (action === 'merge' && dup.duplicates.length > 0) {
        // Default to first duplicate for merge
        newDecisions[idx] = { action: 'merge', targetId: dup.duplicates[0].candidate_id };
      } else if (action === 'create') {
        newDecisions[idx] = { action: 'create', targetId: null };
      } else if (action === 'replace' && dup.duplicates.length > 0) {
        newDecisions[idx] = { action: 'replace', targetId: dup.duplicates[0].candidate_id };
      }
    });
    setBulkDecisions(newDecisions);
  };

  const processBulkDecisions = async () => {
    setProcessingBulk(true);
    let successCount = 0;

    try {
      for (let i = 0; i < bulkDuplicates.length; i++) {
        const dup = bulkDuplicates[i];
        const decision = bulkDecisions[i];
        
        if (!decision || !decision.action) continue;

        try {
          if (decision.action === 'create') {
            // Force create
            await candidatesAPI.uploadCV(dup.file, null, true, null);
            successCount++;
          } else if (decision.action === 'merge' && decision.targetId) {
            // Merge into existing
            await candidatesAPI.uploadCV(dup.file, null, false, decision.targetId);
            successCount++;
          } else if (decision.action === 'replace' && decision.targetId) {
            // Replace: First force create, then we need the evidence
            const createRes = await candidatesAPI.uploadCV(dup.file, null, true, null);
            if (createRes.data.status === 'created') {
              // Now merge the new into old, then delete new
              // Actually, replace means delete old, create new - so we need to delete the old
              await candidatesAPI.delete(decision.targetId);
              successCount++;
            }
          }
        } catch (error) {
          toast.error(`Failed to process ${dup.file.name}: ${error.response?.data?.detail || 'Error'}`);
        }
      }

      if (successCount > 0) {
        toast.success(`Successfully processed ${successCount} candidate(s)`);
      }

      setShowBulkDuplicateDialog(false);
      setBulkDuplicates([]);
      setBulkDecisions({});
      setShowUploadDialog(false);
      loadCandidates();
    } catch (error) {
      toast.error('Failed to process duplicates');
    } finally {
      setProcessingBulk(false);
    }
  };

  const allDecisionsMade = () => {
    return bulkDuplicates.every((_, idx) => bulkDecisions[idx]?.action);
  };

  // ==================== ZIP UPLOAD ====================

  const handleZipSelect = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    
    if (!file.name.toLowerCase().endsWith('.zip')) {
      toast.error('Please select a ZIP file');
      return;
    }
    
    setZipUploading(true);
    setPendingZipFile(file);
    
    try {
      const res = await candidatesAPI.uploadZip(file, false);
      
      if (res.data.status === 'duplicate_warning') {
        setZipDuplicates(res.data);
        setShowZipDuplicateDialog(true);
      } else if (res.data.status === 'created') {
        toast.success(res.data.message);
        loadCandidates();
        setShowUploadDialog(false);
      } else {
        toast.error(res.data.message || 'Upload failed');
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'ZIP upload failed');
    } finally {
      setZipUploading(false);
      if (zipInputRef.current) {
        zipInputRef.current.value = '';
      }
    }
  };

  const handleZipForceCreate = async () => {
    if (!pendingZipFile) return;
    
    setZipUploading(true);
    try {
      const res = await candidatesAPI.uploadZip(pendingZipFile, true);
      toast.success(res.data.message || 'Candidate created');
      setShowZipDuplicateDialog(false);
      setZipDuplicates(null);
      setPendingZipFile(null);
      setSelectedMergeTarget(null);
      loadCandidates();
      setShowUploadDialog(false);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Upload failed');
    } finally {
      setZipUploading(false);
    }
  };

  const handleZipMerge = async (targetCandidateId) => {
    if (!pendingZipFile) return;
    
    setZipUploading(true);
    try {
      const createRes = await candidatesAPI.uploadZip(pendingZipFile, true);
      
      if (createRes.data.status === 'created' && createRes.data.candidate) {
        const mergeRes = await candidatesAPI.merge(createRes.data.candidate.id, targetCandidateId);
        toast.success(`Merged into existing candidate. ${mergeRes.data.evidence_transferred} evidence file(s) transferred.`);
      }
      
      setShowZipDuplicateDialog(false);
      setZipDuplicates(null);
      setPendingZipFile(null);
      setSelectedMergeTarget(null);
      loadCandidates();
      setShowUploadDialog(false);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Merge failed');
    } finally {
      setZipUploading(false);
    }
  };

  // ==================== EVIDENCE CRUD ====================

  const handleDeleteEvidence = async (candidateId, evidenceIndex, evidenceType) => {
    if (!confirm(`Are you sure you want to delete this ${evidenceType} evidence?`)) return;
    
    setDeletingEvidence(evidenceIndex);
    try {
      const res = await candidatesAPI.deleteEvidence(candidateId, evidenceIndex);
      toast.success(`Deleted ${res.data.deleted_evidence.type} evidence`);
      
      // Refresh detail candidate
      if (detailCandidate && detailCandidate.id === candidateId) {
        setDetailCandidate(res.data.candidate);
      }
      loadCandidates();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to delete evidence');
    } finally {
      setDeletingEvidence(null);
    }
  };

  // ==================== TALENT TAGGING HANDLERS ====================

  const handleExtractTags = async () => {
    if (!detailCandidate) return;
    
    setExtractingTags(true);
    try {
      const res = await candidatesAPI.extractTags(detailCandidate.id);
      toast.success(`Extracted ${res.data.tags?.length || 0} tags`);
      setDetailCandidate(res.data.candidate);
      loadCandidates();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to extract tags');
    } finally {
      setExtractingTags(false);
    }
  };

  const handleAddTag = async () => {
    if (!detailCandidate || !addTagValue) return;
    
    try {
      const res = await candidatesAPI.addTag(detailCandidate.id, addTagValue, addTagLayer);
      toast.success(`Added tag: ${res.data.tag.tag_value}`);
      
      // Refresh candidate
      const updated = await candidatesAPI.get(detailCandidate.id);
      setDetailCandidate(updated.data);
      
      setShowAddTagDialog(false);
      setAddTagValue('');
      loadCandidates();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to add tag');
    }
  };

  const handleDeleteTag = async (tagValue, layer) => {
    if (!detailCandidate) return;
    
    setDeletingTag(tagValue);
    try {
      const res = await candidatesAPI.deleteTag(detailCandidate.id, tagValue, layer);
      toast.success(`Deleted tag: ${tagValue}${res.data.blacklisted ? ' (blacklisted)' : ''}`);
      
      // Refresh candidate
      const updated = await candidatesAPI.get(detailCandidate.id);
      setDetailCandidate(updated.data);
      loadCandidates();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to delete tag');
    } finally {
      setDeletingTag(null);
    }
  };

  const getLayerColor = (layer) => {
    switch (layer) {
      case 1: return 'bg-blue-100 text-blue-700 border-blue-200';
      case 2: return 'bg-purple-100 text-purple-700 border-purple-200';
      case 3: return 'bg-green-100 text-green-700 border-green-200';
      case 4: return 'bg-orange-100 text-orange-700 border-orange-200';
      default: return 'bg-slate-100 text-slate-700 border-slate-200';
    }
  };

  const getLayerName = (layer) => {
    switch (layer) {
      case 1: return 'Domain';
      case 2: return 'Job Family';
      case 3: return 'Skill';
      case 4: return 'Scope';
      default: return 'Unknown';
    }
  };

  const groupTagsByLayer = (tags) => {
    const grouped = { 1: [], 2: [], 3: [], 4: [] };
    (tags || []).forEach(tag => {
      if (grouped[tag.layer]) {
        grouped[tag.layer].push(tag);
      }
    });
    return grouped;
  };

  // ==================== OTHER HANDLERS ====================

  const handleDelete = async (id) => {
    if (!confirm('Are you sure you want to delete this candidate?')) return;
    
    try {
      await candidatesAPI.delete(id);
      toast.success('Candidate deleted');
      if (detailCandidate?.id === id) {
        setDetailCandidate(null);
      }
      loadCandidates();
    } catch (error) {
      toast.error('Failed to delete candidate');
    }
  };

  const handleReparse = async (id) => {
    setReparsing(true);
    try {
      const res = await candidatesAPI.reparse(id);
      toast.success('CV re-parsed successfully');
      setDetailCandidate(res.data);
      loadCandidates();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to re-parse CV');
    } finally {
      setReparsing(false);
    }
  };

  const handleEdit = () => {
    setEditMode(true);
    setEditForm({
      name: detailCandidate?.name || '',
      email: detailCandidate?.email || '',
      phone: detailCandidate?.phone || ''
    });
  };

  const handleSaveEdit = async () => {
    setSavingEdit(true);
    try {
      await candidatesAPI.update(detailCandidate.id, editForm);
      toast.success('Candidate updated');
      setDetailCandidate({ ...detailCandidate, ...editForm });
      setEditMode(false);
      loadCandidates();
    } catch (error) {
      toast.error('Failed to update candidate');
    } finally {
      setSavingEdit(false);
    }
  };

  const getEvidenceIcon = (type) => {
    switch (type) {
      case 'cv': return '📄';
      case 'certificate': return '🏆';
      case 'diploma': return '🎓';
      case 'reference': return '📝';
      case 'transcript': return '📊';
      case 'psychotest': return '🧠';
      case 'knowledge_test': return '📚';
      default: return '📎';
    }
  };

  const getEvidenceColor = (type) => {
    switch (type) {
      case 'cv': return 'bg-blue-100 text-blue-700 border-blue-200';
      case 'certificate': return 'bg-amber-100 text-amber-700 border-amber-200';
      case 'diploma': return 'bg-purple-100 text-purple-700 border-purple-200';
      case 'reference': return 'bg-green-100 text-green-700 border-green-200';
      case 'transcript': return 'bg-cyan-100 text-cyan-700 border-cyan-200';
      case 'psychotest': return 'bg-pink-100 text-pink-700 border-pink-200';
      case 'knowledge_test': return 'bg-orange-100 text-orange-700 border-orange-200';
      default: return 'bg-slate-100 text-slate-700 border-slate-200';
    }
  };

  const filteredCandidates = candidates;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      <TopBar />
      
      <div className="p-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-heading font-bold text-slate-900">Talent Pool</h1>
            <p className="text-slate-600 mt-1">Manage your candidate database</p>
          </div>
          
          <div className="flex items-center gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-500 w-4 h-4" />
              <Input
                placeholder="Search candidates..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10 w-64 rounded-full border-slate-200"
              />
            </div>
            <Button 
              onClick={() => {
                setSelectedCandidate(null);
                setShowUploadDialog(true);
              }}
              className="rounded-full bg-indigo-500 hover:bg-indigo-600 text-white"
            >
              <Upload className="w-4 h-4 mr-2" />
              Upload CVs
            </Button>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-4 mb-8">
          <Card className="bg-white/70 backdrop-blur border-slate-200/50">
            <CardContent className="pt-6">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-indigo-100 flex items-center justify-center">
                  <Users className="w-6 h-6 text-indigo-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-slate-900">{total}</p>
                  <p className="text-sm text-slate-600">Total Candidates</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Main Content */}
        <div className="grid grid-cols-12 gap-6">
          {/* Candidate List */}
          <div className="col-span-5">
            <Card className="bg-white/70 backdrop-blur border-slate-200/50">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg font-heading">Candidates</CardTitle>
                <CardDescription>
                  {filteredCandidates.length} candidates shown
                </CardDescription>
              </CardHeader>
              <CardContent>
                {loading ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
                  </div>
                ) : filteredCandidates.length === 0 ? (
                  <EmptyState
                    icon={Users}
                    title="No candidates yet"
                    description="Upload CVs to start building your talent pool"
                  />
                ) : (
                  <>
                    <ScrollArea className="h-[500px]">
                      <div className="space-y-2">
                        {filteredCandidates.map((candidate) => (
                          <div
                            key={candidate.id}
                            onClick={() => setDetailCandidate(candidate)}
                            className={`p-4 rounded-xl cursor-pointer transition-all border ${
                              detailCandidate?.id === candidate.id
                                ? 'bg-indigo-50 border-indigo-200'
                                : 'bg-white border-slate-100 hover:border-indigo-200'
                            }`}
                          >
                            <div className="flex items-start justify-between">
                              <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-400 to-purple-500 flex items-center justify-center text-white font-medium">
                                  {candidate.name?.charAt(0)?.toUpperCase() || '?'}
                                </div>
                                <div>
                                  <h3 className="font-medium text-slate-900">{candidate.name}</h3>
                                  <p className="text-sm text-slate-600">{candidate.email || 'No email'}</p>
                                </div>
                              </div>
                              <div className="flex items-center gap-1">
                                {candidate.evidence?.slice(0, 3).map((ev, idx) => (
                                  <span key={idx} className="text-xs" title={ev.type}>
                                    {getEvidenceIcon(ev.type)}
                                  </span>
                                ))}
                                {candidate.evidence?.length > 3 && (
                                  <span className="text-xs text-slate-500">+{candidate.evidence.length - 3}</span>
                                )}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </ScrollArea>
                    
                    {/* Pagination */}
                    <div className="flex items-center justify-between mt-4 pt-4 border-t border-slate-100">
                      <span className="text-sm text-slate-600">
                        Page {page} of {totalPages}
                      </span>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setPage(p => Math.max(1, p - 1))}
                          disabled={page === 1}
                          className="rounded-full"
                        >
                          <ChevronLeft className="w-4 h-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                          disabled={page === totalPages}
                          className="rounded-full"
                        >
                          <ChevronRight className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Candidate Detail */}
          <div className="col-span-7">
            {detailCandidate ? (
              <Card className="bg-white/70 backdrop-blur border-slate-200/50">
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-4">
                      <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-400 to-purple-500 flex items-center justify-center text-white text-2xl font-bold">
                        {detailCandidate.name?.charAt(0)?.toUpperCase() || '?'}
                      </div>
                      <div>
                        {editMode ? (
                          <Input
                            value={editForm.name}
                            onChange={(e) => setEditForm(f => ({ ...f, name: e.target.value }))}
                            className="font-heading text-xl mb-1"
                          />
                        ) : (
                          <CardTitle className="font-heading text-xl">{detailCandidate.name}</CardTitle>
                        )}
                        <CardDescription>
                          Added {new Date(detailCandidate.created_at).toLocaleDateString()}
                        </CardDescription>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      {editMode ? (
                        <>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setEditMode(false)}
                            className="rounded-full"
                          >
                            Cancel
                          </Button>
                          <Button
                            size="sm"
                            onClick={handleSaveEdit}
                            disabled={savingEdit}
                            className="rounded-full bg-indigo-500 hover:bg-indigo-600 text-white"
                          >
                            {savingEdit && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                            <Save className="w-4 h-4 mr-2" />
                            Save
                          </Button>
                        </>
                      ) : (
                        <>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={handleEdit}
                            className="rounded-full"
                          >
                            <Edit className="w-4 h-4 mr-2" />
                            Edit
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleReparse(detailCandidate.id)}
                            disabled={reparsing}
                            className="rounded-full"
                          >
                            {reparsing ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleDelete(detailCandidate.id)}
                            className="rounded-full text-red-600 hover:bg-red-50"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <Tabs defaultValue="tags" className="w-full">
                    <TabsList className="w-full justify-start mb-4 bg-slate-100/50 p-1 rounded-xl">
                      <TabsTrigger value="tags" className="rounded-full px-6">
                        <Tag className="w-4 h-4 mr-1" />
                        Tags ({detailCandidate.tags?.length || 0})
                      </TabsTrigger>
                      <TabsTrigger value="evidence" className="rounded-full px-6">Evidence ({detailCandidate.evidence?.length || 0})</TabsTrigger>
                      <TabsTrigger value="info" className="rounded-full px-6">Contact Info</TabsTrigger>
                    </TabsList>
                    
                    {/* TAGS TAB */}
                    <TabsContent value="tags">
                      <div className="space-y-4">
                        <div className="flex justify-between items-center">
                          <h3 className="font-medium text-slate-700">Talent Tags</h3>
                          <div className="flex gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={handleExtractTags}
                              disabled={extractingTags}
                              className="rounded-full"
                            >
                              {extractingTags ? (
                                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                              ) : (
                                <Sparkles className="w-4 h-4 mr-2" />
                              )}
                              {extractingTags ? 'Extracting...' : 'Re-Extract Tags'}
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => setShowAddTagDialog(true)}
                              className="rounded-full"
                            >
                              <Plus className="w-4 h-4 mr-2" />
                              Add Tag
                            </Button>
                          </div>
                        </div>
                        
                        {/* Tags by Layer */}
                        {(() => {
                          const grouped = groupTagsByLayer(detailCandidate.tags);
                          const hasAnyTags = Object.values(grouped).some(arr => arr.length > 0);
                          
                          if (!hasAnyTags) {
                            return (
                              <div className="text-center py-8 text-slate-500">
                                <Tag className="w-12 h-12 mx-auto mb-2 opacity-50" />
                                <p>No tags yet</p>
                                <p className="text-sm">Click Re-Extract Tags to analyze evidence</p>
                              </div>
                            );
                          }
                          
                          return (
                            <div className="space-y-4">
                              {/* Layer 1: Domain/Function */}
                              <div className="p-4 bg-blue-50/50 rounded-xl border border-blue-100">
                                <div className="flex items-center justify-between mb-2">
                                  <div className="flex items-center gap-2">
                                    <span className="text-sm font-medium text-blue-700">Layer 1: Domain / Function</span>
                                    <span className="text-xs text-blue-500">(max 3)</span>
                                  </div>
                                </div>
                                <div className="flex flex-wrap gap-2">
                                  {grouped[1].length > 0 ? grouped[1].map((tag, idx) => (
                                    <div 
                                      key={idx}
                                      className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm border ${getLayerColor(1)} ${tag.source === 'MANUAL' ? 'ring-2 ring-blue-300' : ''}`}
                                    >
                                      {tag.source === 'AUTO' && tag.confidence_score && (
                                        <span className="text-xs opacity-60" title={`Confidence: ${Math.round(tag.confidence_score * 100)}%`}>
                                          {Math.round(tag.confidence_score * 100)}%
                                        </span>
                                      )}
                                      {tag.source === 'MANUAL' && <User className="w-3 h-3" />}
                                      <span>{tag.tag_value.replace(/_/g, ' ')}</span>
                                      <button
                                        onClick={() => handleDeleteTag(tag.tag_value, tag.layer)}
                                        disabled={deletingTag === tag.tag_value}
                                        className="ml-1 hover:text-red-600"
                                      >
                                        {deletingTag === tag.tag_value ? <Loader2 className="w-3 h-3 animate-spin" /> : <X className="w-3 h-3" />}
                                      </button>
                                    </div>
                                  )) : <span className="text-xs text-slate-500 italic">No domain tags</span>}
                                </div>
                              </div>
                              
                              {/* Layer 2: Job Family */}
                              <div className="p-4 bg-purple-50/50 rounded-xl border border-purple-100">
                                <div className="flex items-center justify-between mb-2">
                                  <div className="flex items-center gap-2">
                                    <span className="text-sm font-medium text-purple-700">Layer 2: Job Family</span>
                                    <span className="text-xs text-purple-500">(max 3)</span>
                                  </div>
                                </div>
                                <div className="flex flex-wrap gap-2">
                                  {grouped[2].length > 0 ? grouped[2].map((tag, idx) => (
                                    <div 
                                      key={idx}
                                      className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm border ${getLayerColor(2)} ${tag.source === 'MANUAL' ? 'ring-2 ring-purple-300' : ''}`}
                                    >
                                      {tag.source === 'AUTO' && tag.confidence_score && (
                                        <span className="text-xs opacity-60">{Math.round(tag.confidence_score * 100)}%</span>
                                      )}
                                      {tag.source === 'MANUAL' && <User className="w-3 h-3" />}
                                      <span>{tag.tag_value.replace(/_/g, ' ')}</span>
                                      <button
                                        onClick={() => handleDeleteTag(tag.tag_value, tag.layer)}
                                        disabled={deletingTag === tag.tag_value}
                                        className="ml-1 hover:text-red-600"
                                      >
                                        {deletingTag === tag.tag_value ? <Loader2 className="w-3 h-3 animate-spin" /> : <X className="w-3 h-3" />}
                                      </button>
                                    </div>
                                  )) : <span className="text-xs text-slate-500 italic">No job family tags</span>}
                                </div>
                              </div>
                              
                              {/* Layer 3: Skills */}
                              <div className="p-4 bg-green-50/50 rounded-xl border border-green-100">
                                <div className="flex items-center justify-between mb-2">
                                  <div className="flex items-center gap-2">
                                    <span className="text-sm font-medium text-green-700">Layer 3: Skills / Competencies</span>
                                    <span className="text-xs text-green-500">(max 10)</span>
                                  </div>
                                </div>
                                <div className="flex flex-wrap gap-2">
                                  {grouped[3].length > 0 ? grouped[3].map((tag, idx) => (
                                    <div 
                                      key={idx}
                                      className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm border ${getLayerColor(3)} ${tag.source === 'MANUAL' ? 'ring-2 ring-green-300' : ''}`}
                                    >
                                      {tag.source === 'AUTO' && tag.confidence_score && (
                                        <span className="text-xs opacity-60">{Math.round(tag.confidence_score * 100)}%</span>
                                      )}
                                      {tag.source === 'MANUAL' && <User className="w-3 h-3" />}
                                      <span>{tag.tag_value}</span>
                                      <button
                                        onClick={() => handleDeleteTag(tag.tag_value, tag.layer)}
                                        disabled={deletingTag === tag.tag_value}
                                        className="ml-1 hover:text-red-600"
                                      >
                                        {deletingTag === tag.tag_value ? <Loader2 className="w-3 h-3 animate-spin" /> : <X className="w-3 h-3" />}
                                      </button>
                                    </div>
                                  )) : <span className="text-xs text-slate-500 italic">No skill tags</span>}
                                </div>
                              </div>
                              
                              {/* Layer 4: Scope of Work */}
                              <div className="p-4 bg-orange-50/50 rounded-xl border border-orange-100">
                                <div className="flex items-center justify-between mb-2">
                                  <div className="flex items-center gap-2">
                                    <span className="text-sm font-medium text-orange-700">Layer 4: Scope of Work</span>
                                    <span className="text-xs text-orange-500">(max 3)</span>
                                  </div>
                                </div>
                                <div className="flex flex-wrap gap-2">
                                  {grouped[4].length > 0 ? grouped[4].map((tag, idx) => (
                                    <div 
                                      key={idx}
                                      className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm border ${getLayerColor(4)} ${tag.source === 'MANUAL' ? 'ring-2 ring-orange-300' : ''}`}
                                    >
                                      {tag.source === 'AUTO' && tag.confidence_score && (
                                        <span className="text-xs opacity-60">{Math.round(tag.confidence_score * 100)}%</span>
                                      )}
                                      {tag.source === 'MANUAL' && <User className="w-3 h-3" />}
                                      <span>{tag.tag_value}</span>
                                      <button
                                        onClick={() => handleDeleteTag(tag.tag_value, tag.layer)}
                                        disabled={deletingTag === tag.tag_value}
                                        className="ml-1 hover:text-red-600"
                                      >
                                        {deletingTag === tag.tag_value ? <Loader2 className="w-3 h-3 animate-spin" /> : <X className="w-3 h-3" />}
                                      </button>
                                    </div>
                                  )) : <span className="text-xs text-slate-500 italic">No scope tags</span>}
                                </div>
                              </div>
                              
                              {/* Legend */}
                              <div className="text-xs text-slate-500 flex items-center gap-4 pt-2 border-t border-slate-100">
                                <span className="flex items-center gap-1">
                                  <Sparkles className="w-3 h-3" /> = Auto-extracted
                                </span>
                                <span className="flex items-center gap-1">
                                  <User className="w-3 h-3" /> = Manually added
                                </span>
                                <span>% = AI confidence</span>
                              </div>
                            </div>
                          );
                        })()}
                      </div>
                    </TabsContent>
                    
                    <TabsContent value="evidence">
                      <div className="space-y-4">
                        <div className="flex justify-between items-center">
                          <h3 className="font-medium text-slate-700">Documents & Evidence</h3>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              setSelectedCandidate(detailCandidate);
                              setShowUploadDialog(true);
                            }}
                            className="rounded-full"
                          >
                            <Plus className="w-4 h-4 mr-2" />
                            Add Evidence
                          </Button>
                        </div>
                        
                        {detailCandidate.evidence?.length > 0 ? (
                          <ScrollArea className="h-[400px]">
                            <div className="space-y-3">
                              {detailCandidate.evidence.map((ev, index) => (
                                <Card key={index} className={`border ${getEvidenceColor(ev.type)}`}>
                                  <CardContent className="pt-4">
                                    <div className="flex items-start justify-between mb-2">
                                      <div className="flex items-center gap-2">
                                        <span className="text-lg">{getEvidenceIcon(ev.type)}</span>
                                        <div>
                                          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${getEvidenceColor(ev.type)}`}>
                                            {ev.type?.toUpperCase()}
                                          </span>
                                          <p className="text-sm font-medium text-slate-700 mt-1">{ev.file_name}</p>
                                        </div>
                                      </div>
                                      <div className="flex items-center gap-2">
                                        <span className="text-xs text-slate-500">
                                          {ev.uploaded_at ? new Date(ev.uploaded_at).toLocaleDateString() : ''}
                                        </span>
                                        <Button
                                          variant="ghost"
                                          size="sm"
                                          onClick={() => handleDeleteEvidence(detailCandidate.id, index, ev.type)}
                                          disabled={deletingEvidence === index}
                                          className="h-7 w-7 p-0 text-red-500 hover:text-red-700 hover:bg-red-50"
                                        >
                                          {deletingEvidence === index ? (
                                            <Loader2 className="w-4 h-4 animate-spin" />
                                          ) : (
                                            <Trash2 className="w-4 h-4" />
                                          )}
                                        </Button>
                                      </div>
                                    </div>
                                    {ev.pages && ev.pages.length > 0 && (
                                      <p className="text-xs text-slate-500 mb-2">
                                        Pages: {ev.pages.join(', ')}
                                      </p>
                                    )}
                                    {/* Content length indicator */}
                                    <div className="flex items-center justify-between mb-2">
                                      <span className="text-xs text-slate-500">
                                        Content: {ev.content?.length?.toLocaleString() || 0} characters
                                      </span>
                                      {ev.content?.length > 500 && (
                                        <Button
                                          variant="ghost"
                                          size="sm"
                                          onClick={() => setExpandedEvidence(expandedEvidence === index ? null : index)}
                                          className="text-xs h-6 px-2 text-indigo-600 hover:text-indigo-800"
                                        >
                                          {expandedEvidence === index ? 'Show Less' : 'View Full Content'}
                                        </Button>
                                      )}
                                    </div>
                                    <div className={`bg-white/50 rounded-lg p-3 overflow-y-auto ${expandedEvidence === index ? 'max-h-96' : 'max-h-32'}`}>
                                      <pre className="text-xs text-slate-600 whitespace-pre-wrap font-mono">
                                        {expandedEvidence === index 
                                          ? ev.content 
                                          : (ev.content?.substring(0, 500) + (ev.content?.length > 500 ? '...' : ''))}
                                      </pre>
                                    </div>
                                    {expandedEvidence === index && ev.content?.length > 500 && (
                                      <p className="text-xs text-green-600 mt-2 flex items-center gap-1">
                                        <CheckCircle2 className="w-3 h-3" />
                                        Full content displayed ({ev.content.length.toLocaleString()} characters)
                                      </p>
                                    )}
                                  </CardContent>
                                </Card>
                              ))}
                            </div>
                          </ScrollArea>
                        ) : (
                          <div className="text-center py-8 text-slate-500">
                            <FileText className="w-12 h-12 mx-auto mb-2 opacity-50" />
                            <p>No evidence uploaded yet</p>
                          </div>
                        )}
                      </div>
                    </TabsContent>
                    
                    <TabsContent value="info">
                      <div className="space-y-4">
                        <div className="flex items-center gap-3 p-4 bg-slate-50 rounded-xl">
                          <Mail className="w-5 h-5 text-slate-500" />
                          {editMode ? (
                            <Input
                              value={editForm.email}
                              onChange={(e) => setEditForm(f => ({ ...f, email: e.target.value }))}
                              placeholder="Email"
                            />
                          ) : (
                            <span className="text-slate-700">{detailCandidate.email || 'No email'}</span>
                          )}
                        </div>
                        <div className="flex items-center gap-3 p-4 bg-slate-50 rounded-xl">
                          <Phone className="w-5 h-5 text-slate-500" />
                          {editMode ? (
                            <Input
                              value={editForm.phone}
                              onChange={(e) => setEditForm(f => ({ ...f, phone: e.target.value }))}
                              placeholder="Phone"
                            />
                          ) : (
                            <span className="text-slate-700">{detailCandidate.phone || 'No phone'}</span>
                          )}
                        </div>
                      </div>
                    </TabsContent>
                  </Tabs>
                </CardContent>
              </Card>
            ) : (
              <Card className="bg-white/70 backdrop-blur border-slate-200/50 h-full flex items-center justify-center">
                <div className="text-center py-16">
                  <User className="w-16 h-16 mx-auto mb-4 text-slate-300" />
                  <h3 className="text-lg font-medium text-slate-700">Select a candidate</h3>
                  <p className="text-slate-500">Click on a candidate to view details</p>
                </div>
              </Card>
            )}
          </div>
        </div>

        {/* Upload Dialog */}
        <Dialog open={showUploadDialog} onOpenChange={setShowUploadDialog}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle className="font-heading">
                {selectedCandidate ? `Add Evidence for ${selectedCandidate.name}` : 'Upload Candidates'}
              </DialogTitle>
              <DialogDescription>
                {selectedCandidate 
                  ? 'Upload additional documents (CV, psychotest, knowledge test)'
                  : 'Upload PDF files or a ZIP package with multiple evidence files.'}
              </DialogDescription>
            </DialogHeader>
            
            {!selectedCandidate && (
              <div className="flex gap-2 mb-4">
                <Button
                  variant={uploadMode === 'pdf' ? 'default' : 'outline'}
                  onClick={() => setUploadMode('pdf')}
                  className={`flex-1 rounded-full ${uploadMode === 'pdf' ? 'bg-indigo-500 hover:bg-indigo-600 text-white' : ''}`}
                  size="sm"
                >
                  <FileText className="w-4 h-4 mr-2" />
                  PDF Files
                </Button>
                <Button
                  variant={uploadMode === 'zip' ? 'default' : 'outline'}
                  onClick={() => setUploadMode('zip')}
                  className={`flex-1 rounded-full ${uploadMode === 'zip' ? 'bg-indigo-500 hover:bg-indigo-600 text-white' : ''}`}
                  size="sm"
                >
                  <FolderArchive className="w-4 h-4 mr-2" />
                  ZIP Package
                </Button>
              </div>
            )}
            
            <div className="space-y-4 pt-2">
              {uploadMode === 'pdf' || selectedCandidate ? (
                <div 
                  className="border-2 border-dashed border-slate-200 rounded-xl p-8 text-center hover:border-indigo-300 transition-colors cursor-pointer"
                  onClick={() => fileInputRef.current?.click()}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf"
                    multiple
                    onChange={handleFileSelect}
                    className="hidden"
                  />
                  {uploading ? (
                    <Loader2 className="w-8 h-8 mx-auto mb-2 text-indigo-500 animate-spin" />
                  ) : (
                    <Upload className="w-8 h-8 mx-auto mb-2 text-slate-500" />
                  )}
                  <p className="font-medium text-slate-700">
                    {uploading ? 'Processing...' : 'Click to upload PDF files'}
                  </p>
                  <p className="text-sm text-slate-600 mt-1">
                    {selectedCandidate ? 'Add documents to this candidate' : 'Each PDF creates one candidate (with auto evidence splitting)'}
                  </p>
                </div>
              ) : (
                <div 
                  className="border-2 border-dashed border-slate-200 rounded-xl p-8 text-center hover:border-indigo-300 transition-colors cursor-pointer"
                  onClick={() => zipInputRef.current?.click()}
                >
                  <input
                    ref={zipInputRef}
                    type="file"
                    accept=".zip"
                    onChange={handleZipSelect}
                    className="hidden"
                  />
                  {zipUploading ? (
                    <Loader2 className="w-8 h-8 mx-auto mb-2 text-indigo-500 animate-spin" />
                  ) : (
                    <FolderArchive className="w-8 h-8 mx-auto mb-2 text-slate-500" />
                  )}
                  <p className="font-medium text-slate-700">
                    {zipUploading ? 'Processing ZIP...' : 'Click to upload ZIP file'}
                  </p>
                  <p className="text-sm text-slate-600 mt-1">One ZIP = One candidate with multiple evidence</p>
                </div>
              )}
            </div>
          </DialogContent>
        </Dialog>

        {/* BULK Duplicate Detection Dialog */}
        <Dialog open={showBulkDuplicateDialog} onOpenChange={(open) => {
          if (!open && !processingBulk) {
            setShowBulkDuplicateDialog(false);
            setBulkDuplicates([]);
            setBulkDecisions({});
          }
        }}>
          <DialogContent className="max-w-5xl max-h-[90vh] overflow-hidden flex flex-col">
            <DialogHeader>
              <DialogTitle className="font-heading flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-amber-500" />
                {bulkDuplicates.length} Potential Duplicate(s) Detected
              </DialogTitle>
              <DialogDescription>
                Review each duplicate and choose an action. All items must have a decision before processing.
              </DialogDescription>
            </DialogHeader>
            
            {/* Batch Actions */}
            <div className="flex gap-2 py-2 border-b border-slate-200">
              <span className="text-sm text-slate-600 mr-2">Batch Actions:</span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleBatchAction('merge')}
                className="rounded-full text-xs"
              >
                <GitMerge className="w-3 h-3 mr-1" />
                Merge All
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleBatchAction('create')}
                className="rounded-full text-xs"
              >
                <UserPlus className="w-3 h-3 mr-1" />
                Create All New
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleBatchAction('replace')}
                className="rounded-full text-xs"
              >
                <Replace className="w-3 h-3 mr-1" />
                Replace All
              </Button>
            </div>

            {/* Side by side comparison */}
            <div className="flex-1 overflow-hidden">
              <div className="grid grid-cols-12 gap-4 h-full">
                {/* Left: List of duplicates */}
                <div className="col-span-3 border-r border-slate-200 pr-4 overflow-y-auto">
                  <p className="text-xs font-medium text-slate-600 mb-2">Files with duplicates:</p>
                  <div className="space-y-2">
                    {bulkDuplicates.map((dup, idx) => (
                      <div
                        key={idx}
                        onClick={() => setSelectedBulkIndex(idx)}
                        className={`p-3 rounded-lg cursor-pointer border transition-colors ${
                          selectedBulkIndex === idx
                            ? 'bg-indigo-50 border-indigo-200'
                            : 'bg-white border-slate-100 hover:border-slate-200'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <p className="text-sm font-medium truncate" title={dup.file.name}>
                            {dup.file.name.length > 20 ? dup.file.name.substring(0, 20) + '...' : dup.file.name}
                          </p>
                          {bulkDecisions[idx]?.action && (
                            <CheckCircle2 className="w-4 h-4 text-green-500" />
                          )}
                        </div>
                        <p className="text-xs text-slate-500 mt-1">
                          {dup.duplicates.length} match(es)
                        </p>
                        {bulkDecisions[idx]?.action && (
                          <span className={`text-xs px-2 py-0.5 rounded-full mt-1 inline-block ${
                            bulkDecisions[idx].action === 'merge' ? 'bg-blue-100 text-blue-700' :
                            bulkDecisions[idx].action === 'create' ? 'bg-green-100 text-green-700' :
                            'bg-orange-100 text-orange-700'
                          }`}>
                            {bulkDecisions[idx].action}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Right: Side by side comparison */}
                <div className="col-span-9 overflow-y-auto">
                  {bulkDuplicates[selectedBulkIndex] && (
                    <div className="grid grid-cols-2 gap-4">
                      {/* New Upload (Left) */}
                      <Card className="border-green-200 bg-green-50/30">
                        <CardHeader className="pb-2">
                          <CardTitle className="text-sm flex items-center gap-2">
                            <UserPlus className="w-4 h-4 text-green-600" />
                            New Upload
                          </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-3">
                          <div>
                            <Label className="text-xs text-slate-600">File</Label>
                            <p className="text-sm font-medium">{bulkDuplicates[selectedBulkIndex].file.name}</p>
                          </div>
                          <div>
                            <Label className="text-xs text-slate-600">Extracted Name</Label>
                            <p className="text-sm font-medium">{bulkDuplicates[selectedBulkIndex].extractedInfo?.name || '-'}</p>
                          </div>
                          <div>
                            <Label className="text-xs text-slate-600">Extracted Email</Label>
                            <p className="text-sm font-medium">{bulkDuplicates[selectedBulkIndex].extractedInfo?.email || '-'}</p>
                          </div>
                          <div>
                            <Label className="text-xs text-slate-600">Extracted Phone</Label>
                            <p className="text-sm font-medium">{bulkDuplicates[selectedBulkIndex].extractedInfo?.phone || '-'}</p>
                          </div>
                          <div>
                            <Label className="text-xs text-slate-600">Evidence Detected</Label>
                            <div className="flex flex-wrap gap-1 mt-1">
                              {bulkDuplicates[selectedBulkIndex].evidence_preview?.map((ev, i) => (
                                <span key={i} className={`text-xs px-2 py-0.5 rounded-full ${getEvidenceColor(ev.type)}`}>
                                  {getEvidenceIcon(ev.type)} {ev.type}
                                </span>
                              ))}
                            </div>
                          </div>
                        </CardContent>
                      </Card>

                      {/* Existing Match (Right) */}
                      <Card className="border-amber-200 bg-amber-50/30">
                        <CardHeader className="pb-2">
                          <CardTitle className="text-sm flex items-center gap-2">
                            <UserCheck className="w-4 h-4 text-amber-600" />
                            Existing Match(es)
                          </CardTitle>
                        </CardHeader>
                        <CardContent>
                          <div className="space-y-2">
                            {bulkDuplicates[selectedBulkIndex].duplicates.map((match) => (
                              <div 
                                key={match.candidate_id}
                                className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                                  bulkDecisions[selectedBulkIndex]?.targetId === match.candidate_id
                                    ? 'border-indigo-500 bg-indigo-50'
                                    : 'border-slate-200 bg-white hover:border-slate-300'
                                }`}
                                onClick={() => {
                                  if (bulkDecisions[selectedBulkIndex]?.action === 'merge' || 
                                      bulkDecisions[selectedBulkIndex]?.action === 'replace') {
                                    handleBulkDecision(selectedBulkIndex, bulkDecisions[selectedBulkIndex].action, match.candidate_id);
                                  }
                                }}
                              >
                                <p className="font-medium text-sm">{match.candidate_name}</p>
                                <p className="text-xs text-slate-600">{match.candidate_email}</p>
                                {match.candidate_phone && <p className="text-xs text-slate-500">{match.candidate_phone}</p>}
                                <div className="flex gap-1 mt-2">
                                  {match.match_reasons?.map((reason, i) => (
                                    <span key={i} className={`text-xs px-2 py-0.5 rounded-full ${
                                      reason === 'email_match' ? 'bg-red-100 text-red-700' :
                                      reason === 'phone_match' ? 'bg-orange-100 text-orange-700' :
                                      'bg-yellow-100 text-yellow-700'
                                    }`}>
                                      {reason.replace('_', ' ')}
                                    </span>
                                  ))}
                                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                                    match.confidence === 'high' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'
                                  }`}>
                                    {match.confidence}
                                  </span>
                                </div>
                              </div>
                            ))}
                          </div>
                        </CardContent>
                      </Card>
                    </div>
                  )}

                  {/* Action buttons for selected item */}
                  {bulkDuplicates[selectedBulkIndex] && (
                    <div className="mt-4 p-4 bg-slate-50 rounded-lg">
                      <p className="text-sm font-medium text-slate-700 mb-3">Choose action for this file:</p>
                      <div className="flex gap-2">
                        <Button
                          variant={bulkDecisions[selectedBulkIndex]?.action === 'merge' ? 'default' : 'outline'}
                          size="sm"
                          onClick={() => handleBulkDecision(
                            selectedBulkIndex, 
                            'merge', 
                            bulkDecisions[selectedBulkIndex]?.targetId || bulkDuplicates[selectedBulkIndex].duplicates[0]?.candidate_id
                          )}
                          className={`rounded-full ${bulkDecisions[selectedBulkIndex]?.action === 'merge' ? 'bg-blue-500 hover:bg-blue-600' : ''}`}
                        >
                          <GitMerge className="w-4 h-4 mr-2" />
                          Merge (Add Evidence)
                        </Button>
                        <Button
                          variant={bulkDecisions[selectedBulkIndex]?.action === 'create' ? 'default' : 'outline'}
                          size="sm"
                          onClick={() => handleBulkDecision(selectedBulkIndex, 'create', null)}
                          className={`rounded-full ${bulkDecisions[selectedBulkIndex]?.action === 'create' ? 'bg-green-500 hover:bg-green-600' : ''}`}
                        >
                          <UserPlus className="w-4 h-4 mr-2" />
                          Create New
                        </Button>
                        <Button
                          variant={bulkDecisions[selectedBulkIndex]?.action === 'replace' ? 'default' : 'outline'}
                          size="sm"
                          onClick={() => handleBulkDecision(
                            selectedBulkIndex, 
                            'replace', 
                            bulkDecisions[selectedBulkIndex]?.targetId || bulkDuplicates[selectedBulkIndex].duplicates[0]?.candidate_id
                          )}
                          className={`rounded-full ${bulkDecisions[selectedBulkIndex]?.action === 'replace' ? 'bg-orange-500 hover:bg-orange-600' : ''}`}
                        >
                          <Replace className="w-4 h-4 mr-2" />
                          Replace (Delete Old)
                        </Button>
                      </div>
                      {(bulkDecisions[selectedBulkIndex]?.action === 'merge' || bulkDecisions[selectedBulkIndex]?.action === 'replace') && (
                        <p className="text-xs text-slate-600 mt-2">
                          Click on an existing candidate above to select the target for {bulkDecisions[selectedBulkIndex]?.action}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>

            <DialogFooter className="border-t border-slate-200 pt-4">
              <div className="flex items-center justify-between w-full">
                <span className="text-sm text-slate-600">
                  {Object.values(bulkDecisions).filter(d => d?.action).length} of {bulkDuplicates.length} decisions made
                </span>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    onClick={() => {
                      setShowBulkDuplicateDialog(false);
                      setBulkDuplicates([]);
                      setBulkDecisions({});
                    }}
                    disabled={processingBulk}
                    className="rounded-full"
                  >
                    Cancel All
                  </Button>
                  <Button
                    onClick={processBulkDecisions}
                    disabled={!allDecisionsMade() || processingBulk}
                    className="bg-indigo-500 hover:bg-indigo-600 text-white rounded-full"
                  >
                    {processingBulk && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                    Process All ({Object.values(bulkDecisions).filter(d => d?.action).length})
                  </Button>
                </div>
              </div>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* ZIP Duplicate Dialog */}
        <Dialog open={showZipDuplicateDialog} onOpenChange={(open) => {
          if (!open) {
            setShowZipDuplicateDialog(false);
            setZipDuplicates(null);
            setPendingZipFile(null);
            setSelectedMergeTarget(null);
          }
        }}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle className="font-heading flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-amber-500" />
                Potential Duplicate Detected (ZIP)
              </DialogTitle>
              <DialogDescription>
                The candidate in this ZIP file may already exist. Choose how to proceed.
              </DialogDescription>
            </DialogHeader>
            
            {zipDuplicates && (
              <div className="space-y-4 py-4">
                <Card className="border-amber-200 bg-amber-50/50">
                  <CardContent className="pt-4">
                    <p className="text-sm font-medium text-slate-700 mb-3">
                      Found {zipDuplicates.duplicates?.length || 0} potential match(es):
                    </p>
                    <div className="space-y-2">
                      {zipDuplicates.duplicates?.map((match) => (
                        <div 
                          key={match.candidate_id} 
                          className={`flex items-center gap-3 p-3 bg-white rounded-lg border cursor-pointer transition-colors ${
                            selectedMergeTarget === match.candidate_id 
                              ? 'border-indigo-500 ring-2 ring-indigo-200' 
                              : 'border-slate-200 hover:border-slate-300'
                          }`}
                          onClick={() => setSelectedMergeTarget(match.candidate_id)}
                        >
                          <div className="w-10 h-10 rounded-full bg-indigo-100 flex items-center justify-center">
                            <UserCheck className="w-5 h-5 text-indigo-600" />
                          </div>
                          <div className="flex-1">
                            <p className="font-medium text-sm">{match.candidate_name}</p>
                            <p className="text-xs text-slate-600">{match.candidate_email}</p>
                          </div>
                          <div className="flex flex-wrap gap-1">
                            {match.match_reasons?.map((reason, i) => (
                              <span key={i} className={`text-xs px-2 py-0.5 rounded-full ${
                                reason === 'email_match' ? 'bg-red-100 text-red-700' :
                                reason === 'phone_match' ? 'bg-orange-100 text-orange-700' :
                                'bg-yellow-100 text-yellow-700'
                              }`}>
                                {reason.replace('_', ' ')}
                              </span>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}
            
            <DialogFooter className="gap-2">
              <Button
                variant="outline"
                onClick={() => {
                  setShowZipDuplicateDialog(false);
                  setZipDuplicates(null);
                  setPendingZipFile(null);
                }}
                className="rounded-full"
              >
                Cancel
              </Button>
              <Button
                variant="outline"
                onClick={handleZipForceCreate}
                disabled={zipUploading}
                className="rounded-full"
              >
                {zipUploading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                <UserPlus className="w-4 h-4 mr-2" />
                Create New
              </Button>
              <Button
                onClick={() => selectedMergeTarget && handleZipMerge(selectedMergeTarget)}
                disabled={zipUploading || !selectedMergeTarget}
                className="bg-indigo-500 hover:bg-indigo-600 text-white rounded-full"
              >
                {zipUploading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                <GitMerge className="w-4 h-4 mr-2" />
                Merge into Selected
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Add Tag Dialog */}
        <Dialog open={showAddTagDialog} onOpenChange={setShowAddTagDialog}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="font-heading flex items-center gap-2">
                <Tag className="w-5 h-5 text-indigo-500" />
                Add Tag
              </DialogTitle>
              <DialogDescription>
                Manually add a tag to this candidate. Manual tags override auto-generated tags.
              </DialogDescription>
            </DialogHeader>
            
            <div className="space-y-4 py-4">
              <div>
                <Label>Layer</Label>
                <Select value={String(addTagLayer)} onValueChange={(v) => { setAddTagLayer(Number(v)); setAddTagValue(''); }}>
                  <SelectTrigger className="mt-1">
                    <SelectValue placeholder="Select layer" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="1">Layer 1: Domain / Function (max 3)</SelectItem>
                    <SelectItem value="2">Layer 2: Job Family (max 3)</SelectItem>
                    <SelectItem value="3">Layer 3: Skill / Competency (max 10)</SelectItem>
                    <SelectItem value="4">Layer 4: Scope of Work (max 3)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              
              <div>
                <Label>Tag Value</Label>
                {addTagLayer === 3 ? (
                  <Input
                    value={addTagValue}
                    onChange={(e) => setAddTagValue(e.target.value)}
                    placeholder="Enter skill name (e.g., Python, Excel)"
                    className="mt-1"
                  />
                ) : (
                  <Select value={addTagValue} onValueChange={setAddTagValue}>
                    <SelectTrigger className="mt-1">
                      <SelectValue placeholder="Select tag" />
                    </SelectTrigger>
                    <SelectContent>
                      {tagLibrary?.layers?.[addTagLayer]?.tags?.map((tag) => (
                        <SelectItem key={tag} value={tag}>
                          {tag.replace(/_/g, ' ')}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
                {addTagLayer === 4 && tagLibrary?.layers?.[4]?.definitions && (
                  <div className="mt-2 text-xs text-slate-600 space-y-1">
                    <p><strong>OPERATIONAL:</strong> {tagLibrary.layers[4].definitions.OPERATIONAL}</p>
                    <p><strong>TACTICAL:</strong> {tagLibrary.layers[4].definitions.TACTICAL}</p>
                    <p><strong>STRATEGIC:</strong> {tagLibrary.layers[4].definitions.STRATEGIC}</p>
                  </div>
                )}
              </div>
            </div>
            
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => {
                  setShowAddTagDialog(false);
                  setAddTagValue('');
                }}
                className="rounded-full"
              >
                Cancel
              </Button>
              <Button
                onClick={handleAddTag}
                disabled={!addTagValue}
                className="bg-indigo-500 hover:bg-indigo-600 text-white rounded-full"
              >
                <Plus className="w-4 h-4 mr-2" />
                Add Tag
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
};

export default Candidates;
