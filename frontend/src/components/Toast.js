import React, { useEffect } from 'react';

export default function Toast({ message, type = 'success', onClose }) {
  useEffect(() => {
    const t = setTimeout(onClose, 3500);
    return () => clearTimeout(t);
  }, [onClose]);

  return (
    <div className={`toast ${type}`}>
      <span className="toast-icon">{type === 'success' ? '✓' : '✕'}</span>
      <span>{message}</span>
    </div>
  );
}
