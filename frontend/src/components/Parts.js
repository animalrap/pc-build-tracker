import React, { useEffect, useState } from 'react';
import { api, useToast } from '../App';

const CATEGORIES = ['Motherboard', 'CPU', 'GPU', 'RAM', 'Storage', 'Case', 'PSU', 'Cooling', 'Other'];

const EMPTY_PART = {
  name: '', category: 'Motherboard', search_query: '', target_price: '', notes: '', required_keywords: ''
};

// Pre-filled suggestions for quick-add
const SUGGESTIONS = [
  { name: 'MSI MAG X870E Tomahawk WiFi', category: 'Motherboard', search_query: 'MSI MAG X870E Tomahawk WiFi motherboard AM5', target_price: 269, required_keywords: 'X870E' },
];

export default function Parts() {
  const [parts, setParts] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [editPart, setEditPart] = useState(null);
  const [form, setForm] = useState(EMPTY_PART);
  const [loading, setLoading] = useState(true);
  const [liveResults, setLiveResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const showToast = useToast();

  const load = () => {
    api('/parts').then(p => { setParts(p); setLoading(false); });
  };

  useEffect(() => { load(); }, []);

  const openAdd = (prefill = null) => {
    setForm(prefill || EMPTY_PART);
    setEditPart(null);
    setLiveResults([]);
    setShowModal(true);
  };

  const openEdit = (part) => {
    setForm({ ...part });
    setEditPart(part.id);
    setLiveResults([]);
    setShowModal(true);
  };

  const closeModal = () => {
    setShowModal(false);
    setEditPart(null);
    setForm(EMPTY_PART);
    setLiveResults([]);
  };

  const save = async () => {
    if (!form.name || !form.search_query || !form.target_price) return;
    if (editPart) {
      await api(`/parts/${editPart}`, { method: 'PUT', body: JSON.stringify(form) });
    } else {
      await api('/parts', { method: 'POST', body: JSON.stringify(form) });
    }
    load();
    closeModal();
    showToast(editPart ? 'Part updated!' : 'Part added!');
  };

  const deletePart = async (id) => {
    await api(`/parts/${id}`, { method: 'DELETE' });
    setDeleteConfirm(null);
    load();
    showToast('Part deleted', 'error');
  };

  const searchLive = async () => {
    if (!form.search_query) return;
    setSearching(true);
    const results = await api(`/prices/0?query=${encodeURIComponent(form.search_query)}`).catch(() => []);
    setLiveResults(Array.isArray(results) ? results : []);
    setSearching(false);
  };

  const field = (key, val) => setForm(f => ({ ...f, [key]: val }));

  if (loading) return <div className="loading">Loading parts...</div>;

  return (
    <div>
      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div className="section-title" style={{ margin: 0 }}>Parts List ({parts.length})</div>
        <button className="btn btn-primary" onClick={() => openAdd()}>+ Add Part</button>
      </div>

      {/* Quick-add suggestions */}
      {parts.length === 0 && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="section-title">Quick add</div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {SUGGESTIONS.map((s, i) => (
              <button key={i} className="btn btn-secondary" onClick={() => openAdd(s)}>
                + {s.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Parts table */}
      {parts.length === 0 ? (
        <div className="card">
          <div className="empty">
            <div className="empty-icon">📋</div>
            <div className="empty-text">No parts yet. Add your first part to start tracking prices.</div>
          </div>
        </div>
      ) : (
        <div className="card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Category</th>
                  <th>Target price</th>
                  <th>Search query</th>
                  <th>Notes</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {parts.map(part => (
                  <tr key={part.id}>
                    <td style={{ color: '#f1f5f9', fontWeight: 500 }}>{part.name}</td>
                    <td><span className="badge blue">{part.category}</span></td>
                    <td style={{ color: '#34d399' }}>${part.target_price.toFixed(2)}</td>
                    <td style={{ color: '#64748b', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {part.search_query}
                    </td>
                    <td style={{ color: '#64748b' }}>{part.notes || '—'}</td>
                    <td>
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button className="btn btn-secondary btn-sm" onClick={() => openEdit(part)}>Edit</button>
                        <button className="btn btn-danger btn-sm" onClick={() => setDeleteConfirm(part.id)}>Delete</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Add/Edit modal */}
      {showModal && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-title">{editPart ? 'Edit Part' : 'Add Part'}</div>

            <div className="form-row">
              <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                <label className="form-label">Part name</label>
                <input className="form-input" placeholder="e.g. MSI MAG X870E Tomahawk WiFi"
                  value={form.name} onChange={e => field('name', e.target.value)} />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Category</label>
                <select className="form-input" value={form.category} onChange={e => field('category', e.target.value)}>
                  {CATEGORIES.map(c => <option key={c}>{c}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Target price ($)</label>
                <input className="form-input" type="number" placeholder="269.99" min="0"
                  value={form.target_price} onChange={e => field('target_price', parseFloat(e.target.value))} />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                <label className="form-label">Search query (used to find prices)</label>
                <div style={{ display: 'flex', gap: 8 }}>
                  <input className="form-input" style={{ flex: 1 }}
                    placeholder="e.g. MSI MAG X870E Tomahawk WiFi motherboard AM5"
                    value={form.search_query} onChange={e => field('search_query', e.target.value)} />
                  <button className="btn btn-secondary" onClick={searchLive} disabled={searching}>
                    {searching ? '...' : 'Test'}
                  </button>
                </div>
              </div>
            </div>

            {liveResults.length > 0 && (
              <div style={{ background: '#0f1117', borderRadius: 6, padding: 12, marginBottom: 12, maxHeight: 160, overflowY: 'auto' }}>
                <div style={{ fontSize: 11, color: '#64748b', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Live results</div>
                {liveResults.map((r, i) => (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid #1e2536', fontSize: 12 }}>
                    <span style={{ color: '#94a3b8' }}>{r.retailer}</span>
                    <span style={{ color: r.price < form.target_price ? '#34d399' : '#e2e8f0', fontWeight: 500 }}>${r.price?.toFixed(2)}</span>
                  </div>
                ))}
              </div>
            )}

            <div className="form-row">
              <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                <label className="form-label">
                  Required keywords
                  <span style={{ fontWeight: 400, color: 'var(--text-dim)', marginLeft: 6 }}>
                    — results must contain ALL of these (comma-separated)
                  </span>
                </label>
                <input className="form-input"
                  placeholder="e.g. X870E  (prevents X870 results matching)"
                  value={form.required_keywords}
                  onChange={e => field('required_keywords', e.target.value)} />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                <label className="form-label">Notes (optional)</label>
                <input className="form-input" placeholder="e.g. Need AM5, ATX form factor"
                  value={form.notes} onChange={e => field('notes', e.target.value)} />
              </div>
            </div>

            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={closeModal}>Cancel</button>
              <button className="btn btn-primary" onClick={save}>
                {editPart ? 'Save changes' : 'Add part'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete confirm */}
      {deleteConfirm && (
        <div className="modal-overlay" onClick={() => setDeleteConfirm(null)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ width: 360 }}>
            <div className="modal-title">Delete part?</div>
            <p style={{ color: '#94a3b8', fontSize: 13, marginBottom: 8 }}>
              This will also delete all price history for this part. This can't be undone.
            </p>
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setDeleteConfirm(null)}>Cancel</button>
              <button className="btn btn-danger" onClick={() => deletePart(deleteConfirm)}>Delete</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
