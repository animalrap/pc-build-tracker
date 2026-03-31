import React, { useEffect, useState } from 'react';
import { api } from '../App';

export default function Settings() {
  const [form, setForm] = useState({
    discord_webhook: '', email_from: '', email_to: '',
    email_password: '', email_smtp_host: 'smtp.gmail.com',
    email_smtp_port: 587, check_interval_minutes: 60, total_budget: 0,
  });
  const [saved, setSaved] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);

  useEffect(() => {
    api('/settings').then(s => {
      if (Object.keys(s).length) setForm(f => ({ ...f, ...s }));
    });
  }, []);

  const field = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const save = async () => {
    await api('/settings', { method: 'POST', body: JSON.stringify(form) });
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  const testDiscord = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      await api('/settings/test-discord', { method: 'POST' });
      setTestResult('success');
    } catch {
      setTestResult('error');
    }
    setTesting(false);
  };

  return (
    <div style={{ maxWidth: 640 }}>

      {/* Notifications */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="section-title">Discord notifications</div>

        <div className="form-group" style={{ marginBottom: 12 }}>
          <label className="form-label">Webhook URL</label>
          <div style={{ display: 'flex', gap: 8 }}>
            <input className="form-input" style={{ flex: 1 }}
              placeholder="https://discord.com/api/webhooks/..."
              value={form.discord_webhook}
              onChange={e => field('discord_webhook', e.target.value)} />
            <button className="btn btn-secondary" onClick={testDiscord} disabled={testing}>
              {testing ? 'Sending...' : 'Test'}
            </button>
          </div>
          {testResult === 'success' && (
            <div style={{ fontSize: 12, color: '#34d399', marginTop: 4 }}>Test message sent successfully!</div>
          )}
          {testResult === 'error' && (
            <div style={{ fontSize: 12, color: '#f87171', marginTop: 4 }}>Failed — check your webhook URL and save first.</div>
          )}
        </div>

        <div style={{ fontSize: 12, color: '#64748b', lineHeight: 1.6 }}>
          Create a webhook in Discord: right-click any channel → Edit Channel → Integrations → Webhooks → New Webhook → Copy URL
        </div>
      </div>

      {/* Email */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="section-title">Email notifications</div>

        <div className="form-row">
          <div className="form-group">
            <label className="form-label">From address</label>
            <input className="form-input" type="email" placeholder="your@gmail.com"
              value={form.email_from} onChange={e => field('email_from', e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label">To address</label>
            <input className="form-input" type="email" placeholder="your@gmail.com"
              value={form.email_to} onChange={e => field('email_to', e.target.value)} />
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label className="form-label">App password</label>
            <input className="form-input" type="password" placeholder="Gmail app password"
              value={form.email_password} onChange={e => field('email_password', e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label">SMTP host</label>
            <input className="form-input" placeholder="smtp.gmail.com"
              value={form.email_smtp_host} onChange={e => field('email_smtp_host', e.target.value)} />
          </div>
        </div>

        <div style={{ fontSize: 12, color: '#64748b', lineHeight: 1.6 }}>
          For Gmail, generate an App Password at <span style={{ color: '#60a5fa' }}>myaccount.google.com/apppasswords</span>.
          Do not use your regular Gmail password.
        </div>
      </div>

      {/* Tracking */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="section-title">Tracking settings</div>

        <div className="form-row">
          <div className="form-group">
            <label className="form-label">Check interval (minutes)</label>
            <select className="form-input" value={form.check_interval_minutes}
              onChange={e => field('check_interval_minutes', parseInt(e.target.value))}>
              <option value={30}>Every 30 minutes</option>
              <option value={60}>Every hour</option>
              <option value={120}>Every 2 hours</option>
              <option value={360}>Every 6 hours</option>
              <option value={720}>Every 12 hours</option>
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Total build budget ($)</label>
            <input className="form-input" type="number" placeholder="2000"
              value={form.total_budget} onChange={e => field('total_budget', parseFloat(e.target.value))} />
          </div>
        </div>

        <div style={{ fontSize: 12, color: '#64748b', lineHeight: 1.6 }}>
          A shorter interval means faster alerts but more requests. 60 minutes is recommended to be polite to retailers.
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <button className="btn btn-primary" onClick={save}>Save settings</button>
        {saved && <span style={{ fontSize: 13, color: '#34d399' }}>Settings saved!</span>}
      </div>
    </div>
  );
}
