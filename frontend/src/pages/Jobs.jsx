import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { TopBar } from '../components/layout/TopBar';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { jobsAPI } from '../lib/api';
import { Briefcase, Plus, MapPin, Clock, ChevronRight } from 'lucide-react';
import { EmptyState } from '../components/common/EmptyState';

export const Jobs = () => {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    loadJobs();
  }, []);

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

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-pulse text-indigo-500">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen" data-testid="jobs-page">
      <TopBar title="Job Vacancies" subtitle="Manage open positions" />
      
      <div className="p-8">
        <div className="flex justify-between items-center mb-6">
          <div>
            <p className="text-slate-500">{jobs.length} position{jobs.length !== 1 ? 's' : ''}</p>
          </div>
          <Button
            onClick={() => navigate('/jobs/new')}
            className="bg-indigo-500 hover:bg-indigo-600 text-white rounded-full"
            data-testid="create-job-btn"
          >
            <Plus className="w-4 h-4 mr-2" />
            Create Job
          </Button>
        </div>

        {jobs.length === 0 ? (
          <Card className="border-slate-100 shadow-soft">
            <EmptyState
              icon={Briefcase}
              title="No job vacancies yet"
              description="Create your first job posting to start screening candidates."
              actionLabel="Create Job"
              onAction={() => navigate('/jobs/new')}
            />
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {jobs.map((job, index) => (
              <Card
                key={job.id}
                className="border-slate-100 shadow-soft hover:shadow-soft-md hover:border-indigo-200 transition-all cursor-pointer animate-slide-up"
                style={{ animationDelay: `${index * 0.05}s` }}
                onClick={() => navigate(`/jobs/${job.id}`)}
                data-testid={`job-card-${job.id}`}
              >
                <CardContent className="p-6">
                  <div className="flex items-start justify-between mb-4">
                    <div className="w-12 h-12 rounded-xl bg-indigo-50 flex items-center justify-center">
                      <Briefcase className="w-6 h-6 text-indigo-500" />
                    </div>
                    <span className={`badge-${job.status === 'open' ? 'success' : 'neutral'}`}>
                      {job.status}
                    </span>
                  </div>
                  
                  <h3 className="font-heading font-semibold text-lg text-slate-900 mb-2">
                    {job.title}
                  </h3>
                  
                  <div className="space-y-2 mb-4">
                    {job.location && (
                      <div className="flex items-center gap-2 text-sm text-slate-500">
                        <MapPin className="w-4 h-4" />
                        {job.location}
                      </div>
                    )}
                    <div className="flex items-center gap-2 text-sm text-slate-500">
                      <Clock className="w-4 h-4" />
                      {job.employment_type}
                    </div>
                  </div>
                  
                  <div className="flex items-center justify-between pt-4 border-t border-slate-100">
                    <span className={`text-xs ${job.playbook ? 'text-green-600' : 'text-amber-600'}`}>
                      {job.playbook ? '✓ Playbook ready' : '! Needs playbook'}
                    </span>
                    <ChevronRight className="w-4 h-4 text-slate-400" />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
