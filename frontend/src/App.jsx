import React, { useState, useEffect, useRef } from 'react';
import { 
  Shield, CheckCircle, XCircle, AlertCircle, RefreshCw, 
  Smartphone, TrendingUp, TrendingDown, ArrowUpRight, 
  ArrowDownRight, Users, Activity, FileText, Database, 
  CreditCard, IndianRupee, Bell, Send
} from 'lucide-react';
import { 
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, 
  Tooltip, CartesianGrid 
} from 'recharts';

export default function App() {
  const [customers, setCustomers] = useState([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState('CUST_STRONG_START');
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  
  // Real-time Pipeline States for the selected customer
  const [features, setFeatures] = useState(null);
  const [score, setScore] = useState(null);
  const [risk, setRisk] = useState(null);
  const [compliance, setCompliance] = useState(null);
  const [notification, setNotification] = useState(null);
  
  // Simulation logs
  const [liveTransactions, setLiveTransactions] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [chartData, setChartData] = useState([]);
  const [payloadExplorer, setPayloadExplorer] = useState(null);
  
  // Connection state
  const [isConnected, setIsConnected] = useState(false);
  const [systemMessage, setSystemMessage] = useState('Initializing connections...');
  const [mobileNotify, setMobileNotify] = useState(false);
  const [disbursedStatus, setDisbursedStatus] = useState(false);

  const socketRef = useRef(null);

  // Fetch static metadata & history
  useEffect(() => {
    fetchCustomers();
  }, []);

  useEffect(() => {
    if (selectedCustomerId) {
      fetchCustomerHistory(selectedCustomerId);
      setDisbursedStatus(false);
      setMobileNotify(false);
    }
  }, [selectedCustomerId]);

  const fetchCustomers = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/customers');
      const data = await res.json();
      setCustomers(data);
      if (data.length > 0 && !selectedCustomer) {
        setSelectedCustomer(data.find(c => c.customer_id === selectedCustomerId) || data[0]);
      }
    } catch (e) {
      console.error("Error fetching customers:", e);
      setSystemMessage("Backend server offline.");
    }
  };

  const fetchCustomerHistory = async (customerId) => {
    try {
      // 1. Fetch historical transactions
      const txRes = await fetch(`http://localhost:8000/api/transactions/${customerId}?limit=50`);
      const txs = await txRes.json();
      
      // Update local transaction log
      setLiveTransactions(prev => {
        // Keep unique transaction events
        const existingIds = new Set(prev.map(t => t.event_id));
        const filteredNew = txs.filter(t => !existingIds.has(t.event_id));
        return [...filteredNew, ...prev].slice(0, 50);
      });

      // 2. Fetch audit logs
      const logRes = await fetch(`http://localhost:8000/api/audit-logs?customer_id=${customerId}&limit=100`);
      const logs = await logRes.json();
      setAuditLogs(logs);

      // 3. Extract historical score data
      const scores = logs
        .filter(l => l.agent_name === 'ScoringAgent')
        .map(l => ({
          score: l.payload.score,
          timestamp: new Date(l.timestamp).toLocaleDateString([], { month: 'short', day: 'numeric' })
        }))
        .reverse(); // oldest to newest
      setChartData(scores);

      // 4. Load latest state from audit logs if available
      const latestFeaturesLog = logs.find(l => l.agent_name === 'DataAggregator');
      const latestScoringLog = logs.find(l => l.agent_name === 'ScoringAgent');
      const latestRiskLog = logs.find(l => l.agent_name === 'RiskAgent');
      const latestComplianceLog = logs.find(l => l.agent_name === 'ComplianceAgent');
      const latestNotificationLog = logs.find(l => l.agent_name === 'NotificationAgent');

      if (latestFeaturesLog) setFeatures(latestFeaturesLog.payload);
      if (latestScoringLog) setScore(latestScoringLog.payload);
      if (latestRiskLog) setRisk(latestRiskLog.payload);
      if (latestComplianceLog) setCompliance(latestComplianceLog.payload);
      if (latestNotificationLog) {
        setNotification(latestNotificationLog.payload);
        if (latestNotificationLog.payload.approved_amount > 0 && latestComplianceLog?.payload.status === "APPROVED") {
          setMobileNotify(true);
        }
      }
    } catch (e) {
      console.error("Error fetching history:", e);
    }
  };

  // Connect WebSocket
  useEffect(() => {
    connectWS();
    return () => {
      if (socketRef.current) socketRef.current.close();
    };
  }, []);

  const connectWS = () => {
    setSystemMessage("Connecting to WebSocket...");
    const socket = new WebSocket('ws://localhost:8000/ws');
    socketRef.current = socket;

    socket.onopen = () => {
      setIsConnected(true);
      setSystemMessage("Live scoring channel active.");
    };

    socket.onclose = () => {
      setIsConnected(false);
      setSystemMessage("WebSocket disconnected. Retrying...");
      setTimeout(connectWS, 3000);
    };

    socket.onerror = (err) => {
      console.error("WebSocket error:", err);
      socket.close();
    };

    socket.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      
      if (msg.type === "SYSTEM_INFO") {
        setSystemMessage(msg.message);
      } 
      else if (msg.type === "PIPELINE_UPDATE") {
        const update = msg;
        
        // Append raw event to transaction scroller ticker
        setLiveTransactions(prev => [update.event, ...prev].slice(0, 50));
        
        // Append audit log entries locally
        const mockAuditEntry = (agent, payload) => ({
          id: Date.now() + Math.random(),
          timestamp: new Date().toISOString(),
          customer_id: update.customer_id,
          agent_name: agent,
          event_type: 'live_decision',
          payload
        });
        
        // If this update is for our focused customer, update main panels
        if (update.customer_id === selectedCustomerId) {
          setFeatures(update.features);
          setScore(update.score);
          setRisk(update.risk);
          setCompliance(update.compliance);
          setNotification(update.notification);
          
          // Append new score to line chart
          setChartData(prev => [
            ...prev, 
            {
              score: update.score.score,
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
            }
          ].slice(-25)); // limit chart to last 25 ticks

          // If approved, trigger mobile alert on phone simulator
          if (update.compliance.status === "APPROVED" && update.notification.approved_amount > 0) {
            setMobileNotify(true);
            setDisbursedStatus(false);
          } else {
            setMobileNotify(false);
          }
        }

        // Add to global logs
        setAuditLogs(prev => [
          mockAuditEntry("NotificationAgent", update.notification),
          mockAuditEntry("ComplianceAgent", update.compliance),
          mockAuditEntry("RiskAgent", update.risk),
          mockAuditEntry("ScoringAgent", update.score),
          mockAuditEntry("DataAggregator", update.features),
          ...prev
        ].slice(0, 100));
      }
    };
  };

  const handleResetDemo = async () => {
    if (window.confirm("This will erase current database logs and re-seed the 45-day history. Proceed?")) {
      try {
        setSystemMessage("Resetting simulation...");
        const res = await fetch('http://localhost:8000/api/reset-demo', { method: 'POST' });
        const data = await res.json();
        
        // Clear UI states
        setLiveTransactions([]);
        setAuditLogs([]);
        setChartData([]);
        setFeatures(null);
        setScore(null);
        setRisk(null);
        setCompliance(null);
        setNotification(null);
        setMobileNotify(false);
        setDisbursedStatus(false);
        
        setSystemMessage(data.message);
        
        // Reload data
        await fetchCustomers();
        await fetchCustomerHistory(selectedCustomerId);
      } catch (e) {
        console.error("Reset failed:", e);
      }
    }
  };

  const handleDisburseClick = () => {
    setDisbursedStatus(true);
  };

  // UI status colors mapping
  const getRiskColor = (tier) => {
    if (tier === 'Low') return 'var(--status-success)';
    if (tier === 'Medium') return 'var(--status-warning)';
    return 'var(--status-danger)';
  };

  const getComplianceStatusBadge = (status) => {
    if (status === 'APPROVED') return <span className="badge low">Approved</span>;
    if (status === 'HOLD') return <span className="badge medium">Hold</span>;
    return <span className="badge high">Rejected</span>;
  };

  // Dial calculations
  const radius = 65;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = score ? circumference - (score.score / 100) * circumference : circumference;

  return (
    <div className="app-container">
      {/* HEADER SECTION */}
      <header className="glass-panel app-header">
        <div className="logo-section">
          <div className="logo-badge">S</div>
          <div>
            <h1 className="logo-title">Sankalp</h1>
            <p className="logo-subtitle">Agentic AI Credit Scout</p>
          </div>
        </div>
        
        <div className="header-actions">
          <div className="status-indicator">
            <div className={isConnected ? "pulse-dot" : "pulse-dot"} style={{ backgroundColor: isConnected ? 'var(--status-success)' : 'var(--status-danger)' }} />
            <span>{systemMessage}</span>
          </div>
          <button className="btn-reset" onClick={handleResetDemo}>
            <RefreshCw size={14} style={{ marginRight: '4px', verticalAlign: 'middle' }} />
            Reset Demo
          </button>
        </div>
      </header>

      {/* LIVE EVENT STREAM TICKER */}
      <div className="glass-panel ticker-container">
        <div className="ticker-label">
          <Activity size={14} /> Live stream:
        </div>
        <div className="ticker-content">
          {liveTransactions.length === 0 ? (
            <span style={{ color: 'var(--text-muted)' }}>Waiting for transactions...</span>
          ) : (
            liveTransactions.slice(0, 10).map((t, idx) => (
              <div key={t.event_id || idx} className="ticker-item">
                <span style={{ color: 'var(--accent-gold)' }}>●</span>
                <span style={{ fontWeight: 600 }}>{customers.find(c => c.customer_id === t.customer_id)?.name || t.customer_id}</span>
                <span style={{ color: 'var(--text-muted)' }}>({t.event_type.replace('_', ' ')})</span>
                <span style={{ color: t.status === 'SUCCESS' ? 'var(--status-success)' : 'var(--status-danger)', fontWeight: 600 }}>
                  ₹{t.amount.toLocaleString('en-IN')}
                </span>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                  {new Date(t.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </span>
              </div>
            ))
          )}
        </div>
      </div>

      {/* MAIN LAYOUT GRID */}
      <main className="dashboard-grid">
        
        {/* SIDEBAR: CUSTOMER PROFILES */}
        <section className="customer-sidebar">
          <h2 className="section-title">
            <Users size={14} /> Candidates
          </h2>
          {customers.map((c) => {
            const isActive = c.customer_id === selectedCustomerId;
            return (
              <div 
                key={c.customer_id} 
                className={`customer-card ${isActive ? 'active' : ''}`}
                onClick={() => {
                  setSelectedCustomerId(c.customer_id);
                  setSelectedCustomer(c);
                }}
              >
                <div className="customer-header">
                  <span className="customer-name">{c.name}</span>
                  <span style={{ fontSize: '0.6875rem', color: 'var(--accent-gold)' }}>
                    {c.customer_id === 'CUST_STRONG_START' && 'Strong Profile'}
                    {c.customer_id === 'CUST_TRENDING_UP' && 'Trending Up'}
                    {c.customer_id === 'CUST_VOLATILE' && 'Erratic Profile'}
                  </span>
                </div>
                <div className="customer-meta">
                  <span>{c.location}</span>
                </div>
                <div className="customer-meta" style={{ color: 'var(--text-muted)' }}>
                  <span>{c.mobile}</span>
                </div>
              </div>
            );
          })}

          {/* PROJECT EXPLAINER */}
          <div className="glass-panel glass-card" style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <h3 style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--accent-gold)' }}>What is Sankalp?</h3>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: '1.4' }}>
              Sankalp continuously scores unbanked customers from alternative data (mandi receipts, utility bills, recharges) and approves microloans. Approved offers push instantly to field agents (Bank Mitras) for disbursal.
            </p>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', borderTop: '1px solid var(--border-glass)', paddingTop: '0.5rem', marginTop: '0.25rem' }}>
              <strong>Real:</strong> Agent scoring, compliance, logging.<br />
              <strong>Simulated:</strong> Transaction stream.
            </div>
          </div>
        </section>

        {/* CENTER CONTENT: LIVE SCORE & ALTERNATIVE FEATURES */}
        <section className="main-content">
          
          {/* SCORE SECTION */}
          <div className="scoring-row">
            
            {/* GAUGE CARD */}
            <div className="glass-panel score-dial-card">
              <span className="section-title" style={{ position: 'absolute', top: '1rem', left: '1.25rem' }}>
                Credit Score
              </span>
              <div className="dial-svg-container" style={{ marginTop: '0.5rem' }}>
                <svg width="160" height="160" viewBox="0 0 160 160">
                  {/* Track ring */}
                  <circle 
                    cx="80" 
                    cy="80" 
                    r={radius} 
                    fill="transparent" 
                    stroke="rgba(255,255,255,0.03)" 
                    strokeWidth="12" 
                  />
                  {/* Progress ring */}
                  <circle 
                    cx="80" 
                    cy="80" 
                    r={radius} 
                    fill="transparent" 
                    stroke={score ? getRiskColor(risk?.risk_tier) : 'var(--text-muted)'} 
                    strokeWidth="12" 
                    strokeDasharray={circumference}
                    strokeDashoffset={strokeDashoffset}
                    strokeLinecap="round"
                    transform="rotate(-90 80 80)"
                    style={{ transition: 'stroke-dashoffset 0.8s ease' }}
                  />
                </svg>
                <div className="dial-score-num">
                  <span className="score-val">{score ? score.score : '--'}</span>
                  {score && score.score_delta !== 0 && (
                    <span className={`score-delta ${score.score_delta > 0 ? 'up' : 'down'}`}>
                      {score.score_delta > 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                      {score.score_delta > 0 ? `+${score.score_delta}` : score.score_delta}
                    </span>
                  )}
                  <span className="score-lbl">Shadow Score</span>
                </div>
              </div>
            </div>

            {/* EXPLANATORY & REASONING factores */}
            <div className="glass-panel glass-card explanation-card">
              <h3 className="section-title">AI Scoring Reasoning</h3>
              <p className="explanation-text">
                {score ? `"${score.explanation}"` : 'Awaiting streaming transactions to compute scoring explanation...'}
              </p>
              <div className="reasoning-list">
                {score && score.reasoning_factors.map((f, idx) => (
                  <div key={idx} className="reasoning-item">
                    {f}
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* HISTORICAL CHART */}
          <div className="glass-panel glass-card" style={{ flex: 1, minHeight: '220px', display: 'flex', flexDirection: 'column' }}>
            <h3 className="section-title" style={{ marginBottom: '1rem' }}>Credit Score Trend</h3>
            <div style={{ flex: 1, width: '100%', height: '180px' }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 5, right: 10, left: -25, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" />
                  <XAxis dataKey="timestamp" stroke="var(--text-muted)" fontSize={10} tickLine={false} />
                  <YAxis domain={[30, 100]} stroke="var(--text-muted)" fontSize={10} tickLine={false} />
                  <Tooltip 
                    contentStyle={{ background: '#0f172a', borderColor: 'var(--border-glass)', borderRadius: '8px' }}
                    labelStyle={{ color: 'var(--text-secondary)' }}
                  />
                  <Line 
                    type="monotone" 
                    dataKey="score" 
                    stroke="var(--accent-gold)" 
                    strokeWidth={2} 
                    dot={{ fill: 'var(--accent-gold)', strokeWidth: 1, r: 3 }}
                    activeDot={{ r: 5, strokeWidth: 0 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* DYNAMIC ALTERNATIVE FEATURES */}
          <div className="features-grid">
            <div className="feature-stat-card">
              <span className="feature-label">Net Savings Ratio</span>
              <span className="feature-value" style={{ color: features && features.net_savings_ratio >= 0 ? 'var(--status-success)' : 'var(--status-danger)' }}>
                {features ? `${int(features.net_savings_ratio*100)}%` : '--'}
              </span>
            </div>
            
            <div className="feature-stat-card">
              <span className="feature-label">Utility Bill Timeliness</span>
              <span className="feature-value" style={{ color: features && features.utility_payment_regularity >= 0.8 ? 'var(--status-success)' : 'var(--status-danger)' }}>
                {features ? `${int(features.utility_payment_regularity*100)}%` : '--'}
              </span>
            </div>

            <div className="feature-stat-card">
              <span className="feature-label">Crop Sales (Mandi)</span>
              <span className="feature-value">
                {features ? `₹${features.mandi_sales_total.toLocaleString('en-IN')}` : '--'}
              </span>
              <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>
                {features ? `${features.mandi_sales_frequency} sales transactions` : ''}
              </span>
            </div>

            <div className="feature-stat-card">
              <span className="feature-label">UPI Activity</span>
              <span className="feature-value">
                {features ? features.upi_transaction_count : '--'}
              </span>
              <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>
                {features ? `Avg: ₹${features.average_transaction_value.toLocaleString('en-IN')}` : ''}
              </span>
            </div>
          </div>

        </section>

        {/* RIGHT PANEL: RISK, COMPLIANCE & BANK MITRA VIEW */}
        <section className="right-panel">
          
          {/* RISK & LIMIT CARD */}
          <div className="glass-panel glass-card risk-card">
            <h3 className="section-title">Risk Assessment</h3>
            <div className="risk-level-display">
              <span style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>Assigned Tier</span>
              {risk ? (
                <span className={`badge ${risk.risk_tier.toLowerCase()}`}>{risk.risk_tier}</span>
              ) : '--'}
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', borderTop: '1px solid var(--border-glass)', paddingTop: '0.75rem' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Max Microloan Limit</span>
              <span style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--accent-gold)' }}>
                {risk ? `₹${risk.max_loan_limit.toLocaleString('en-IN')}` : '--'}
              </span>
            </div>
            
            <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: '1.4', background: 'rgba(255,255,255,0.01)', padding: '0.5rem', borderRadius: '8px' }}>
              {risk ? risk.justification : 'Awaiting score evaluation to justify exposure limit...'}
            </p>
          </div>

          {/* COMPLIANCE CHECKLIST */}
          <div className="glass-panel glass-card compliance-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 className="section-title">Compliance Audit</h3>
              {compliance ? getComplianceStatusBadge(compliance.status) : '--'}
            </div>

            <div className="rules-list">
              {compliance ? compliance.triggered_rules.map((rule) => (
                <div key={rule.rule_id} className="rule-row">
                  <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'flex-start' }}>
                    {rule.passed ? (
                      <CheckCircle size={12} style={{ color: 'var(--status-success)', marginTop: '2px', flexShrink: 0 }} />
                    ) : (
                      <XCircle size={12} style={{ color: 'var(--status-danger)', marginTop: '2px', flexShrink: 0 }} />
                    )}
                    <span className="rule-desc">{rule.description}</span>
                  </div>
                  <span style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-secondary)', flexShrink: 0 }}>
                    {rule.rule_id === 'RULE_CONSENT' && (rule.value ? 'Yes' : 'No')}
                    {rule.rule_id === 'RULE_MIN_HISTORY' && rule.value}
                    {rule.rule_id === 'RULE_LIMIT_BOUNDS' && `₹${rule.value?.toLocaleString('en-IN')}`}
                    {rule.rule_id === 'RULE_ACTIVE_INFLOWS' && `₹${rule.value?.toLocaleString('en-IN')}`}
                  </span>
                </div>
              )) : (
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Awaiting compliance audits...</span>
              )}
            </div>
            {compliance && compliance.rejection_reason && (
              <div style={{ fontSize: '0.7rem', color: 'var(--status-danger)', background: 'rgba(244,63,94,0.05)', padding: '0.4rem', borderRadius: '6px', marginTop: '0.25rem' }}>
                <strong>Audit Hold Reason:</strong> {compliance.rejection_reason}
              </div>
            )}
          </div>

          {/* BANK MITRA PHONE VIEW */}
          <div className="glass-panel glass-card bankmitra-container">
            <h3 className="section-title" style={{ width: '100%', marginBottom: '0.75rem' }}>
              <Smartphone size={14} style={{ marginRight: '4px', verticalAlign: 'middle' }} /> Bank Mitra Interface
            </h3>
            
            <div className="phone-shell">
              <div className="phone-screen">
                <div className="phone-header">
                  <span>9:41 AM</span>
                  <span>Mitra-App v2.4</span>
                </div>

                <div className="mitra-app-title">
                  <Shield size={14} /> Bharat Bank Mitra
                </div>

                {mobileNotify && notification && (
                  <div className="push-notification">
                    <div className="push-header">
                      <Bell size={12} /> Live Pre-Approval Alert
                    </div>
                    <div className="push-body">
                      {notification.sms_preview}
                    </div>
                  </div>
                )}

                {mobileNotify && notification && notification.approved_amount > 0 ? (
                  <div className="phone-details-card">
                    <div className="phone-detail-row">
                      <span className="phone-detail-lbl">Borrower</span>
                      <span className="phone-detail-val">{notification.customer_name}</span>
                    </div>
                    <div className="phone-detail-row">
                      <span className="phone-detail-lbl">Principal</span>
                      <span className="phone-detail-val">₹{notification.approved_amount.toLocaleString('en-IN')}</span>
                    </div>
                    <div className="phone-detail-row">
                      <span className="phone-detail-lbl">Tenure</span>
                      <span className="phone-detail-val">{notification.tenure_months} Months</span>
                    </div>
                    <div className="phone-detail-row">
                      <span className="phone-detail-lbl">Weekly Installment</span>
                      <span className="phone-detail-val" style={{ color: 'var(--status-success)' }}>
                        ₹{notification.repayment_amount.toLocaleString('en-IN')}
                      </span>
                    </div>

                    {!disbursedStatus ? (
                      <button className="phone-disburse-btn" onClick={handleDisburseClick}>
                        Disburse Cash Now
                      </button>
                    ) : (
                      <div style={{ textAlign: 'center', color: 'var(--status-success)', fontSize: '0.8rem', fontWeight: 700, padding: '0.5rem 0', background: 'rgba(16,185,129,0.05)', borderRadius: '8px' }}>
                        ✓ Cash Disbursed successfully!
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#3f3f46', gap: '0.5rem', textAlign: 'center' }}>
                    <AlertCircle size={28} />
                    <span style={{ fontSize: '0.75rem' }}>No approved loan packages pending for focused client.</span>
                  </div>
                )}
              </div>
            </div>
          </div>

        </section>
      </main>

      {/* BOTTOM SECTION: AUDIT LOG VIEWER */}
      <footer className="glass-panel glass-card audit-logs-section">
        <h2 className="section-title">
          <Database size={14} /> Agent Audit Trail Logs
        </h2>
        <div className="logs-table-container">
          <table className="audit-table">
            <thead>
              <tr>
                <th style={{ width: '120px' }}>Timestamp</th>
                <th style={{ width: '120px' }}>Customer ID</th>
                <th style={{ width: '150px' }}>Agent Name</th>
                <th style={{ width: '150px' }}>Event Action</th>
                <th>Payload Decision Details (Click to inspect)</th>
              </tr>
            </thead>
            <tbody>
              {auditLogs.length === 0 ? (
                <tr>
                  <td colSpan="5" style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
                    No audit logs available. Start simulation feed...
                  </td>
                </tr>
              ) : (
                auditLogs.map((log) => (
                  <tr key={log.id}>
                    <td>{new Date(log.timestamp).toLocaleTimeString()}</td>
                    <td>{log.customer_id}</td>
                    <td>
                      <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                        {log.agent_name}
                      </span>
                    </td>
                    <td>
                      <span style={{ color: 'var(--accent-gold)' }}>
                        {log.event_type}
                      </span>
                    </td>
                    <td>
                      <div 
                        className="audit-payload-json"
                        onClick={() => setPayloadExplorer(log)}
                      >
                        {JSON.stringify(log.payload)}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </footer>

      {/* JSON PAYLOAD EXPLORER MODAL */}
      {payloadExplorer && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '2rem' }}>
          <div className="glass-panel glass-card" style={{ width: '100%', maxWidth: '600px', maxHeight: '80%', display: 'flex', flexDirection: 'column', gap: '1rem', background: '#0b0f19' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-glass)', paddingBottom: '0.5rem' }}>
              <h3 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--accent-gold)' }}>
                {payloadExplorer.agent_name} Payload Details
              </h3>
              <button 
                style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '1.2rem' }}
                onClick={() => setPayloadExplorer(null)}
              >
                ×
              </button>
            </div>
            <pre style={{ flex: 1, overflowY: 'auto', background: 'rgba(0,0,0,0.3)', padding: '1rem', borderRadius: '8px', fontSize: '0.75rem', color: '#e2e8f0', fontFamily: 'monospace' }}>
              {JSON.stringify(payloadExplorer.payload, null, 2)}
            </pre>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
              <button 
                className="btn-reset" 
                onClick={() => setPayloadExplorer(null)}
                style={{ padding: '0.4rem 1rem' }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Helper function to cast to integer for render
function int(val) {
  return Math.round(val);
}
