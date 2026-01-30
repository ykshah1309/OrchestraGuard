/**
 * MetricsCard Component - Reusable Metric Display Card
 */
import React from 'react';

const MetricsCard = ({ 
  title, 
  value, 
  icon, 
  subtitle, 
  trend,
  color = 'blue',
  onClick 
}) => {
  const colorClasses = {
    blue: {
      bg: 'bg-blue-50',
      border: 'border-blue-100',
      text: 'text-blue-600',
      hover: 'hover:border-blue-300 hover:shadow-blue-100'
    },
    green: {
      bg: 'bg-green-50',
      border: 'border-green-100',
      text: 'text-green-600',
      hover: 'hover:border-green-300 hover:shadow-green-100'
    },
    red: {
      bg: 'bg-red-50',
      border: 'border-red-100',
      text: 'text-red-600',
      hover: 'hover:border-red-300 hover:shadow-red-100'
    },
    yellow: {
      bg: 'bg-yellow-50',
      border: 'border-yellow-100',
      text: 'text-yellow-600',
      hover: 'hover:border-yellow-300 hover:shadow-yellow-100'
    },
    purple: {
      bg: 'bg-purple-50',
      border: 'border-purple-100',
      text: 'text-purple-600',
      hover: 'hover:border-purple-300 hover:shadow-purple-100'
    },
    gray: {
      bg: 'bg-gray-50',
      border: 'border-gray-100',
      text: 'text-gray-600',
      hover: 'hover:border-gray-300 hover:shadow-gray-100'
    }
  };

  const colors = colorClasses[color] || colorClasses.blue;

  const renderTrend = (trendValue) => {
    if (!trendValue) return null;
    
    const isPositive = trendValue.startsWith('+');
    const trendClass = isPositive ? 'text-green-600' : 'text-red-600';
    const trendIcon = isPositive ? '↗' : '↘';
    
    return (
      <div className={`flex items-center text-sm ${trendClass}`}>
        <span className="mr-1">{trendIcon}</span>
        <span>{trendValue}</span>
      </div>
    );
  };

  return (
    <div
      className={`
        ${colors.bg} ${colors.border} border rounded-xl p-6
        transition-all duration-300 ${onClick ? 'cursor-pointer hover:shadow-lg ' + colors.hover : ''}
      `}
      onClick={onClick}
    >
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center space-x-3 mb-4">
            <div className={`${colors.text} p-2 rounded-lg bg-white`}>
              {icon}
            </div>
            {trend && <div className="ml-auto">{renderTrend(trend)}</div>}
          </div>
          
          <div className="mb-2">
            <p className="text-sm font-medium text-gray-600">{title}</p>
            <p className="text-3xl font-bold text-gray-900 mt-1">{value}</p>
          </div>
          
          {subtitle && (
            <p className="text-sm text-gray-600">{subtitle}</p>
          )}
        </div>
      </div>
      
      {/* Progress bar for percentage values */}
      {typeof value === 'string' && value.includes('%') && !isNaN(parseFloat(value)) && (
        <div className="mt-4">
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div 
              className={`h-2 rounded-full ${colors.bg.replace('50', '500').replace('bg-', 'bg-')}`}
              style={{ width: value }}
            ></div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MetricsCard;