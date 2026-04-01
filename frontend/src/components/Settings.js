import React, { useEffect, useState } from 'react';
import { api, useToast } from '../App';


// Known retailers for the quick-add buttons
const KNOWN_RETAILERS = [
  'Temu', 'Wish', 'AliExpress', 'Walmart', 'Amazon', 'Newegg',
  'Best Buy', 'Micro Center', 'B&H Photo', 'Adorama', 'Antonline',
];

function BlockedRetailers({ value, onChange }) {
  const blocked = value
    ? value.split(',').map(r => r.trim().toLowerCase()).filter(Boolean)
    : [];

  const toggle = (retailer) => {
    const lower = retailer.toLowerCase();
    const updated = blocked.includes(lower)
      ? blocked.filter(r => r !== lower)
      : [...blocked, lower];
    onChange(updated.join(','));
  };

  return (
    <div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
        {KNOWN_RETAILERS.map(r => {
          const isBlocked = blocked.includes(r.toLowerCase());
          return (
            <button
              key={r}
              onClick={() => toggle(r)}
              style={{
                padding: '4px 12px', borderRadius: 6, fontSize: 12,
                fontWeight: 500, cursor: 'pointer', border: 'none',
                background: isBlocked
                  ? 'rgba(242,68,5,0.15)' : 'rgba(34,186,187,0.1)',
                color: isBlocked ? '#ff9a7a' : 'var(--teal-mid)',
                outline: isBlocked
                  ? '1px solid rgba(242,68,5,0.3)' : '1px solid rgba(34,186,187,0.2)',
                transition: 'all 0.15s',
              }}
            >
              {isBlocked ? '✕ ' : '+ '}{r}
            </button>
          );
        })}
      </div>
      <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 6 }}>
        Custom (comma-separated):
      </div>
      <input
        className="form-input"
        placeholder="e.g. temu,wish,aliexpress"
        value={value}
        onChange={e => onChange(e.target.value)}
      />
      {blocked.length > 0 && (
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 6 }}>
          Currently blocking: {blocked.join(', ')}
        </div>
      )}
    </div>
  );
}

export default function Settings() {
  const [form, setForm] = useState({
    discord_webhook: '',
    email_from: '', email_to: '',
    email_password: '',
    email_smtp_host: 'smtp.gmail.com',
    email_smtp_port: 587,
    check_interval_minutes: 120,
    total_budget: 0,
    pricesapi_key: '',
    slickdeals_enabled: 1,
    blocked_retailers: 'temu,wish,aliexpress',
  });
  const [hasApiKey, setHasApiKey]         = useState(false);
  const [hasEmailPw, setHasEmailPw]       = useState(false);
  const showToast = useToast();
  const [testing, setTesting]             = useState(false);
  const [testResult, setTestResult]       = useState(null);
  const [quota, setQuota]                 = useState(null);

  useEffect(() => {
    api('/settings').then(s => {
      if (!s || !Object.keys(s).length) return;
      setHasApiKey(!!s.has_pricesapi_key);
      setHasEmailPw(!!s.has_email_password);
      // Don't overwrite secret fields with empty string from server
      setForm(f => ({
        ...f,
        discord_webhook:        s.discord_webhook        ?? f.discord_webhook,
        email_from:             s.email_from             ?? f.email_from,
        email_to:               s.email_to               ?? f.email_to,
        email_smtp_host:        s.email_smtp_host        ?? f.email_smtp_host,
        email_smtp_port:        s.email_smtp_port        ?? f.email_smtp_port,
        check_interval_minutes: s.check_interval_minutes ?? f.check_interval_minutes,
        total_budget:           s.total_budget           ?? f.total_budget,
        slickdeals_enabled:     s.slickdeals_enabled     ?? f.slickdeals_enabled,
        blocked_retailers:      s.blocked_retailers      ?? f.blocked_retailers,
        // leave pricesapi_key and email_password blank — user must re-enter to change
      }));
    });
    api('/quota').then(setQuota).catch(() => {});
  }, []);

  const field = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const save = async () => {
    try {
      const res = await api('/settings', {
        method: 'POST',
        body: JSON.stringify(form),
      });
      if (res && res.ok) {
        if (form.pricesapi_key) setHasApiKey(true);
        if (form.email_password) setHasEmailPw(true);
        setForm(f => ({ ...f, pricesapi_key: '', email_password: '' }));
        api('/quota').then(setQuota).catch(() => {});
        showToast('Settings saved!');
      } else {
        showToast('Save failed — check logs', 'error');
      }
    } catch (e) {
      showToast(`Error: ${e.message}`, 'error');
    }
  };

  const testDiscord = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await api('/settings/test-discord', { method: 'POST' });
      const ok = res && res.ok;
      setTestResult(ok ? 'success' : 'error');
      showToast(ok ? 'Test message sent to Discord!' : 'Discord test failed', ok ? 'success' : 'error');
    } catch {
      setTestResult('error');
      showToast('Discord test failed', 'error');
    }
    setTesting(false);
  };

  const quotaColor = quota
    ? quota.headroom_percent > 30 ? '#34d399'
      : quota.headroom_percent > 10 ? '#fbbf24'
      : '#f87171'
    : '#64748b';

  return (
    <div style={{ maxWidth: 640 }}>

      {/* Price sources */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="section-title">Price sources</div>

        <div className="form-group" style={{ marginBottom: 16 }}>
          <label className="form-label">
            PricesAPI.io key
            {hasApiKey && (
              <span style={{ marginLeft: 8, fontSize: 11, color: '#34d399', fontWeight: 400 }}>
                ✓ key saved
              </span>
            )}
          </label>
          <input
            className="form-input"
            type="password"
            placeholder={hasApiKey ? '••••••••  (leave blank to keep existing)' : 'Paste your API key from pricesapi.io'}
            value={form.pricesapi_key}
            onChange={e => field('pricesapi_key', e.target.value)}
          />
          <div style={{ fontSize: 12, color: '#64748b', marginTop: 4, lineHeight: 1.6 }}>
            Free tier: 1,000 calls/month · Covers Amazon, Newegg, Best Buy, B&H
          </div>
        </div>

        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '12px 0', borderTop: '1px solid #1e2536',
        }}>
          <div>
            <div style={{ fontSize: 13, color: '#e2e8f0', fontWeight: 500 }}>SlickDeals RSS</div>
            <div style={{ fontSize: 12, color: '#64748b', marginTop: 2 }}>
              Free community deal alerts — no API calls used
            </div>
          </div>
          <button
            onClick={() => field('slickdeals_enabled', form.slickdeals_enabled ? 0 : 1)}
            style={{
              width: 44, height: 24, borderRadius: 12, border: 'none', cursor: 'pointer',
              background: form.slickdeals_enabled ? '#2563eb' : '#2d3748',
              position: 'relative', transition: 'background 0.2s', flexShrink: 0,
            }}
          >
            <div style={{
              width: 18, height: 18, borderRadius: '50%', background: '#fff',
              position: 'absolute', top: 3,
              left: form.slickdeals_enabled ? 23 : 3,
              transition: 'left 0.2s',
            }} />
          </button>
        </div>
      </div>

      {/* Quota advisor */}
      {quota && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="section-title">API quota advisor</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10, marginBottom: 12 }}>
            <div className="stat-card" style={{ padding: 12 }}>
              <div className="stat-label">Parts tracked</div>
              <div className="stat-value blue" style={{ fontSize: 20 }}>{quota.part_count}</div>
            </div>
            <div className="stat-card" style={{ padding: 12 }}>
              <div className="stat-label">Est. calls/month</div>
              <div className="stat-value" style={{ fontSize: 20, color: quotaColor }}>
                {quota.estimated_calls_per_month}
                <span style={{ fontSize: 11, color: '#64748b' }}>/1000</span>
              </div>
            </div>
            <div className="stat-card" style={{ padding: 12 }}>
              <div className="stat-label">Headroom</div>
              <div className="stat-value" style={{ fontSize: 20, color: quotaColor }}>
                {quota.headroom_percent}%
              </div>
            </div>
          </div>
          <div style={{ fontSize: 12, color: '#64748b', lineHeight: 1.7 }}>
            Recommended for {quota.part_count} part{quota.part_count !== 1 ? 's' : ''}:{' '}
            <span style={{ color: '#e2e8f0', fontWeight: 500 }}>
              every {quota.recommended_interval_minutes} min
            </span>
            {form.check_interval_minutes < quota.recommended_interval_minutes && (
              <span style={{ color: '#fbbf24' }}>
                {' '}— your current {form.check_interval_minutes}min interval may exceed quota.
              </span>
            )}
          </div>
        </div>
      )}

      {/* Tracking */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="section-title">Tracking settings</div>
        <div className="form-row">
          <div className="form-group">
            <label className="form-label">Check interval</label>
            <select className="form-input" value={form.check_interval_minutes}
              onChange={e => field('check_interval_minutes', parseInt(e.target.value))}>
              <option value={30}>Every 30 minutes</option>
              <option value={60}>Every hour</option>
              <option value={120}>Every 2 hours</option>
              <option value={180}>Every 3 hours</option>
              <option value={360}>Every 6 hours</option>
              <option value={720}>Every 12 hours</option>
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Total build budget ($)</label>
            <input className="form-input" type="number" placeholder="2000"
              value={form.total_budget}
              onChange={e => field('total_budget', parseFloat(e.target.value) || 0)} />
          </div>
        </div>
      </div>

      {/* Discord */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="section-title">Discord notifications</div>
        <div className="form-group" style={{ marginBottom: 8 }}>
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
            <div style={{ fontSize: 12, color: '#34d399', marginTop: 4 }}>Sent! Check your Discord channel.</div>
          )}
          {testResult === 'error' && (
            <div style={{ fontSize: 12, color: '#f87171', marginTop: 4 }}>Failed — save first, then test.</div>
          )}
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
            <label className="form-label">
              App password
              {hasEmailPw && (
                <span style={{ marginLeft: 8, fontSize: 11, color: '#34d399', fontWeight: 400 }}>
                  ✓ saved
                </span>
              )}
            </label>
            <input className="form-input" type="password"
              placeholder={hasEmailPw ? '••••••••  (leave blank to keep existing)' : 'Gmail app password'}
              value={form.email_password}
              onChange={e => field('email_password', e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label">SMTP host</label>
            <input className="form-input" placeholder="smtp.gmail.com"
              value={form.email_smtp_host} onChange={e => field('email_smtp_host', e.target.value)} />
          </div>
        </div>
        <div style={{ fontSize: 12, color: '#64748b', lineHeight: 1.6 }}>
          Gmail users: generate an App Password at myaccount.google.com/apppasswords
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="section-title">Blocked retailers</div>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12, lineHeight: 1.6 }}>
          Prices from these retailers will be ignored and removed from history. Comma-separated, case-insensitive.
        </p>
        <BlockedRetailers
          value={form.blocked_retailers}
          onChange={v => field('blocked_retailers', v)}
        />
      </div>

      <button className="btn btn-primary" onClick={save}>Save settings</button>

    </div>
  );
}
