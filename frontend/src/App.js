import React, { useState, useCallback, createContext, useContext } from 'react';
import Dashboard from './components/Dashboard';
import Parts from './components/Parts';
import Settings from './components/Settings';
import Toast from './components/Toast';
import './App.css';

const API = '/api';

export function api(path, opts = {}) {
  return fetch(API + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  }).then(r => r.json());
}

export const ToastContext = createContext(() => {});
export function useToast() { return useContext(ToastContext); }

export default function App() {
  const [tab, setTab]           = useState('dashboard');
  const [checking, setChecking] = useState(false);
  const [lastChecked, setLastChecked] = useState(null);
  const [toast, setToast]       = useState(null);

  const showToast = useCallback((message, type = 'success') => {
    setToast({ message, type, key: Date.now() });
  }, []);

  const triggerCheck = async () => {
    setChecking(true);
    try {
      await api('/check', { method: 'POST' });
      setTimeout(() => {
        setChecking(false);
        setLastChecked(new Date().toLocaleTimeString());
        showToast('Price check started');
      }, 1000);
    } catch {
      setChecking(false);
      showToast('Price check failed', 'error');
    }
  };

  const tabs = [
    { id: 'dashboard', label: 'Dashboard' },
    { id: 'parts',     label: 'Parts List' },
    { id: 'settings',  label: 'Settings' },
  ];

  return (
    <ToastContext.Provider value={showToast}>
      <div className="app">
        <header className="header">
          <div className="header-left">
            <div className="logo">
              <span className="logo-icon">⚙</span>
              <span className="logo-text">PC Build Tracker</span>
            </div>
            <nav className="nav">
              {tabs.map(t => (
                <button
                  key={t.id}
                  className={`nav-btn ${tab === t.id ? 'active' : ''}`}
                  onClick={() => setTab(t.id)}
                >
                  {t.label}
                </button>
              ))}
            </nav>
          </div>
          <div className="header-right">
            {lastChecked && (
              <span className="last-checked">Last checked {lastChecked}</span>
            )}
            <button
              className={`check-btn ${checking ? 'checking' : ''}`}
              onClick={triggerCheck}
              disabled={checking}
            >
              {checking ? 'Checking...' : 'Check Prices Now'}
            </button>
          </div>
        </header>

        <main className="main">
          {tab === 'dashboard' && <Dashboard />}
          {tab === 'parts'     && <Parts />}
          {tab === 'settings'  && <Settings />}
        </main>

        {toast && (
          <Toast
            key={toast.key}
            message={toast.message}
            type={toast.type}
            onClose={() => setToast(null)}
          />
        )}
      </div>
    </ToastContext.Provider>
  );
}
