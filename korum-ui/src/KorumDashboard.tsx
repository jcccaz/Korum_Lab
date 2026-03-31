import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Database, Brain, ShieldAlert, FileText, Network, Search, Activity, Terminal, CheckCircle2, ChevronRight, AlertTriangle, AlertCircle, Cpu, FileCheck } from "lucide-react";
import "./KorumDashboard.css";

const starterText = `Project FrankNet:\nWe are deciding whether to replace a failing router or reroute traffic.\nPacket loss has increased 25%.\nTechnicians report intermittent outages.`;

// Data shaping for the Backend Response (Matches api.py schema)
interface ExtractResult {
  project: string;
  decision_context: string;
  evidence: string[];
  assumptions: string[];
  risks: string[];
  unknowns: string[];
  recommendation: string;
  confidence_score: number;
  governance_status: string;
  status_color: string;
  graph_injection_status?: string;
}

export default function KorumLabDashboard() {
  const [inputText, setInputText] = useState(starterText);
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState<ExtractResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleExtract = async () => {
    setIsProcessing(true);
    setResult(null);
    setErrorMsg(null);
    
    try {
      const response = await fetch("http://127.0.0.1:8000/api/extract", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: inputText }),
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.detail || "Failed to hit extraction engine");
      }
      
      setResult(data);
    } catch (err: any) {
       setErrorMsg(err.message || "Engine API offline or unreachable.");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleReset = () => {
    setInputText("");
    setResult(null);
    setErrorMsg(null);
  };

  const renderConfidenceRing = (score: number) => {
    let strokeColor = "var(--k-success)";
    if (score < 80) strokeColor = "var(--k-warning)";
    if (score < 50) strokeColor = "var(--k-ruby-base)";
    
    const radius = 24;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (score / 100) * circumference;

    return (
      <div style={{ position: "relative", width: "64px", height: "64px", display: "flex", alignItems: "center", justifyContent: "center" }}>
         <svg width="64" height="64" style={{ transform: "rotate(-90deg)", position: "absolute" }}>
           <circle cx="32" cy="32" r={radius} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="6" />
           <motion.circle 
             cx="32" cy="32" r={radius} 
             fill="none" 
             stroke={strokeColor} 
             strokeWidth="6"
             strokeDasharray={circumference}
             initial={{ strokeDashoffset: circumference }}
             animate={{ strokeDashoffset: offset }}
             transition={{ duration: 1.5, ease: "easeOut" }}
             strokeLinecap="round"
           />
         </svg>
         <span style={{ fontSize: "1rem", fontWeight: 700, color: "var(--k-text-main)" }}>{score}</span>
      </div>
    );
  };

  return (
    <div className="korum-dashboard-container">
      {/* Header */}
      <header className="korum-header">
        <div className="korum-logo">
          <Terminal className="icon" size={28} />
          <span>Korum Lab Console</span>
        </div>
        <div className="korum-status">
          <div className="korum-status-dot"></div>
          Decision Engine Online
        </div>
      </header>

      {/* Main Grid */}
      <div className="korum-grid">
        
        {/* Left Column: Input Source */}
        <div className="korum-card">
          <div className="scan-line"></div>
          <div className="korum-card-header">
            <h3 className="korum-card-title">
              <Database className="icon" /> Raw Context Extraction
            </h3>
          </div>
          <div className="korum-card-content">
            <p style={{ fontSize: '0.875rem', color: 'var(--k-text-muted)', marginBottom: '1rem', marginTop: 0 }}>
              Input operational data, meeting transcripts, or intelligence logs for decision extraction.
            </p>
            <textarea 
              className="korum-textarea" 
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="Enter context here... (e.g. Project Code, Incident Data)"
              spellCheck="false"
            />
            
            <div className="korum-button-row">
              <button 
                className="korum-button secondary" 
                onClick={handleReset}
                disabled={isProcessing}
              >
                Clear
              </button>
              <button 
                className="korum-button" 
                onClick={handleExtract}
                disabled={isProcessing || !inputText.trim()}
              >
                {isProcessing ? (
                  <>
                    <Activity className="icon" style={{ animation: 'pulse 1s infinite' }} /> 
                    Querying LLM Engine...
                  </>
                ) : (
                  <>
                    <Brain className="icon" /> Extract Insights
                  </>
                )}
              </button>
            </div>
            
            {errorMsg && (
              <div style={{ marginTop: '1rem', padding: '1rem', backgroundColor: 'rgba(230, 57, 70, 0.1)', border: '1px solid var(--k-ruby-base)', borderRadius: '6px', color: 'var(--k-ruby-base)', fontSize: '0.875rem' }}>
                <AlertCircle size={14} style={{ display: 'inline', marginRight: '6px', verticalAlign: '-2px' }}/>
                {errorMsg}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Processed Context */}
        <div className="korum-card">
          <div className="korum-card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 className="korum-card-title">
              <Network className="icon" /> Intelligence Construct
            </h3>
            {result && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.75rem', color: 'var(--k-text-muted)', textTransform: 'uppercase' }}>
                <FileCheck size={14} /> LIVE NEO4J STREAM
              </div>
            )}
          </div>
          
          <div className="korum-card-content" style={{ overflowY: 'auto' }}>
            <AnimatePresence mode="wait">
              {isProcessing && (
                <motion.div 
                  initial={{ opacity: 0 }} 
                  animate={{ opacity: 1 }} 
                  exit={{ opacity: 0 }}
                  className="korum-empty-state"
                  key="loading"
                >
                  <Search className="icon" style={{ animation: 'pulse 2s infinite', color: 'var(--k-ruby-base)', opacity: 1 }} />
                  <div>
                    <strong style={{ color: 'var(--k-ruby-base)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
                      Parsing Neural Graph
                    </strong>
                    <p style={{ margin: '0.5rem 0', fontSize: '0.875rem' }}>Hitting actual Python API and injecting into graph...</p>
                  </div>
                </motion.div>
              )}

              {!isProcessing && !result && !errorMsg && (
                <motion.div 
                  initial={{ opacity: 0 }} 
                  animate={{ opacity: 1 }} 
                  exit={{ opacity: 0 }}
                  className="korum-empty-state"
                  key="empty"
                >
                  <FileText className="icon" />
                  <span>Awaiting Data Source Injection</span>
                </motion.div>
              )}

              {!isProcessing && result && (
                <motion.div 
                  initial={{ opacity: 0, y: 10 }} 
                  animate={{ opacity: 1, y: 0 }} 
                  transition={{ staggerChildren: 0.1 }}
                  key="results"
                >
                  {/* Governor Header Dashboard */}
                  <div style={{ display: 'flex', gap: '1.5rem', marginBottom: '2rem', padding: '1rem', backgroundColor: 'rgba(0,0,0,0.3)', border: '1px solid var(--k-border)', borderRadius: '8px', alignItems: 'center' }}>
                    {renderConfidenceRing(result.confidence_score)}
                    <div style={{ flex: 1 }}>
                       <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--k-text-muted)', letterSpacing: '0.1em', marginBottom: '4px' }}>
                         AI Confidence Governor
                       </div>
                       <div style={{ fontSize: '1.125rem', fontWeight: 600, color: `var(--k-${result.status_color || 'ruby-base'})`, letterSpacing: '0.05em' }}>
                         {result.governance_status}
                       </div>
                    </div>
                  </div>

                  {/* Project & Decision */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
                    <div className="korum-data-group" style={{ marginBottom: 0 }}>
                      <div className="korum-data-label">
                        <Activity size={12} /> Project Target
                      </div>
                      <div className="korum-data-value ruby-border" style={{ fontWeight: 600 }}>
                        <span className="korum-badge">Target</span>
                        {result.project || 'Unspecified'}
                      </div>
                    </div>
                    
                    <div className="korum-data-group" style={{ marginBottom: 0 }}>
                      <div className="korum-data-label">
                        <CheckCircle2 size={12} /> Core Decision Context
                      </div>
                      <div className="korum-data-value ruby-border">
                        {result.decision_context || 'None Extracted'}
                      </div>
                    </div>
                  </div>

                  {/* Evidence Array */}
                  <div className="korum-data-group">
                    <div className="korum-data-label">
                      <Database size={12} /> Evidence Traces
                    </div>
                    <ul className="korum-list">
                      {result.evidence && result.evidence.length > 0 ? result.evidence.map((ev, i) => (
                        <motion.li initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.1 * i }} key={i}>
                          <ChevronRight size={16} className="bullet" />
                          <span>{ev}</span>
                        </motion.li>
                      )) : <li>No evidence lines detected.</li> }
                    </ul>
                  </div>

                  {/* Assumptions vs Risks */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
                    <div className="korum-data-group" style={{ marginBottom: 0 }}>
                      <div className="korum-data-label">
                        <Cpu size={12} style={{ color: 'var(--k-warning)' }} /> Assumptions
                      </div>
                      <ul className="korum-list" style={{ borderColor: 'var(--k-border-light)' }}>
                        {result.assumptions && result.assumptions.length > 0 ? result.assumptions.map((u, i) => (
                          <motion.li initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 + (0.1 * i) }} key={i}>
                            <span className="bullet" style={{ color: 'var(--k-warning)' }}>A</span>
                            <span style={{ color: 'var(--k-text-muted)' }}>{u}</span>
                          </motion.li>
                        )) : <li style={{ color: 'var(--k-text-muted)' }}>No clear assumptions made.</li>}
                      </ul>
                    </div>
                    
                    <div className="korum-data-group" style={{ marginBottom: 0 }}>
                      <div className="korum-data-label">
                        <ShieldAlert size={12} style={{ color: 'var(--k-ruby-intense)' }} /> Known Risks
                      </div>
                      <ul className="korum-list" style={{ borderColor: 'var(--k-ruby-base)' }}>
                        {result.risks && result.risks.length > 0 ? result.risks.map((r, i) => (
                          <motion.li initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3 + (0.1 * i) }} key={i}>
                            <AlertTriangle size={16} className="bullet" style={{ color: 'var(--k-ruby-base)' }} />
                            <span>{r}</span>
                          </motion.li>
                        )) : <li>No identifiable risks extracted.</li>}
                      </ul>
                    </div>
                  </div>

                  {/* Recommendation */}
                  <div className="korum-data-group">
                    <div className="korum-data-label">
                      <Brain size={12} style={{ color: 'var(--k-success)' }} /> Actionable Recommendation
                    </div>
                    <div className="korum-data-value" style={{ borderLeftColor: 'var(--k-success)', background: 'rgba(43, 147, 72, 0.05)' }}>
                      {result.recommendation || 'No specific recommendation offered given the data.'}
                    </div>
                  </div>

                  {/* Graph Injection State */}
                  <div style={{ marginTop: '2rem', padding: '0.75rem', backgroundColor: 'var(--k-surface-hover)', borderRadius: '4px', border: '1px solid var(--k-border)', fontSize: '0.75rem', color: 'var(--k-text-muted)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                     <Network size={14} /> 
                     <span><strong>Graph Engine Status:</strong> {result.graph_injection_status || 'Waiting...'}</span>
                  </div>

                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

      </div>
    </div>
  );
}
