import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { 
  Shield, Users, CheckCircle, XCircle, DollarSign, 
  BarChart3, Briefcase, FileText, TrendingUp, LogOut,
  Clock, Mail, UserCheck, UserX, Edit2, Save, Settings as SettingsIcon,
  Plus, Minus, X
} from 'lucide-react';
import { toast } from 'sonner';
import axios from 'axios';
import { SuperAdminSettings } from '../components/admin/SuperAdminSettings';

const API_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

export const SuperAdmin = () => {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [editingCredits, setEditingCredits] = useState({});
  const [addingCredits, setAddingCredits] = useState({}); // Track which user is in add/subtract mode
  const [pagination, setPagination] = useState({ skip: 0, limit: 20, total: 0 });
  const [searchQuery, setSearchQuery] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    const adminToken = localStorage.getItem('admin_token');
    if (!adminToken) {
      toast.error('Admin authentication required');
      navigate('/admin-login');
      return;
    }
    
    loadData();
  }, [navigate]);

  const getAuthHeaders = () => {
    const token = localStorage.getItem('admin_token');
    return {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    };
  };

  const loadData = async (skip = 0, search = '') => {
    try {
      const [statsRes, usersRes] = await Promise.all([
        axios.get(`${API_URL}/api/admin/dashboard`, getAuthHeaders()),
        axios.get(`${API_URL}/api/admin/users?skip=${skip}&limit=20&search=${search}`, getAuthHeaders())
      ]);
      
      setStats(statsRes.data);
      setUsers(usersRes.data.users);
      setPagination({
        skip: usersRes.data.skip,
        limit: usersRes.data.limit,
        total: usersRes.data.total
      });
    } catch (error) {
      console.error('Failed to load admin data:', error);
      if (error.response?.status === 401 || error.response?.status === 403) {
        toast.error('Admin session expired');
        handleLogout();
      }
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('admin_token');
    localStorage.removeItem('admin_user');
    navigate('/admin-login');
  };

  const handleApprove = async (userId) => {
    try {
      await axios.post(
        `${API_URL}/api/admin/users/${userId}/approve?default_credits=100`,
        {},
        getAuthHeaders()
      );
      toast.success('User approved successfully');
      loadData();
    } catch (error) {
      toast.error('Failed to approve user');
    }
  };

  const handleReject = async (userId) => {
    try {
      await axios.post(
        `${API_URL}/api/admin/users/${userId}/reject`,
        {},
        getAuthHeaders()
      );
      toast.success('User rejected');
      loadData();
    } catch (error) {
      toast.error('Failed to reject user');
    }
  };

  const handleUpdateCredits = async (userId, newCredits) => {
    try {
      await axios.put(
        `${API_URL}/api/admin/users/${userId}`,
        { credits: parseFloat(newCredits) },
        getAuthHeaders()
      );
      toast.success('Credits updated');
      setEditingCredits(prev => {
        const updated = { ...prev };
        delete updated[userId];
        return updated;
      });
      setAddingCredits(prev => {
        const updated = { ...prev };
        delete updated[userId];
        return updated;
      });
      loadData();
    } catch (error) {
      toast.error('Failed to update credits');
    }
  };

  const handleAddCredits = async (userId, amount) => {
    const user = users.find(u => u.id === userId);
    if (!user) return;
    
    const newTotal = (user.credits || 0) + amount;
    await handleUpdateCredits(userId, newTotal);
  };

  const handleSubtractCredits = async (userId, amount) => {
    const user = users.find(u => u.id === userId);
    if (!user) return;
    
    const newTotal = (user.credits || 0) - amount;
    await handleUpdateCredits(userId, newTotal);
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-purple-50">
        <div className="animate-pulse text-purple-600">Loading admin panel...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-purple-50">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-8 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
              <Shield className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="font-heading font-bold text-xl text-slate-900">Super Admin</h1>
              <p className="text-sm text-slate-600">Aikrut Control Panel</p>
            </div>
          </div>
          
          <Button
            onClick={handleLogout}
            variant="outline"
            className="border-slate-300 hover:bg-slate-100"
          >
            <LogOut className="w-4 h-4 mr-2" />
            Logout
          </Button>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-8 py-8">
        <Tabs defaultValue="dashboard" className="w-full">
          <TabsList className="grid w-full max-w-md grid-cols-2 mb-8">
            <TabsTrigger value="dashboard" className="flex items-center gap-2">
              <BarChart3 className="w-4 h-4" />
              Dashboard
            </TabsTrigger>
            <TabsTrigger value="settings" className="flex items-center gap-2">
              <SettingsIcon className="w-4 h-4" />
              Settings
            </TabsTrigger>
          </TabsList>

          {/* Dashboard Tab */}
          <TabsContent value="dashboard" className="space-y-8">
        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <Card className="border-slate-100 shadow-soft">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-600">Total Users</p>
                  <p className="text-3xl font-bold text-slate-900 mt-1">{stats?.total_users || 0}</p>
                </div>
                <div className="w-12 h-12 rounded-full bg-blue-100 flex items-center justify-center">
                  <Users className="w-6 h-6 text-blue-600" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-slate-100 shadow-soft">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-600">Pending Approval</p>
                  <p className="text-3xl font-bold text-orange-600 mt-1">{stats?.pending_users || 0}</p>
                </div>
                <div className="w-12 h-12 rounded-full bg-orange-100 flex items-center justify-center">
                  <Clock className="w-6 h-6 text-orange-600" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-slate-100 shadow-soft">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-600">Active Users</p>
                  <p className="text-3xl font-bold text-green-600 mt-1">{stats?.active_users || 0}</p>
                </div>
                <div className="w-12 h-12 rounded-full bg-green-100 flex items-center justify-center">
                  <UserCheck className="w-6 h-6 text-green-600" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-slate-100 shadow-soft">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-600">Total Credits</p>
                  <p className="text-3xl font-bold text-purple-600 mt-1">{stats?.total_credits_distributed?.toFixed(0) || 0}</p>
                </div>
                <div className="w-12 h-12 rounded-full bg-purple-100 flex items-center justify-center">
                  <DollarSign className="w-6 h-6 text-purple-600" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-slate-100 shadow-soft">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-600">Total Jobs</p>
                  <p className="text-3xl font-bold text-slate-900 mt-1">{stats?.total_jobs || 0}</p>
                </div>
                <div className="w-12 h-12 rounded-full bg-indigo-100 flex items-center justify-center">
                  <Briefcase className="w-6 h-6 text-indigo-600" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-slate-100 shadow-soft">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-600">Total Candidates</p>
                  <p className="text-3xl font-bold text-slate-900 mt-1">{stats?.total_candidates || 0}</p>
                </div>
                <div className="w-12 h-12 rounded-full bg-teal-100 flex items-center justify-center">
                  <FileText className="w-6 h-6 text-teal-600" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-slate-100 shadow-soft">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-600">Total Analyses</p>
                  <p className="text-3xl font-bold text-slate-900 mt-1">{stats?.total_analyses || 0}</p>
                </div>
                <div className="w-12 h-12 rounded-full bg-pink-100 flex items-center justify-center">
                  <BarChart3 className="w-6 h-6 text-pink-600" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* User Management */}
        <Card className="border-slate-100 shadow-soft">
          <CardHeader>
            <CardTitle className="font-heading flex items-center gap-2">
              <Users className="w-5 h-5 text-purple-500" />
              User Management
            </CardTitle>
            <CardDescription>
              Approve users, manage credits, and monitor activity
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-200">
                    <th className="text-left py-3 px-4 text-sm font-medium text-slate-600">User</th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-slate-600">Status</th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-slate-600">Credits</th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-slate-600">Stats</th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-slate-600">Created</th>
                    <th className="text-right py-3 px-4 text-sm font-medium text-slate-600">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((user) => (
                    <tr key={user.id} className="border-b border-slate-100 hover:bg-slate-50">
                      <td className="py-3 px-4">
                        <div>
                          <p className="font-medium text-slate-900">{user.name}</p>
                          <p className="text-sm text-slate-600">{user.email}</p>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex gap-2">
                          {user.is_approved ? (
                            <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs bg-green-100 text-green-700">
                              <CheckCircle className="w-3 h-3" />
                              Approved
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs bg-orange-100 text-orange-700">
                              <Clock className="w-3 h-3" />
                              Pending
                            </span>
                          )}
                          {user.is_active ? (
                            <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs bg-blue-100 text-blue-700">
                              Active
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs bg-slate-100 text-slate-700">
                              Inactive
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        {addingCredits[user.id] !== undefined ? (
                          <div className="flex items-center gap-2">
                            <Input
                              type="number"
                              value={addingCredits[user.id]}
                              onChange={(e) => setAddingCredits(prev => ({ ...prev, [user.id]: e.target.value }))}
                              placeholder="Amount"
                              className="w-20 h-8"
                              step="1"
                            />
                            <Button
                              size="sm"
                              onClick={() => handleAddCredits(user.id, parseFloat(addingCredits[user.id] || 0))}
                              className="h-8 px-2 bg-green-500 hover:bg-green-600"
                            >
                              <Plus className="w-3 h-3" />
                            </Button>
                            <Button
                              size="sm"
                              onClick={() => handleSubtractCredits(user.id, parseFloat(addingCredits[user.id] || 0))}
                              className="h-8 px-2 bg-red-500 hover:bg-red-600"
                            >
                              <Minus className="w-3 h-3" />
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => setAddingCredits(prev => {
                                const updated = { ...prev };
                                delete updated[user.id];
                                return updated;
                              })}
                              className="h-8 px-2"
                            >
                              <X className="w-3 h-3" />
                            </Button>
                          </div>
                        ) : (
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-slate-900">{user.credits?.toFixed(2) || '0.00'}</span>
                            <button
                              onClick={() => setAddingCredits(prev => ({ ...prev, [user.id]: '' }))}
                              className="text-slate-500 hover:text-purple-600"
                              title="Add/Subtract credits"
                            >
                              <Edit2 className="w-3 h-3" />
                            </button>
                          </div>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <div className="text-sm text-slate-600">
                          <p>Jobs: {user.stats?.jobs_count || 0}</p>
                          <p>CVs: {user.stats?.candidates_count || 0}</p>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <span className="text-sm text-slate-600">
                          {new Date(user.created_at).toLocaleDateString()}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex justify-end gap-2">
                          {!user.is_approved && (
                            <>
                              <Button
                                size="sm"
                                onClick={() => handleApprove(user.id)}
                                className="bg-green-500 hover:bg-green-600 text-white h-8"
                              >
                                <CheckCircle className="w-3 h-3 mr-1" />
                                Approve
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleReject(user.id)}
                                className="border-red-300 text-red-600 hover:bg-red-50 h-8"
                              >
                                <XCircle className="w-3 h-3 mr-1" />
                                Reject
                              </Button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {pagination.total > pagination.limit && (
              <div className="flex items-center justify-between px-4 py-4 border-t border-slate-100">
                <p className="text-sm text-slate-600">
                  Showing {pagination.skip + 1} to {Math.min(pagination.skip + pagination.limit, pagination.total)} of {pagination.total} users
                </p>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => loadData(Math.max(0, pagination.skip - pagination.limit), searchQuery)}
                    disabled={pagination.skip === 0}
                    className="h-8"
                  >
                    Previous
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => loadData(pagination.skip + pagination.limit, searchQuery)}
                    disabled={pagination.skip + pagination.limit >= pagination.total}
                    className="h-8"
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
          </TabsContent>

          {/* Settings Tab */}
          <TabsContent value="settings">
            <SuperAdminSettings />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};
