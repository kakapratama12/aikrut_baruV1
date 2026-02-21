import React from 'react';
import { cn } from '../../lib/utils';

export const ScoreRing = ({ score, size = 60, strokeWidth = 6, className }) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (score / 100) * circumference;
  
  const getColor = (score) => {
    if (score >= 80) return { stroke: '#22c55e', bg: '#dcfce7', text: '#166534' };
    if (score >= 60) return { stroke: '#eab308', bg: '#fef9c3', text: '#854d0e' };
    if (score >= 40) return { stroke: '#f97316', bg: '#ffedd5', text: '#9a3412' };
    return { stroke: '#ef4444', bg: '#fee2e2', text: '#991b1b' };
  };
  
  const colors = getColor(score);

  return (
    <div className={cn('relative inline-flex items-center justify-center', className)}>
      <svg width={size} height={size} className="transform -rotate-90">
        {/* Background circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#e2e8f0"
          strokeWidth={strokeWidth}
        />
        {/* Progress circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={colors.stroke}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-500 ease-out"
        />
      </svg>
      <span 
        className="absolute font-semibold text-sm"
        style={{ color: colors.text }}
      >
        {Math.round(score)}
      </span>
    </div>
  );
};

export const ScoreBadge = ({ score, showLabel = true }) => {
  const getScoreClass = (score) => {
    if (score >= 80) return 'badge-success';
    if (score >= 60) return 'badge-warning';
    return 'badge-error';
  };
  
  const getLabel = (score) => {
    if (score >= 80) return 'Excellent';
    if (score >= 60) return 'Good';
    if (score >= 40) return 'Fair';
    return 'Poor';
  };

  return (
    <span className={getScoreClass(score)}>
      {Math.round(score)}{showLabel && ` - ${getLabel(score)}`}
    </span>
  );
};
