// src/components/LoadingScreen.jsx
import React from 'react';
import { Loader2 } from 'lucide-react';

const LoadingScreen = ({ message = 'Yüklənir...' }) => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-900 via-purple-900 to-indigo-900 flex items-center justify-center">
      <div className="text-center">
        <Loader2 className="w-12 h-12 text-white animate-spin mx-auto mb-4" />
        <p className="text-white text-lg">{message}</p>
      </div>
    </div>
  );
};

export default LoadingScreen;