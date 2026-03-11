import React, { useState, useEffect } from 'react';
import { TopBar } from '../components/layout/TopBar';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { dashboardAPI, jobsAPI, candidatesAPI } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { Users, Briefcase, BarChart3, TrendingUp, Clock, CheckCircle, Plus } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { EmptyState } from '../components/common/EmptyState';
import { ScoreRing } from '../components/common/ScoreRing';

export const Dashboard = () => {
  const [stats, setStats] = useState(null);
  const [activity, setActivity] = useState([]);
  const [recentJobs, setRecentJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const { user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    try {
      const [statsRes, activityRes, jobsRes] = await Promise.all([
        dashboardAPI.getStats(),
        dashboardAPI.getRecentActivity(),
        jobsAPI.list()
      ]);
      setStats(statsRes.data);
      setActivity(activityRes.data);
      setRecentJobs(jobsRes.data.slice(0, 5));
    } catch (error) {
      console.error('Failed to load dashboard:', error);
    } finally {
      setLoading(false);
    }
  };

  const statCards = [
    { 
      label: 'Total Candidates', 
      value: stats?.total_candidates || 0, 
      icon: Users,
      color: 'bg-indigo-50 text-indigo-600',
      trend: '+12%'
    },
    { 
      label: 'Open Positions', 
      value: stats?.open_jobs || 0, 
      icon: Briefcase,
      color: 'bg-green-50 text-green-600',
      trend: '+3'
    },
    { 
      label: 'Analyses Completed', 
      value: stats?.analyses_completed || 0, 
      icon: BarChart3,
      color: 'bg-purple-50 text-purple-600',
      trend: '+28%'
    },
    { 
      label: 'Average Score', 
      value: stats?.avg_score || 0, 
      icon: TrendingUp,
      color: 'bg-amber-50 text-amber-600',
      isScore: true
    },
  ];

  const getActivityIcon = (type) => {
    switch (type) {
      case 'candidate_added': return <Users className="w-4 h-4" />;
      case 'job_created': return <Briefcase className="w-4 h-4" />;
      case 'analysis_completed': return <CheckCircle className="w-4 h-4" />;
      default: return <Clock className="w-4 h-4" />;
    }
  };

  const getActivityColor = (type) => {
    switch (type) {
      case 'candidate_added': return 'bg-indigo-100 text-indigo-600';
      case 'job_created': return 'bg-green-100 text-green-600';
      case 'analysis_completed': return 'bg-purple-100 text-purple-600';
      default: return 'bg-slate-100 text-slate-600';
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-pulse text-indigo-500">Loading...</div>
      </div>
    );
  }

  const hasCompany = user?.company_id;

  return (
    <div className="min-h-screen" data-testid="dashboard">
      <TopBar title="Dashboard" subtitle={`Welcome back, ${user?.name?.split(' ')[0]}`} />
      
      <div className="p-8">
        {!hasCompany ? (
          <Card className="border-slate-100 shadow-soft">
            <EmptyState
              icon={Briefcase}
              title="Set up your company first"
              description="Before you can start screening candidates, you need to set up your company profile and values."
              actionLabel="Set Up Company"
              onAction={() => navigate('/company')}
            />
          </Card>
        ) : (
          <>
            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
              {statCards.map((stat, index) => {
                const Icon = stat.icon;
                return (
                  <Card key={index} className="border-slate-100 shadow-soft animate-slide-up" style={{ animationDelay: `${index * 0.05}s` }}>
                    <CardContent className="p-6">
                      <div className="flex items-start justify-between">
                        <div>
                          <p className="text-sm text-slate-600 mb-1">{stat.label}</p>
                          {stat.isScore ? (
                            <div className="flex items-center gap-3">
                              <ScoreRing score={stat.value} size={48} strokeWidth={5} />
                            </div>
                          ) : (
                            <p className="text-3xl font-bold text-slate-900">{stat.value}</p>
                          )}
                        </div>
                        <div className={`p-3 rounded-xl ${stat.color}`}>
                          <Icon className="w-5 h-5" />
                        </div>
                      </div>
                      {stat.trend && (
                        <p className="text-xs text-green-600 mt-2">
                          <TrendingUp className="w-3 h-3 inline mr-1" />
                          {stat.trend} this month
                        </p>
                      )}
                    </CardContent>
                  </Card>
                );
              })}
            </div>

            {/* Content Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Recent Activity */}
              <Card className="border-slate-100 shadow-soft">
                <CardHeader className="pb-4">
                  <CardTitle className="font-heading text-lg flex items-center gap-2">
                    <Clock className="w-5 h-5 text-slate-500" />
                    Recent Activity
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {activity.length === 0 ? (
                    <p className="text-sm text-slate-600 text-center py-8">No recent activity</p>
                  ) : (
                    <div className="space-y-4">
                      {activity.map((item, index) => (
                        <div key={index} className="flex items-start gap-3">
                          <div className={`p-2 rounded-lg ${getActivityColor(item.type)}`}>
                            {getActivityIcon(item.type)}
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm text-slate-700">{item.message}</p>
                            <p className="text-xs text-slate-500">
                              {new Date(item.timestamp).toLocaleDateString()}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Open Jobs */}
              <Card className="border-slate-100 shadow-soft">
                <CardHeader className="pb-4 flex flex-row items-center justify-between">
                  <CardTitle className="font-heading text-lg flex items-center gap-2">
                    <Briefcase className="w-5 h-5 text-slate-500" />
                    Open Positions
                  </CardTitle>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => navigate('/jobs/new')}
                    className="text-indigo-600 hover:text-indigo-700"
                    data-testid="create-job-btn"
                  >
                    <Plus className="w-4 h-4 mr-1" />
                    New Job
                  </Button>
                </CardHeader>
                <CardContent>
                  {recentJobs.length === 0 ? (
                    <p className="text-sm text-slate-600 text-center py-8">No open positions</p>
                  ) : (
                    <div className="space-y-3">
                      {recentJobs.map((job) => (
                        <div 
                          key={job.id} 
                          onClick={() => navigate(`/jobs/${job.id}`)}
                          className="p-4 rounded-xl bg-slate-50 hover:bg-indigo-50 transition-colors cursor-pointer"
                        >
                          <div className="flex items-center justify-between">
                            <div>
                              <p className="font-medium text-slate-900">{job.title}</p>
                              <p className="text-sm text-slate-600">{job.location || 'Remote'}</p>
                            </div>
                            <span className={`badge-${job.status === 'open' ? 'success' : 'neutral'}`}>
                              {job.status}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
