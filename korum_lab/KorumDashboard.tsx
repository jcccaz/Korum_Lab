import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Database, Brain, ShieldAlert, FileText, Network, Search, Activity, Terminal, CheckCircle2, ChevronRight, AlertTriangle, AlertCircle } from "lucide-react";
import "./KorumDashboard.css";

const starterText = `Project FrankNet:\nWe are deciding whether to replace a failing router or reroute traffic.\nPacket loss has increased 25%.\nTechnicians report intermittent outages.`;

function extractLines(text: string) {
  const lines = text
    .split(/\n+/)
    .map((l) => l.trim())
    .filter(Boolean);

  const projectLine = lines.find((l) => /project\s+/i.test(l)) || "Project: Unknown";
  const project = projectLine.replace(/^project\s*/i, "").replace(/^:\s*/, "").replace(/:$/, "").trim() || "Unknown";

  const decisionLine =
    lines.find((l) => /decid/i.test(l)) ||
    lines.find((l) => /whether to/i.test(l)) ||
    "Decision context not detected.";

  const evidence = lines.filter((l) => /increased|report|logs|outage|timeout|error|packet loss|latency/i.test(l));

  const risks = [
    text.toLowerCase().includes("reroute") ? "Rerouting may create downstream congestion or instability." : null,
    /outage|packet loss|timeout|error/i.test(text) ? "Service degradation may continue if remediation is delayed." : null,
  ].filter(Boolean) as string[];

  const unknowns = [
    "Exact root cause is not yet confirmed.",
    "Cost and time tradeoff between the response options is unclear.",
  ];

  return {
    project,
    decision: decisionLine,
    evidence: evidence.length ? evidence : ["No evidence lines detected yet."],
    risks,
    unknowns
  };
}

export default function KorumLabDashboard() {
  const [inputText, setInputText] = useState(starterText);
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState<ReturnType<typeof extractLines> | null>(null);

  const handleExtract = () => {
    setIsProcessing(true);
    setResult(null);
    // Simulate Neural/Engine latency for drama
    setTimeout(() => {
      setResult(extractLines(inputText));
      setIsProcessing(false);
    }, 1800);
  };

  const handleReset = () => {
    setInputText("");
    setResult(null);
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
                    Processing...
                  </>
                ) : (
                  <>
                    <Brain className="icon" /> Extract Insights
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Right Column: Processed Context */}
        <div className="korum-card">
          <div className="korum-card-header">
            <h3 className="korum-card-title">
              <Network className="icon" /> Intelligence Construct
            </h3>
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
                    <p style={{ margin: '0.5rem 0', fontSize: '0.875rem' }}>Extracting decision lines, evidence, and risk profiles...</p>
                  </div>
                </motion.div>
              )}

              {!isProcessing && !result && (
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
                  {/* Project & Decision */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
                    <div className="korum-data-group" style={{ marginBottom: 0 }}>
                      <div className="korum-data-label">
                        <Activity size={12} /> Project Target
                      </div>
                      <div className="korum-data-value ruby-border" style={{ fontWeight: 600 }}>
                        <span className="korum-badge">Target</span>
                        {result.project}
                      </div>
                    </div>
                    
                    <div className="korum-data-group" style={{ marginBottom: 0 }}>
                      <div className="korum-data-label">
                        <CheckCircle2 size={12} /> Core Decision
                      </div>
                      <div className="korum-data-value ruby-border">
                        {result.decision}
                      </div>
                    </div>
                  </div>

                  {/* Evidence Array */}
                  <div className="korum-data-group">
                    <div className="korum-data-label">
                      <Database size={12} /> Evidence Traces
                    </div>
                    <ul className="korum-list">
                      {result.evidence.map((ev, i) => (
                        <motion.li 
                          initial={{ opacity: 0, x: -10 }} 
                          animate={{ opacity: 1, x: 0 }} 
                          transition={{ delay: 0.1 * i }}
                          key={i}
                        >
                          <ChevronRight size={16} className="bullet" />
                          <span>{ev}</span>
                        </motion.li>
                      ))}
                    </ul>
                  </div>

                  {/* Risks */}
                  <div className="korum-data-group">
                    <div className="korum-data-label">
                      <ShieldAlert size={12} style={{ color: 'var(--k-ruby-intense)' }} /> Known Risks
                    </div>
                    <ul className="korum-list" style={{ borderColor: 'var(--k-ruby-base)' }}>
                      {result.risks.length > 0 ? result.risks.map((r, i) => (
                         <motion.li initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 + (0.1 * i) }} key={i}>
                           <AlertTriangle size={16} className="bullet" style={{ color: 'var(--k-warning)' }} />
                           <span>{r}</span>
                         </motion.li>
                      )) : (
                        <li>No identifiable risks extracted.</li>
                      )}
                    </ul>
                  </div>

                  {/* Unknowns */}
                  <div className="korum-data-group">
                    <div className="korum-data-label">
                      <AlertCircle size={12} style={{ color: 'var(--k-text-muted)' }} /> Intelligence Gaps (Unknowns)
                    </div>
                    <ul className="korum-list">
                      {result.unknowns.map((u, i) => (
                         <motion.li initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3 + (0.1 * i) }} key={i}>
                           <span className="bullet" style={{ color: 'var(--k-text-muted)' }}>?</span>
                           <span style={{ color: 'var(--k-text-muted)' }}>{u}</span>
                         </motion.li>
                      ))}
                    </ul>
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
