import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Clock, Mail, Shield } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export const PendingApproval = () => {
  const navigate = useNavigate();
  const { logout } = useAuth();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-indigo-50 flex items-center justify-center p-4">
      <Card className="max-w-md w-full border-slate-100 shadow-soft-lg">
        <CardHeader className="text-center pb-4">
          <div className="w-16 h-16 rounded-full bg-orange-100 flex items-center justify-center mx-auto mb-4">
            <Clock className="w-8 h-8 text-orange-600" />
          </div>
          <CardTitle className="font-heading text-2xl">Account Pending Approval</CardTitle>
          <CardDescription>Your registration is being reviewed</CardDescription>
        </CardHeader>
        
        <CardContent className="space-y-4">
          <div className="p-4 rounded-lg bg-blue-50 border border-blue-100">
            <div className="flex items-start gap-3">
              <Shield className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-blue-900">
                <p className="font-medium mb-2">Thank you for registering!</p>
                <p className="text-blue-700">
                  Your account is currently awaiting administrator approval. 
                  This is a security measure to ensure platform integrity.
                </p>
              </div>
            </div>
          </div>

          <div className="p-4 rounded-lg bg-slate-50 border border-slate-200">
            <div className="flex items-start gap-3">
              <Mail className="w-5 h-5 text-slate-600 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-slate-700">
                <p className="font-medium mb-1">What happens next?</p>
                <ul className="list-disc list-inside space-y-1 text-slate-600">
                  <li>Our admin team will review your registration</li>
                  <li>Approval typically takes 24-48 hours</li>
                </ul>
              </div>
            </div>
          </div>

          <div className="pt-4 space-y-3">
            <p className="text-sm text-center text-slate-600">
              Need immediate access? Contact our admin team at:
              <br />
              <a href="mailto:admin@widyaanalytic.org" className="text-indigo-600 hover:underline font-medium">
                admin@widyaanalytic.org
              </a>
              <br />
              <p>or</p>
              <a 
                href="https://wa.me/6281225056948" 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-indigo-600 hover:underline font-medium"
              >
                Contact by WhatsApp
              </a>
            </p>

            <Button
              onClick={handleLogout}
              variant="outline"
              className="w-full border-slate-300 hover:bg-slate-100"
            >
              Back to Login
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
