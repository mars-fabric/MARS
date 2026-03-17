// components/common/ConnectionStatus.tsx

import { Wifi, WifiOff, RefreshCw } from 'lucide-react';

interface ConnectionStatusProps {
  connected: boolean;
  reconnectAttempt: number;
  lastError: string | null;
  onReconnect?: () => void;
}

export function ConnectionStatus({
  connected,
  reconnectAttempt,
  lastError,
  onReconnect,
}: ConnectionStatusProps) {
  if (connected) {
    return (
      <div className="flex items-center space-x-2 text-green-400">
        <Wifi className="w-4 h-4" />
        <span className="text-xs">Connected</span>
      </div>
    );
  }

  if (reconnectAttempt > 0) {
    return (
      <div className="flex items-center space-x-2 text-yellow-400">
        <RefreshCw className="w-4 h-4 animate-spin" />
        <span className="text-xs">
          Reconnecting... (attempt {reconnectAttempt})
        </span>
      </div>
    );
  }

  return (
    <div className="flex items-center space-x-2 text-red-400">
      <WifiOff className="w-4 h-4" />
      <span className="text-xs">Disconnected</span>
      {lastError && (
        <span className="text-xs text-gray-400">({lastError})</span>
      )}
      {onReconnect && (
        <button
          onClick={onReconnect}
          className="px-2 py-0.5 text-xs bg-red-500/20 hover:bg-red-500/30 rounded"
        >
          Retry
        </button>
      )}
    </div>
  );
}
