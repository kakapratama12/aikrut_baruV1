import React, { useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { Avatar, AvatarFallback } from '../ui/avatar';
import { Bell, Coins } from 'lucide-react';

export const TopBar = ({ title, subtitle }) => {
  const { user, refreshUser } = useAuth();

  // Refresh user data when component mounts (page navigation)
  useEffect(() => {
    refreshUser();
  }, []);

  const initials = user?.name
    ? user.name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
    : 'U';

  return (
    <header className="h-16 bg-white border-b border-slate-100 flex items-center justify-between px-8 sticky top-0 z-30" data-testid="topbar">
      <div>
        <h1 className="font-heading font-semibold text-xl text-slate-900">{title}</h1>
        {subtitle && <p className="text-sm text-slate-600">{subtitle}</p>}
      </div>

      <div className="flex items-center gap-4">
        {/* Credit Balance - Clean display without spinning icon */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-gradient-to-r from-indigo-50 to-purple-50 border border-indigo-100">
          <Coins className="w-4 h-4 text-indigo-600" />
          <span className="text-sm font-semibold text-indigo-900">
            {user?.credits !== undefined ? user.credits.toFixed(2) : '0.00'}
          </span>
          <span className="text-xs text-indigo-600">credits</span>
        </div>

        <button
          className="p-2 rounded-full hover:bg-slate-100 transition-colors relative"
          data-testid="notifications-btn"
        >
          <Bell className="w-5 h-5 text-slate-600" />
        </button>

        <div className="flex items-center gap-3">
          <Avatar className="h-9 w-9">
            <AvatarFallback className="bg-indigo-100 text-indigo-600 text-sm font-medium">
              {initials}
            </AvatarFallback>
          </Avatar>
          <div className="hidden sm:block">
            <p className="text-sm font-medium text-slate-900">{user?.name}</p>
            <p className="text-xs text-slate-600">{user?.email}</p>
          </div>
        </div>
      </div>
    </header>
  );
};
