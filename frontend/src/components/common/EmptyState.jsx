import React from 'react';
import { Button } from '../ui/button';

export const EmptyState = ({ 
  icon: Icon, 
  title, 
  description, 
  actionLabel, 
  onAction,
  className = ''
}) => {
  return (
    <div className={`flex flex-col items-center justify-center py-16 px-8 text-center ${className}`}>
      {Icon && (
        <div className="w-16 h-16 rounded-2xl bg-indigo-50 flex items-center justify-center mb-6">
          <Icon className="w-8 h-8 text-indigo-500" />
        </div>
      )}
      <h3 className="font-heading font-semibold text-lg text-slate-900 mb-2">{title}</h3>
      <p className="text-slate-600 text-sm max-w-sm mb-6">{description}</p>
      {actionLabel && onAction && (
        <Button 
          onClick={onAction}
          className="bg-indigo-500 hover:bg-indigo-600 text-white rounded-full px-6"
        >
          {actionLabel}
        </Button>
      )}
    </div>
  );
};
