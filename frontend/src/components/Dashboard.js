import React, { useEffect, useState } from 'react';
import { api } from '../App';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [parts, setParts] = useState([]);
  const [bestPrices, setBestPrices] = useState({});
  const [selectedPart, setSelectedPart] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api('/summary'),
      api('/parts'),
    ]).then(([s, p]) => {
      setSummary(s);
      setParts(p);
      // fetch best price for each part
      Promise.all(p.map(part =>
        api(`/parts/${part.id}/best-price`).then(bp => ({ id: part.id, bp }))
      )).then(results => {
        const map = {};
        results.forEach(r => { map[r.id] = r.bp; });
        setBestPrices(map);
        setLoading(false);
      });
    });
  }, []);

  const loadHistory = (part) => {
    setSelectedPart(part);
    api(`/parts/${part.id}/history?days=30`).then(h => {
      // Group by date for chart
      const byDate = {};
      h.forEach(row => {
        const date = row.checked_at.split('T')[0].split(' ')[0];
        if (!byDate[date] || row.price < byDate[date]) {
          byDate[date] = row.price;
        }
      });
      const chartData = Object.entries(byDate)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([date, price]) => ({ date, price }));
      setHistory(chartData);
    });
  };

  const savings = summary
    ? summary.total_target - summary.total_best_prices
    : 0;

  const CATEGORIES = ['Motherboard', 'CPU', 'GPU', 'RAM', 'Storage', 'Case', 'PSU', 'Cooling', 'Other'];

  const grouped = CATEGORIES.reduce((acc, cat) => {
    const catParts = parts.filter(p => p.category === cat);
    if (catParts.length) acc[cat] = catParts;
    return acc;
  }, {});

  if (loading) return <div className="loading">Loading dashboard...</div>;

  return (
    <div>
      {/* Summary stats */}
      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-label">Parts tracked</div>
          <div className="stat-value blue">{summary?.part_count || 0}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Target build cost</div>
          <div className="stat-value">${summary?.total_target?.toFixed(2) || '0.00'}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Best prices found</div>
          <div className="stat-value green">${summary?.total_best_prices?.toFixed(2) || '0.00'}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Savings vs target</div>
          <div className={`stat-value ${savings > 0 ? 'green' : 'red'}`}>
            {savings >= 0 ? '+' : ''}{savings.toFixed(2) !== '0.00' ? `$${Math.abs(savings).toFixed(2)}` : '—'}
          </div>
        </div>
        {summary?.budget > 0 && (
          <div className="stat-card">
            <div className="stat-label">Budget remaining</div>
            <div className={`stat-value ${summary.budget_remaining >= 0 ? 'green' : 'red'}`}>
              ${Math.abs(summary.budget_remaining).toFixed(2)}
              {summary.budget_remaining < 0 ? ' over' : ' left'}
            </div>
            <div className="stat-sub">of ${summary.budget.toFixed(2)} budget</div>
          </div>
        )}
      </div>

      {/* Parts by category */}
      {Object.keys(grouped).length === 0 ? (
        <div className="card">
          <div className="empty">
            <div className="empty-icon">🔧</div>
            <div className="empty-text">No parts added yet. Go to Parts List to start tracking.</div>
          </div>
        </div>
      ) : (
        Object.entries(grouped).map(([cat, catParts]) => (
          <div key={cat} className="card" style={{ marginBottom: 16 }}>
            <div className="section-title">{cat}</div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Part</th>
                    <th>Target</th>
                    <th>Best Price</th>
                    <th>Retailer</th>
                    <th>Status</th>
                    <th>History</th>
                  </tr>
                </thead>
                <tbody>
                  {catParts.map(part => {
                    const bp = bestPrices[part.id];
                    const isDeal = bp && bp.price < part.target_price;
                    return (
                      <tr key={part.id} className={isDeal ? 'deal-row' : ''}>
                        <td style={{ color: '#f1f5f9', fontWeight: 500 }}>{part.name}</td>
                        <td className="target-price">${part.target_price.toFixed(2)}</td>
                        <td className={isDeal ? 'deal-price' : ''}>
                          {bp?.price ? `$${bp.price.toFixed(2)}` : '—'}
                        </td>
                        <td>{bp?.retailer || '—'}</td>
                        <td>
                          {!bp ? (
                            <span className="badge gray">No data</span>
                          ) : isDeal ? (
                            <span className="badge green">Deal!</span>
                          ) : (
                            <span className="badge blue">Watching</span>
                          )}
                        </td>
                        <td>
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={() => loadHistory(part)}
                          >
                            View chart
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        ))
      )}

      {/* Price history modal */}
      {selectedPart && (
        <div className="modal-overlay" onClick={() => setSelectedPart(null)}>
          <div className="modal" style={{ width: 600 }} onClick={e => e.stopPropagation()}>
            <div className="modal-title">Price history — {selectedPart.name}</div>
            {history.length === 0 ? (
              <div className="empty">
                <div className="empty-text">No price history yet. Run a price check first.</div>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={history}>
                  <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 11 }} />
                  <YAxis
                    domain={['auto', 'auto']}
                    tick={{ fill: '#64748b', fontSize: 11 }}
                    tickFormatter={v => `$${v}`}
                  />
                  <Tooltip
                    formatter={v => [`$${v.toFixed(2)}`, 'Price']}
                    contentStyle={{ background: '#1a2035', border: '1px solid #2d3748', borderRadius: 6 }}
                    labelStyle={{ color: '#94a3b8' }}
                  />
                  <ReferenceLine
                    y={selectedPart.target_price}
                    stroke="#f59e0b"
                    strokeDasharray="4 4"
                    label={{ value: 'Target', fill: '#f59e0b', fontSize: 11 }}
                  />
                  <Line
                    type="monotone" dataKey="price"
                    stroke="#60a5fa" strokeWidth={2}
                    dot={{ fill: '#60a5fa', r: 3 }}
                    activeDot={{ r: 5 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setSelectedPart(null)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
