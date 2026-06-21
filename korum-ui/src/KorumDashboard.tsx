import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Database, Brain, ShieldAlert, FileText, Network, Search, Activity, Terminal, CheckCircle2, ChevronRight, AlertTriangle, AlertCircle, Cpu, FileCheck, Target, Info, RotateCcw, TrendingUp, TrendingDown, Minus, Scale, ListChecks, XCircle, Send, Copy, ExternalLink, History, Anchor } from "lucide-react";
import "./KorumDashboard.css";

const starterText = `Project FrankNet:\nWe are deciding whether to replace a failing router or reroute traffic.\nPacket loss has increased 25%.\nTechnicians report intermittent outages.`;

// --- Strategy Types & Presets (mirrors korum_lab/models/strategy.py) ---
interface Strategy {
  objective: string;
  decision_type: string;
  success_criteria: string[];
  required_evidence: string[];
  risk_tolerance: string;
  time_horizon: string;
  escalation_rules: Record<string, unknown>;
}

const STRATEGY_PRESETS: Record<string, Strategy> = {
  "Incident Response": {
    objective: "Maintain service stability while minimizing customer impact",
    decision_type: "Incident Response",
    success_criteria: ["Restore stability quickly", "Avoid cascading failures"],
    required_evidence: ["Telemetry or log confirmation", "Operational or field confirmation"],
    risk_tolerance: "Medium",
    time_horizon: "Immediate",
    escalation_rules: { confidence_below: 65, unknowns_exceed_evidence: true, missing_required_evidence: true },
  },
  "Financial Review": {
    objective: "Validate financial decision against risk exposure and return thresholds",
    decision_type: "Financial Review",
    success_criteria: ["ROI clearly demonstrated", "Risk exposure within approved limits"],
    required_evidence: ["Financial data or projections", "Risk assessment or audit trail"],
    risk_tolerance: "Low",
    time_horizon: "Short-term",
    escalation_rules: { confidence_below: 70, unknowns_exceed_evidence: true, missing_required_evidence: true },
  },
  "Strategic Planning": {
    objective: "Align decision with long-term organizational objectives and market position",
    decision_type: "Strategic Planning",
    success_criteria: ["Aligns with stated mission", "Competitive advantage demonstrated"],
    required_evidence: ["Market or competitive analysis", "Stakeholder or leadership input"],
    risk_tolerance: "High",
    time_horizon: "Long-term",
    escalation_rules: { confidence_below: 55, unknowns_exceed_evidence: false, missing_required_evidence: true },
  },
};

// --- Governor Verdict Shape ---
interface GovernorVerdict {
  final_decision: "GO" | "NO-GO" | "CONDITIONAL";
  decision_status: string;
  confidence_score: number;
  red_team_verdict: "SUSTAINED" | "PARTIALLY SUSTAINED" | "REJECTED";
  new_risks_identified: string[];
  critical_unresolved_risks: string[];
  required_validations: string[];
  decision_conditions: string[];
  failure_triggers: string[];
  monitoring_requirements: string[];
  governor_rationale: string;
  rule_flags: string[];
}

// --- Push-to-KorumOS Response Shape (mirrors api.py's /api/push-to-korum) ---
interface PushToKorumResult {
  status: "manual_required" | "submitted" | "error";
  message?: string;
  query_package: string;
  korumos_url?: string;
  job_id?: string | null;
  poll_url?: string;
  http_status?: number;
  detail?: string;
}

// --- Send-to-ANCHOR Response Shape (mirrors api.py's /api/push-to-anchor) ---
interface PushToAnchorResult {
  status: "manual_required" | "ingested" | "duplicate" | "submitted" | "error";
  message?: string;
  query_package: string;
  anchor_url?: string;
  http_status?: number;
  detail?: string;
}

// --- Concept Lock Shape (mirrors api.py's /api/concept-lock) ---
// Per the KORUM Concept Lock Workflow: this is the frozen, reusable
// institutional pattern — not the raw decision. This is what goes to ANCHOR.
//
// Governance Conditions stay split into four subfields — they answer
// different questions for different downstream consumers (approval gate,
// pre-execution gate for Foundry Build, reversal trigger, ongoing
// Watchtower hook) and flattening them would erase that distinction.
interface GovernanceConditions {
  decision_conditions: string[];
  required_validations: string[];
  failure_triggers: string[];
  monitoring_requirements: string[];
}

interface ConceptLock {
  id: string | null;
  decision_id: string | null;
  status: "LOCKED" | "CONDITIONAL_LOCK";
  core_thesis: string;
  supporting_assumptions: string[];
  risks: string[];
  recommendations: string[];
  open_unknowns: string[];
  governance_conditions: GovernanceConditions;
  graph_status: string;
}

// --- Blueprint Preview Shape (mirrors api.py's /api/concept-lock/{id}/preview-blueprint) ---
// Test-harness preview only — a single LLM sanity-check of a Concept Lock.
// NOT Foundry's real Forge: no council seats, no phased build, no Construction
// Documents, no Send to Coder. Planning artifacts only — no code/repo/deploy.
interface BuildBlueprint {
  id: string | null;
  lock_id: string | null;
  status: string;
  is_preview: boolean;
  note: string;
  product_brief: string;
  architecture_blueprint: string;
  data_model: string[];
  required_components: string[];
  dependencies: string[];
  build_phases: string[];
  validation_gates: string[];
  graph_status: string;
}

// --- History List Item (mirrors korum_lab/graph/queries.py's query_list_decisions) ---
interface DecisionHistoryItem {
  id: string;
  decision_context: string;
  project: string | null;
  confidence_score: number | null;
  governance_status: string | null;
  created_at: string;
}

// --- History Detail (mirrors query_decision_by_id) ---
interface DecisionDetail {
  id: string;
  decision_context: string;
  project: string | null;
  confidence_score: number | null;
  governance_status: string | null;
  created_at: string | null;
  evidence: string[];
  assumptions: string[];
  unknowns: string[];
  risks: string[];
  recommendation: string | null;
  strategy_decision_type: string | null;
  strategy_objective: string | null;
}

// --- API Response Shape ---
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
  governance_reason: string[];
  strategy_applied: { decision_type: string; objective: string } | null;
  rebuttal_applied: boolean;
  score_delta: number | null;
  graph_injection_status?: string;
  decision_id?: string | null;
}

export default function KorumLabDashboard() {
  const [inputText, setInputText] = useState(starterText);
  const [selectedStrategy, setSelectedStrategy] = useState<string>("Incident Response");
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState<ExtractResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [rebuttalText, setRebuttalText] = useState<string>("");
  const [isRebutting, setIsRebutting] = useState(false);
  const [redTeamOutput, setRedTeamOutput] = useState<string | null>(null);
  const [isAttacking, setIsAttacking] = useState(false);
  const [governorVerdict, setGovernorVerdict] = useState<GovernorVerdict | null>(null);
  const [isResolving, setIsResolving] = useState(false);
  const [isPushing, setIsPushing] = useState(false);
  const [pushResult, setPushResult] = useState<PushToKorumResult | null>(null);
  const [copyConfirmed, setCopyConfirmed] = useState(false);
  const [isSendingToAnchor, setIsSendingToAnchor] = useState(false);
  const [anchorResult, setAnchorResult] = useState<PushToAnchorResult | null>(null);
  const [conceptLock, setConceptLock] = useState<ConceptLock | null>(null);
  const [isLocking, setIsLocking] = useState(false);
  const [lockError, setLockError] = useState<string | null>(null);
  const [buildBlueprint, setBuildBlueprint] = useState<BuildBlueprint | null>(null);
  const [isGeneratingBlueprint, setIsGeneratingBlueprint] = useState(false);
  const [blueprintError, setBlueprintError] = useState<string | null>(null);
  const [history, setHistory] = useState<DecisionHistoryItem[]>([]);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [loadingDecisionId, setLoadingDecisionId] = useState<string | null>(null);

  const fetchHistory = async () => {
    setIsLoadingHistory(true);
    setHistoryError(null);
    try {
      const response = await fetch("http://127.0.0.1:8000/api/decisions?limit=50");
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Failed to load history");
      setHistory(data);
    } catch (err: any) {
      setHistoryError(err.message || "History unavailable — is Neo4j running?");
    } finally {
      setIsLoadingHistory(false);
    }
  };

  // Pull the list once on load so the panel isn't empty the first time it's opened.
  useEffect(() => {
    fetchHistory();
  }, []);

  const handleLoadDecision = async (decisionId: string) => {
    setLoadingDecisionId(decisionId);
    setErrorMsg(null);
    try {
      const response = await fetch(`http://127.0.0.1:8000/api/decisions/${decisionId}`);
      const data: DecisionDetail = await response.json();
      if (!response.ok) throw new Error((data as any).detail || "Failed to load decision");

      // Neo4j only persists the extraction + governor fields below — it does not
      // store rebuttal/red-team state, so this is a faithful restore of what's
      // actually in the graph, not a full replay of that original session.
      setResult({
        project: data.project || "",
        decision_context: data.decision_context || "",
        evidence: data.evidence || [],
        assumptions: data.assumptions || [],
        risks: data.risks || [],
        unknowns: data.unknowns || [],
        recommendation: data.recommendation || "",
        confidence_score: data.confidence_score ?? 0,
        governance_status: data.governance_status || "RESTORED FROM HISTORY",
        status_color: (data.confidence_score ?? 0) >= 80 ? "success" : (data.confidence_score ?? 0) >= 50 ? "warning" : "ruby-base",
        governance_reason: [],
        strategy_applied: data.strategy_decision_type
          ? { decision_type: data.strategy_decision_type, objective: data.strategy_objective || "" }
          : null,
        rebuttal_applied: false,
        score_delta: null,
        graph_injection_status: `Loaded from history (${data.created_at || "unknown date"})`,
        decision_id: data.id,
      });
      setRedTeamOutput(null);
      setGovernorVerdict(null);
      setPushResult(null);
      setAnchorResult(null);
      setConceptLock(null);
      setLockError(null);
      setBuildBlueprint(null);
      setBlueprintError(null);
      setIsHistoryOpen(false);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to load that decision from history.");
    } finally {
      setLoadingDecisionId(null);
    }
  };

  const handleExtract = async () => {
    setIsProcessing(true);
    setResult(null);
    setErrorMsg(null);

    const strategy = selectedStrategy ? STRATEGY_PRESETS[selectedStrategy] : undefined;

    try {
      const response = await fetch("http://127.0.0.1:8000/api/extract", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: inputText, strategy }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Failed to hit extraction engine");
      }

      setResult(data);
      fetchHistory(); // New decision just landed in Neo4j — refresh the list so it's there immediately.
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
    setRebuttalText("");
    setRedTeamOutput(null);
    setGovernorVerdict(null);
    setPushResult(null);
    setAnchorResult(null);
    setConceptLock(null);
    setLockError(null);
    setBuildBlueprint(null);
    setBlueprintError(null);
    setCopyConfirmed(false);
  };

  const handleRedTeamAttack = async () => {
    if (!result) return;
    setIsAttacking(true);
    setRedTeamOutput(null);

    const summary = [
      `Project: ${result.project}`,
      `Decision: ${result.decision_context}`,
      `Recommendation: ${result.recommendation}`,
      `Confidence: ${result.confidence_score}`,
      `Status: ${result.governance_status}`,
      result.evidence.length ? `Evidence: ${result.evidence.join("; ")}` : "",
      result.assumptions.length ? `Assumptions: ${result.assumptions.join("; ")}` : "",
      result.risks.length ? `Risks: ${result.risks.join("; ")}` : "",
      result.unknowns.length ? `Unknowns: ${result.unknowns.join("; ")}` : "",
    ].filter(Boolean).join("\n");

    try {
      const response = await fetch("http://127.0.0.1:8000/api/rebuttal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision_summary: summary }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Red Team attack failed");
      setRedTeamOutput(data.rebuttal);
    } catch (err: any) {
      setRedTeamOutput(`Error: ${err.message}`);
    } finally {
      setIsAttacking(false);
    }
  };

  const handleGovernorResolve = async () => {
    if (!result || !redTeamOutput) return;
    setIsResolving(true);
    setGovernorVerdict(null);
    setConceptLock(null); // A fresh verdict invalidates any earlier lock — re-lock against the new ruling.
    setLockError(null);
    setBuildBlueprint(null); // ...and any blueprint generated from the old lock goes with it.
    setBlueprintError(null);

    const summary = [
      `Project: ${result.project}`,
      `Decision: ${result.decision_context}`,
      `Recommendation: ${result.recommendation}`,
      `Confidence: ${result.confidence_score}`,
      result.evidence.length ? `Evidence: ${result.evidence.join("; ")}` : "",
      result.assumptions.length ? `Assumptions: ${result.assumptions.join("; ")}` : "",
      result.risks.length ? `Risks: ${result.risks.join("; ")}` : "",
      result.unknowns.length ? `Unknowns: ${result.unknowns.join("; ")}` : "",
    ].filter(Boolean).join("\n");

    try {
      const response = await fetch("http://127.0.0.1:8000/api/governor", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ original_summary: summary, red_team_attack: redTeamOutput }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Governor resolution failed");
      setGovernorVerdict(data);
    } catch (err: any) {
      setGovernorVerdict(null);
    } finally {
      setIsResolving(false);
    }
  };

  const handlePushToKorum = async () => {
    if (!result || !governorVerdict) return;
    setIsPushing(true);
    setPushResult(null);
    setCopyConfirmed(false);

    try {
      const response = await fetch("http://127.0.0.1:8000/api/push-to-korum", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project: result.project,
          decision_context: result.decision_context,
          evidence: result.evidence,
          assumptions: result.assumptions,
          unknowns: result.unknowns,
          risks: result.risks,
          recommendation: result.recommendation,
          governor_verdict: governorVerdict.final_decision,
          governor_confidence: governorVerdict.confidence_score,
          governor_rationale: governorVerdict.governor_rationale,
          required_validations: governorVerdict.required_validations,
          failure_triggers: governorVerdict.failure_triggers,
          monitoring_requirements: governorVerdict.monitoring_requirements,
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Push to KorumOS failed.");
      }
      setPushResult(data);
    } catch (err: any) {
      setPushResult({
        status: "error",
        query_package: "",
        detail: err.message || "Push to KorumOS failed — is the API running?",
      });
    } finally {
      setIsPushing(false);
    }
  };

  const handleLockConcept = async () => {
    if (!result || !governorVerdict) return;
    setIsLocking(true);
    setLockError(null);

    try {
      const response = await fetch("http://127.0.0.1:8000/api/concept-lock", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project: result.project,
          decision_context: result.decision_context,
          recommendation: result.recommendation,
          assumptions: result.assumptions,
          risks: result.risks,
          unknowns: result.unknowns,
          final_decision: governorVerdict.final_decision,
          confidence_score: governorVerdict.confidence_score,
          governor_rationale: governorVerdict.governor_rationale,
          new_risks_identified: governorVerdict.new_risks_identified,
          decision_conditions: governorVerdict.decision_conditions,
          required_validations: governorVerdict.required_validations,
          failure_triggers: governorVerdict.failure_triggers,
          monitoring_requirements: governorVerdict.monitoring_requirements,
          decision_id: result.decision_id,
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Lock Concept failed.");
      }
      setConceptLock(data);
      setAnchorResult(null); // Any previous send was for a different (or no) lock — clear it.
      setBuildBlueprint(null); // Same for any blueprint generated from a previous lock.
      setBlueprintError(null);
    } catch (err: any) {
      setLockError(err.message || "Lock Concept failed — is the API running?");
    } finally {
      setIsLocking(false);
    }
  };

  const handleSendToAnchor = async () => {
    if (!conceptLock) return;
    setIsSendingToAnchor(true);
    setAnchorResult(null);

    try {
      const response = await fetch("http://127.0.0.1:8000/api/push-to-anchor", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project: result?.project || "",
          core_thesis: conceptLock.core_thesis,
          supporting_assumptions: conceptLock.supporting_assumptions,
          risks: conceptLock.risks,
          recommendations: conceptLock.recommendations,
          open_unknowns: conceptLock.open_unknowns,
          governance_conditions: conceptLock.governance_conditions,
          status: conceptLock.status,
          lock_id: conceptLock.id,
          decision_id: conceptLock.decision_id,
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Send to ANCHOR failed.");
      }
      setAnchorResult(data);
    } catch (err: any) {
      setAnchorResult({
        status: "error",
        query_package: "",
        detail: err.message || "Send to ANCHOR failed — is anchor-runtime running?",
      });
    } finally {
      setIsSendingToAnchor(false);
    }
  };

  const handleGenerateBlueprint = async () => {
    // Backend reads the lock fresh from Neo4j by id, so a persisted id is required.
    if (!conceptLock?.id) return;
    setIsGeneratingBlueprint(true);
    setBlueprintError(null);

    try {
      const response = await fetch(
        `http://127.0.0.1:8000/api/concept-lock/${conceptLock.id}/preview-blueprint`,
        { method: "POST" }
      );

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Generate Preview Blueprint failed.");
      }
      setBuildBlueprint(data);
    } catch (err: any) {
      setBlueprintError(err.message || "Generate Preview Blueprint failed — is the API running?");
    } finally {
      setIsGeneratingBlueprint(false);
    }
  };

  const handleCopyQueryPackage = async () => {
    if (!pushResult?.query_package) return;
    try {
      await navigator.clipboard.writeText(pushResult.query_package);
      setCopyConfirmed(true);
      setTimeout(() => setCopyConfirmed(false), 2000);
    } catch {
      // Clipboard API can fail silently (e.g. permissions) — no-op is fine here.
    }
  };

  const handleCopyAnchorPackage = async () => {
    if (!anchorResult?.query_package) return;
    try {
      await navigator.clipboard.writeText(anchorResult.query_package);
      setCopyConfirmed(true);
      setTimeout(() => setCopyConfirmed(false), 2000);
    } catch {
      // Clipboard API can fail silently (e.g. permissions) — no-op is fine here.
    }
  };

  const handleRebuttal = async () => {
    if (!rebuttalText.trim() || !result) return;
    setIsRebutting(true);

    const strategy = selectedStrategy ? STRATEGY_PRESETS[selectedStrategy] : undefined;

    try {
      const response = await fetch("http://127.0.0.1:8000/api/extract", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: inputText,
          strategy,
          rebuttal_text: rebuttalText,
          previous_score: result.confidence_score,
        }),
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Rebuttal evaluation failed");
      setResult(data);
      setRebuttalText("");
    } catch (err: any) {
      setErrorMsg(err.message || "Rebuttal failed.");
    } finally {
      setIsRebutting(false);
    }
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
      <header className="korum-header" style={{ position: 'relative' }}>
        <div className="korum-logo">
          <Terminal className="icon" size={28} />
          <span>Korum Lab Console</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <button
            className="korum-button secondary"
            style={{ padding: '0.5rem 0.9rem' }}
            onClick={() => setIsHistoryOpen((open) => !open)}
          >
            <History size={14} /> History {history.length > 0 && `(${history.length})`}
          </button>
          <div className="korum-status">
            <div className="korum-status-dot"></div>
            Decision Engine Online
          </div>
        </div>

        {isHistoryOpen && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            style={{
              position: 'absolute', top: '100%', right: '1.5rem', marginTop: '0.5rem',
              width: '420px', maxHeight: '420px', overflowY: 'auto', zIndex: 50,
              backgroundColor: 'var(--k-surface, #14141a)', border: '1px solid var(--k-border)',
              borderRadius: '8px', boxShadow: '0 12px 32px rgba(0,0,0,0.5)', padding: '0.75rem',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--k-text-muted)' }}>
                Past Decisions (from Neo4j)
              </span>
              <button className="korum-button secondary" style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }} onClick={fetchHistory} disabled={isLoadingHistory}>
                {isLoadingHistory ? "..." : "Refresh"}
              </button>
            </div>

            {historyError && (
              <div style={{ fontSize: '0.8rem', color: 'var(--k-danger)', padding: '0.5rem 0' }}>{historyError}</div>
            )}
            {!historyError && !isLoadingHistory && history.length === 0 && (
              <div style={{ fontSize: '0.8rem', color: 'var(--k-text-muted)', padding: '0.5rem 0' }}>No past decisions yet.</div>
            )}

            {history.map((item) => (
              <button
                key={item.id}
                onClick={() => handleLoadDecision(item.id)}
                disabled={loadingDecisionId === item.id}
                style={{
                  display: 'block', width: '100%', textAlign: 'left', background: 'rgba(255,255,255,0.02)',
                  border: '1px solid var(--k-border)', borderRadius: '6px', padding: '0.6rem 0.75rem',
                  marginBottom: '0.4rem', cursor: 'pointer', color: 'var(--k-text-main)',
                }}
              >
                <div style={{ fontSize: '0.7rem', color: 'var(--k-accent)', marginBottom: '0.2rem' }}>
                  {item.project || 'Unspecified'} · {item.id}
                  {loadingDecisionId === item.id && " · loading..."}
                </div>
                <div style={{ fontSize: '0.82rem', lineHeight: 1.4 }}>
                  {item.decision_context.length > 110 ? `${item.decision_context.slice(0, 110)}...` : item.decision_context}
                </div>
                {item.confidence_score !== null && (
                  <div style={{ fontSize: '0.7rem', color: 'var(--k-text-muted)', marginTop: '0.3rem' }}>
                    Confidence: {item.confidence_score} · {item.governance_status || 'Unknown status'}
                  </div>
                )}
              </button>
            ))}
          </motion.div>
        )}
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
            <p style={{ fontSize: '0.875rem', color: 'var(--k-text-muted)', marginBottom: '0.5rem', marginTop: 0 }}>
              Input operational data, meeting transcripts, or intelligence logs for decision extraction.
            </p>

            {/* Strategy Selector */}
            <div>
              <label className="korum-data-label" style={{ marginBottom: '0.5rem' }}>
                <Target size={12} /> Operational Strategy
              </label>
              <select
                value={selectedStrategy}
                onChange={(e) => setSelectedStrategy(e.target.value)}
                className="korum-select"
              >
                <option value="">None — Generic Extraction</option>
                {Object.keys(STRATEGY_PRESETS).map((key) => (
                  <option key={key} value={key}>{key}</option>
                ))}
              </select>
              {selectedStrategy && (
                <p style={{ fontSize: '0.75rem', color: 'var(--k-text-muted)', marginTop: '0.4rem', marginBottom: 0 }}>
                  <Info size={11} style={{ display: 'inline', verticalAlign: '-1px', marginRight: '4px' }} />
                  {STRATEGY_PRESETS[selectedStrategy].objective}
                </p>
              )}
            </div>

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
                <AlertCircle size={14} style={{ display: 'inline', marginRight: '6px', verticalAlign: '-2px' }} />
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
                  <div style={{ display: 'flex', gap: '1.5rem', marginBottom: '1rem', padding: '1rem', backgroundColor: 'rgba(0,0,0,0.3)', border: '1px solid var(--k-border)', borderRadius: '8px', alignItems: 'center' }}>
                    {renderConfidenceRing(result.confidence_score)}
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--k-text-muted)', letterSpacing: '0.1em', marginBottom: '4px' }}>
                        AI Confidence Governor
                        {result.rebuttal_applied && (
                          <span style={{ marginLeft: '8px', color: 'var(--k-accent)', fontWeight: 600 }}>· REBUTTAL APPLIED</span>
                        )}
                      </div>
                      <div style={{ fontSize: '1.125rem', fontWeight: 600, color: `var(--k-${result.status_color || 'ruby-base'})`, letterSpacing: '0.05em' }}>
                        {result.governance_status}
                      </div>
                    </div>
                    {result.score_delta !== null && result.score_delta !== undefined && (
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '0.5rem 0.75rem', borderRadius: '6px', backgroundColor: result.score_delta > 0 ? 'rgba(43,147,72,0.1)' : result.score_delta < 0 ? 'rgba(201,74,74,0.1)' : 'rgba(255,255,255,0.05)', border: `1px solid ${result.score_delta > 0 ? 'var(--k-success)' : result.score_delta < 0 ? 'var(--k-danger)' : 'var(--k-border)'}` }}>
                        {result.score_delta > 0 ? <TrendingUp size={16} style={{ color: 'var(--k-success)' }} /> : result.score_delta < 0 ? <TrendingDown size={16} style={{ color: 'var(--k-danger)' }} /> : <Minus size={16} style={{ color: 'var(--k-text-muted)' }} />}
                        <span style={{ fontSize: '0.8rem', fontWeight: 700, color: result.score_delta > 0 ? 'var(--k-success)' : result.score_delta < 0 ? 'var(--k-danger)' : 'var(--k-text-muted)', marginTop: '2px' }}>
                          {result.score_delta > 0 ? `+${result.score_delta}` : result.score_delta}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Strategy Applied */}
                  {result.strategy_applied && (
                    <motion.div
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.1 }}
                      style={{ marginBottom: '1rem', padding: '0.875rem 1rem', backgroundColor: 'rgba(212,175,55,0.05)', border: '1px solid rgba(212,175,55,0.2)', borderRadius: '8px' }}
                    >
                      <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--k-accent)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <Target size={11} /> Strategy Applied
                      </div>
                      <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--k-text-main)', marginBottom: '0.25rem' }}>
                        {result.strategy_applied.decision_type}
                      </div>
                      <div style={{ fontSize: '0.8rem', color: 'var(--k-text-muted)' }}>
                        {result.strategy_applied.objective}
                      </div>
                    </motion.div>
                  )}

                  {/* Governance Reasons */}
                  {result.governance_reason && result.governance_reason.length > 0 && (
                    <motion.div
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.15 }}
                      style={{ marginBottom: '1.5rem', padding: '0.875rem 1rem', backgroundColor: 'rgba(201,74,74,0.06)', border: '1px solid rgba(201,74,74,0.25)', borderRadius: '8px' }}
                    >
                      <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--k-danger)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <ShieldAlert size={11} /> Escalation Triggers
                      </div>
                      <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                        {result.governance_reason.map((reason, i) => (
                          <li key={i} style={{ fontSize: '0.82rem', color: 'var(--k-text-muted)', display: 'flex', gap: '0.5rem', alignItems: 'flex-start' }}>
                            <AlertTriangle size={12} style={{ color: 'var(--k-danger)', flexShrink: 0, marginTop: '2px' }} />
                            {reason}
                          </li>
                        ))}
                      </ul>
                    </motion.div>
                  )}

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
                      )) : <li>No evidence lines detected.</li>}
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

                  {/* Rebuttal Panel */}
                  <div style={{ marginTop: '2rem', padding: '1rem', backgroundColor: 'rgba(212,175,55,0.04)', border: '1px solid rgba(212,175,55,0.2)', borderRadius: '8px' }}>
                    <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--k-accent)', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <RotateCcw size={11} /> Rebuttal / Additional Context
                    </div>
                    <textarea
                      className="korum-textarea"
                      style={{ minHeight: '100px', fontSize: '0.875rem' }}
                      value={rebuttalText}
                      onChange={(e) => setRebuttalText(e.target.value)}
                      placeholder="Provide missing evidence, clarifications, or additional context to address the escalation triggers..."
                      spellCheck="false"
                    />
                    <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.75rem' }}>
                      <button
                        className="korum-button"
                        style={{ flex: 1 }}
                        onClick={handleRebuttal}
                        disabled={isRebutting || !rebuttalText.trim()}
                      >
                        {isRebutting ? (
                          <><Activity size={14} style={{ animation: 'pulse 1s infinite' }} /> Re-Evaluating...</>
                        ) : (
                          <><RotateCcw size={14} /> Re-Evaluate</>
                        )}
                      </button>
                      <button
                        className="korum-button"
                        style={{ flex: 1, backgroundColor: 'rgba(201,74,74,0.15)', color: 'var(--k-danger)', border: '1px solid rgba(201,74,74,0.4)', boxShadow: 'none' }}
                        onClick={handleRedTeamAttack}
                        disabled={isAttacking}
                      >
                        {isAttacking ? (
                          <><Activity size={14} style={{ animation: 'pulse 1s infinite' }} /> Attacking...</>
                        ) : (
                          <><ShieldAlert size={14} /> Red Team Attack</>
                        )}
                      </button>
                    </div>
                    {redTeamOutput && (
                      <button
                        className="korum-button"
                        style={{ width: '100%', marginTop: '0.5rem', backgroundColor: 'rgba(212,175,55,0.1)', color: 'var(--k-accent)', border: '1px solid rgba(212,175,55,0.35)', boxShadow: 'none' }}
                        onClick={handleGovernorResolve}
                        disabled={isResolving}
                      >
                        {isResolving ? (
                          <><Activity size={14} style={{ animation: 'pulse 1s infinite' }} /> Governor Resolving...</>
                        ) : (
                          <><Scale size={14} /> Governor Resolve</>
                        )}
                      </button>
                    )}
                  </div>

                  {/* Red Team Output */}
                  {redTeamOutput && (
                    <motion.div
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      style={{ marginTop: '1rem', padding: '1rem', backgroundColor: 'rgba(201,74,74,0.06)', border: '1px solid rgba(201,74,74,0.3)', borderRadius: '8px' }}
                    >
                      <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--k-danger)', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <ShieldAlert size={11} /> Red Team Challenge — Mistral 7B Local
                      </div>
                      <div style={{ fontSize: '0.875rem', color: 'var(--k-text-main)', lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>
                        {redTeamOutput}
                      </div>
                    </motion.div>
                  )}

                  {/* Governor Verdict Panel */}
                  {governorVerdict && (
                    <motion.div
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      style={{ marginTop: '1rem', padding: '1rem', backgroundColor: 'rgba(212,175,55,0.05)', border: '1px solid rgba(212,175,55,0.3)', borderRadius: '8px' }}
                    >
                      <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--k-accent)', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <Scale size={11} /> Governor Resolution — Final Ruling
                      </div>

                      {/* Decision + Score row */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '0.75rem' }}>
                        <div style={{
                          padding: '0.4rem 1rem', borderRadius: '6px', fontWeight: 700, fontSize: '0.9rem', letterSpacing: '0.08em',
                          backgroundColor: governorVerdict.final_decision === 'GO' ? 'rgba(43,147,72,0.15)' : governorVerdict.final_decision === 'NO-GO' ? 'rgba(201,74,74,0.15)' : 'rgba(212,175,55,0.12)',
                          color: governorVerdict.final_decision === 'GO' ? 'var(--k-success)' : governorVerdict.final_decision === 'NO-GO' ? 'var(--k-danger)' : 'var(--k-accent)',
                          border: `1px solid ${governorVerdict.final_decision === 'GO' ? 'var(--k-success)' : governorVerdict.final_decision === 'NO-GO' ? 'var(--k-danger)' : 'rgba(212,175,55,0.4)'}`,
                        }}>
                          {governorVerdict.decision_status || governorVerdict.final_decision}
                        </div>
                        <div style={{ fontSize: '0.85rem', color: 'var(--k-text-muted)' }}>
                          Adjusted Confidence: <strong style={{ color: 'var(--k-text-main)' }}>{governorVerdict.confidence_score}</strong>
                        </div>
                        <div style={{ marginLeft: 'auto', fontSize: '0.75rem', padding: '0.25rem 0.6rem', borderRadius: '4px', border: '1px solid var(--k-border)',
                          color: governorVerdict.red_team_verdict === 'SUSTAINED' ? 'var(--k-danger)' : governorVerdict.red_team_verdict === 'REJECTED' ? 'var(--k-success)' : 'var(--k-warning)' }}>
                          Red Team: {governorVerdict.red_team_verdict}
                        </div>
                      </div>

                      {/* Rule flags */}
                      {governorVerdict.rule_flags && governorVerdict.rule_flags.length > 0 && (
                        <div style={{ marginBottom: '0.75rem' }}>
                          <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', color: 'var(--k-warning)', marginBottom: '0.4rem', display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <AlertTriangle size={10} /> Rule Flags
                          </div>
                          {governorVerdict.rule_flags.map((flag, i) => (
                            <div key={i} style={{ fontSize: '0.8rem', color: 'var(--k-text-muted)', display: 'flex', gap: '0.5rem', alignItems: 'flex-start', marginBottom: '0.25rem' }}>
                              <AlertTriangle size={11} style={{ color: 'var(--k-warning)', flexShrink: 0, marginTop: '2px' }} />{flag}
                            </div>
                          ))}
                        </div>
                      )}

                      {/* New risks */}
                      {governorVerdict.new_risks_identified.length > 0 && (
                        <div style={{ marginBottom: '0.75rem' }}>
                          <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', color: 'var(--k-danger)', marginBottom: '0.4rem', display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <XCircle size={10} /> Net-New Risks (from Red Team)
                          </div>
                          {governorVerdict.new_risks_identified.map((r, i) => (
                            <div key={i} style={{ fontSize: '0.8rem', color: 'var(--k-text-muted)', display: 'flex', gap: '0.5rem', alignItems: 'flex-start', marginBottom: '0.25rem' }}>
                              <ChevronRight size={11} style={{ color: 'var(--k-danger)', flexShrink: 0, marginTop: '2px' }} />{r}
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Required validations */}
                      {governorVerdict.required_validations.length > 0 && (
                        <div style={{ marginBottom: '0.75rem' }}>
                          <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', color: 'var(--k-accent)', marginBottom: '0.4rem', display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <ListChecks size={10} /> Required Validations
                          </div>
                          {governorVerdict.required_validations.map((v, i) => (
                            <div key={i} style={{ fontSize: '0.8rem', color: 'var(--k-text-muted)', display: 'flex', gap: '0.5rem', alignItems: 'flex-start', marginBottom: '0.25rem' }}>
                              <ChevronRight size={11} style={{ color: 'var(--k-accent)', flexShrink: 0, marginTop: '2px' }} />{v}
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Decision Conditions */}
                      {governorVerdict.decision_conditions?.length > 0 && (
                        <div style={{ marginBottom: '0.75rem' }}>
                          <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', color: 'var(--k-accent)', marginBottom: '0.4rem', display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <CheckCircle2 size={10} /> Decision Conditions
                          </div>
                          {governorVerdict.decision_conditions.map((c, i) => (
                            <div key={i} style={{ fontSize: '0.8rem', color: 'var(--k-text-muted)', display: 'flex', gap: '0.5rem', alignItems: 'flex-start', marginBottom: '0.25rem' }}>
                              <ChevronRight size={11} style={{ color: 'var(--k-accent)', flexShrink: 0, marginTop: '2px' }} />{c}
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Failure Triggers */}
                      {governorVerdict.failure_triggers?.length > 0 && (
                        <div style={{ marginBottom: '0.75rem' }}>
                          <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', color: 'var(--k-danger)', marginBottom: '0.4rem', display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <XCircle size={10} /> Failure Triggers
                          </div>
                          {governorVerdict.failure_triggers.map((t, i) => (
                            <div key={i} style={{ fontSize: '0.8rem', color: 'var(--k-text-muted)', display: 'flex', gap: '0.5rem', alignItems: 'flex-start', marginBottom: '0.25rem' }}>
                              <AlertTriangle size={11} style={{ color: 'var(--k-danger)', flexShrink: 0, marginTop: '2px' }} />{t}
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Monitoring Requirements */}
                      {governorVerdict.monitoring_requirements?.length > 0 && (
                        <div style={{ marginBottom: '0.75rem' }}>
                          <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', color: 'var(--k-warning)', marginBottom: '0.4rem', display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <Activity size={10} /> Monitoring Requirements
                          </div>
                          {governorVerdict.monitoring_requirements.map((m, i) => (
                            <div key={i} style={{ fontSize: '0.8rem', color: 'var(--k-text-muted)', display: 'flex', gap: '0.5rem', alignItems: 'flex-start', marginBottom: '0.25rem' }}>
                              <ChevronRight size={11} style={{ color: 'var(--k-warning)', flexShrink: 0, marginTop: '2px' }} />{m}
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Rationale */}
                      <div style={{ fontSize: '0.82rem', color: 'var(--k-text-muted)', lineHeight: 1.7, borderTop: '1px solid var(--k-border)', paddingTop: '0.75rem', fontStyle: 'italic', marginBottom: '0.75rem' }}>
                        {governorVerdict.governor_rationale}
                      </div>

                      {/* Lock Concept — freezes this verdict into a reusable institutional pattern.
                          A NO-GO is a dead end, not a pattern, so locking is disabled for it. */}
                      {!conceptLock && (
                        <>
                          <button
                            className="korum-button"
                            style={{ width: '100%', backgroundColor: 'rgba(212,175,55,0.15)', color: 'var(--k-accent)', border: '1px solid rgba(212,175,55,0.5)', boxShadow: 'none' }}
                            onClick={handleLockConcept}
                            disabled={isLocking || governorVerdict.final_decision === 'NO-GO'}
                            title={governorVerdict.final_decision === 'NO-GO' ? 'NO-GO decisions cannot be locked — they are not approved patterns.' : undefined}
                          >
                            {isLocking ? (
                              <><Activity size={14} style={{ animation: 'pulse 1s infinite' }} /> Locking Concept...</>
                            ) : (
                              <><FileCheck size={14} /> {governorVerdict.final_decision === 'NO-GO' ? 'Cannot Lock (NO-GO)' : 'Lock Concept'}</>
                            )}
                          </button>
                          {lockError && (
                            <div style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: 'var(--k-danger)' }}>{lockError}</div>
                          )}
                        </>
                      )}

                      {conceptLock && (
                        <motion.div
                          initial={{ opacity: 0, y: 6 }}
                          animate={{ opacity: 1, y: 0 }}
                          style={{ marginBottom: '0.75rem', padding: '1rem', borderRadius: '8px', backgroundColor: 'rgba(212,175,55,0.06)', border: '1px solid rgba(212,175,55,0.35)' }}
                        >
                          <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--k-accent)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <FileCheck size={11} /> Concept Lock — {conceptLock.status}
                          </div>
                          <div style={{ fontSize: '0.85rem', color: 'var(--k-text-main)', fontWeight: 600, marginBottom: '0.6rem' }}>
                            {conceptLock.core_thesis}
                          </div>
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.6rem', fontSize: '0.78rem', color: 'var(--k-text-muted)' }}>
                            <div><strong style={{ color: 'var(--k-text-main)' }}>Supporting Assumptions:</strong> {conceptLock.supporting_assumptions.length || 'None'}</div>
                            <div><strong style={{ color: 'var(--k-text-main)' }}>Risks Accepted:</strong> {conceptLock.risks.length || 'None'}</div>
                            <div><strong style={{ color: 'var(--k-text-main)' }}>Open Unknowns:</strong> {conceptLock.open_unknowns.length || 'None'}</div>
                          </div>

                          {/* Governance Conditions — kept as 4 distinct rows, not one combined count:
                              each answers a different question for a different downstream consumer
                              (approval gate / pre-execution gate / reversal trigger / Watchtower hook). */}
                          <div style={{ marginTop: '0.6rem', paddingTop: '0.6rem', borderTop: '1px solid rgba(212,175,55,0.2)' }}>
                            <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--k-accent)', marginBottom: '0.4rem' }}>
                              Governance Conditions
                            </div>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', fontSize: '0.78rem', color: 'var(--k-text-muted)' }}>
                              <div><strong style={{ color: 'var(--k-text-main)' }}>Decision Conditions:</strong> {conceptLock.governance_conditions.decision_conditions.length || 'None'}</div>
                              <div><strong style={{ color: 'var(--k-text-main)' }}>Required Validations:</strong> {conceptLock.governance_conditions.required_validations.length || 'None'}</div>
                              <div><strong style={{ color: 'var(--k-text-main)' }}>Failure Triggers:</strong> {conceptLock.governance_conditions.failure_triggers.length || 'None'}</div>
                              <div><strong style={{ color: 'var(--k-text-main)' }}>Monitoring Requirements:</strong> {conceptLock.governance_conditions.monitoring_requirements.length || 'None'}</div>
                            </div>
                          </div>

                          <div style={{ fontSize: '0.72rem', color: 'var(--k-text-muted)', marginTop: '0.5rem' }}>{conceptLock.graph_status}</div>
                        </motion.div>
                      )}

                      {/* Push to KorumOS / Send to Anchor */}
                      <div style={{ display: 'flex', gap: '0.75rem' }}>
                        <button
                          className="korum-button"
                          style={{ flex: 1 }}
                          onClick={handlePushToKorum}
                          disabled={isPushing}
                        >
                          {isPushing ? (
                            <><Activity size={14} style={{ animation: 'pulse 1s infinite' }} /> Pushing to KorumOS...</>
                          ) : (
                            <><Send size={14} /> Push to KorumOS</>
                          )}
                        </button>
                        <button
                          className="korum-button"
                          style={{ flex: 1, backgroundColor: 'rgba(94,154,255,0.12)', color: '#5e9aff', border: '1px solid rgba(94,154,255,0.4)', boxShadow: 'none' }}
                          onClick={handleSendToAnchor}
                          disabled={isSendingToAnchor || !conceptLock}
                          title={!conceptLock ? 'Lock the concept first — ANCHOR stores approved patterns, not raw decisions.' : undefined}
                        >
                          {isSendingToAnchor ? (
                            <><Activity size={14} style={{ animation: 'pulse 1s infinite' }} /> Sending to ANCHOR...</>
                          ) : (
                            <><Anchor size={14} /> Send to ANCHOR</>
                          )}
                        </button>
                      </div>

                      {anchorResult && (
                        <motion.div
                          initial={{ opacity: 0, y: 6 }}
                          animate={{ opacity: 1, y: 0 }}
                          style={{ marginTop: '0.75rem', padding: '1rem', borderRadius: '8px',
                            backgroundColor: anchorResult.status === 'error' ? 'rgba(201,74,74,0.06)' : 'rgba(94,154,255,0.06)',
                            border: `1px solid ${anchorResult.status === 'error' ? 'var(--k-danger)' : 'rgba(94,154,255,0.4)'}` }}
                        >
                          {(anchorResult.status === 'ingested' || anchorResult.status === 'submitted' || anchorResult.status === 'duplicate') && (
                            <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: '#5e9aff', display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <CheckCircle2 size={11} />
                              {anchorResult.status === 'duplicate' ? 'Already Archived in ANCHOR' : 'Archived to ANCHOR Memory'}
                            </div>
                          )}

                          {anchorResult.status === 'manual_required' && (
                            <>
                              <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: '#5e9aff', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <Info size={11} /> Manual Ingest Required
                              </div>
                              <div style={{ fontSize: '0.82rem', color: 'var(--k-text-muted)', marginBottom: '0.75rem' }}>
                                {anchorResult.message || 'ANCHOR_API_KEY not configured. Copy the package and ingest it into ANCHOR manually.'}
                              </div>
                              <button className="korum-button secondary" onClick={handleCopyAnchorPackage}>
                                <Copy size={13} /> {copyConfirmed ? 'Copied!' : 'Copy Package'}
                              </button>
                              <pre style={{ marginTop: '0.75rem', maxHeight: '160px', overflowY: 'auto', fontSize: '0.72rem', color: 'var(--k-text-muted)', whiteSpace: 'pre-wrap', background: 'rgba(0,0,0,0.25)', padding: '0.75rem', borderRadius: '6px', border: '1px solid var(--k-border)' }}>
                                {anchorResult.query_package}
                              </pre>
                            </>
                          )}

                          {anchorResult.status === 'error' && (
                            <>
                              <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--k-danger)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <AlertCircle size={11} /> Send to ANCHOR Failed
                              </div>
                              <div style={{ fontSize: '0.82rem', color: 'var(--k-text-muted)' }}>
                                {anchorResult.detail || 'Unknown error.'}
                              </div>
                              {anchorResult.query_package && (
                                <button className="korum-button secondary" style={{ marginTop: '0.5rem' }} onClick={handleCopyAnchorPackage}>
                                  <Copy size={13} /> {copyConfirmed ? 'Copied!' : 'Copy Package Anyway'}
                                </button>
                              )}
                            </>
                          )}
                        </motion.div>
                      )}

                      {pushResult && (
                        <motion.div
                          initial={{ opacity: 0, y: 6 }}
                          animate={{ opacity: 1, y: 0 }}
                          style={{ marginTop: '0.75rem', padding: '1rem', borderRadius: '8px',
                            backgroundColor: pushResult.status === 'submitted' ? 'rgba(43,147,72,0.06)' : pushResult.status === 'error' ? 'rgba(201,74,74,0.06)' : 'rgba(212,175,55,0.05)',
                            border: `1px solid ${pushResult.status === 'submitted' ? 'var(--k-success)' : pushResult.status === 'error' ? 'var(--k-danger)' : 'rgba(212,175,55,0.3)'}` }}
                        >
                          {pushResult.status === 'submitted' && (
                            <>
                              <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--k-success)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <CheckCircle2 size={11} /> Submitted to KorumOS Neural Council
                              </div>
                              <div style={{ fontSize: '0.85rem', color: 'var(--k-text-main)' }}>
                                Job ID: <strong>{pushResult.job_id || 'pending'}</strong>
                              </div>
                              {pushResult.poll_url && (
                                <div style={{ fontSize: '0.8rem', color: 'var(--k-text-muted)', marginTop: '0.25rem' }}>
                                  Poll: {pushResult.poll_url}
                                </div>
                              )}
                            </>
                          )}

                          {pushResult.status === 'manual_required' && (
                            <>
                              <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--k-accent)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <Info size={11} /> Manual Submission Required
                              </div>
                              <div style={{ fontSize: '0.82rem', color: 'var(--k-text-muted)', marginBottom: '0.75rem' }}>
                                {pushResult.message || 'KORUMOS_API_KEY not configured. Copy the query package and paste it into KorumOS.'}
                              </div>
                              <div style={{ display: 'flex', gap: '0.5rem' }}>
                                <button
                                  className="korum-button secondary"
                                  style={{ flex: 1 }}
                                  onClick={handleCopyQueryPackage}
                                >
                                  <Copy size={13} /> {copyConfirmed ? 'Copied!' : 'Copy Query Package'}
                                </button>
                                <a
                                  href={pushResult.korumos_url || 'https://korum-os.com'}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="korum-button secondary"
                                  style={{ flex: 1, textDecoration: 'none', textAlign: 'center', justifyContent: 'center' }}
                                >
                                  <ExternalLink size={13} /> Open KorumOS
                                </a>
                              </div>
                              <pre style={{ marginTop: '0.75rem', maxHeight: '160px', overflowY: 'auto', fontSize: '0.72rem', color: 'var(--k-text-muted)', whiteSpace: 'pre-wrap', background: 'rgba(0,0,0,0.25)', padding: '0.75rem', borderRadius: '6px', border: '1px solid var(--k-border)' }}>
                                {pushResult.query_package}
                              </pre>
                            </>
                          )}

                          {pushResult.status === 'error' && (
                            <>
                              <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--k-danger)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <AlertCircle size={11} /> Push Failed
                              </div>
                              <div style={{ fontSize: '0.82rem', color: 'var(--k-text-muted)' }}>
                                {pushResult.detail || 'Unknown error.'}
                              </div>
                              {pushResult.query_package && (
                                <>
                                  <button
                                    className="korum-button secondary"
                                    style={{ marginTop: '0.5rem' }}
                                    onClick={handleCopyQueryPackage}
                                  >
                                    <Copy size={13} /> {copyConfirmed ? 'Copied!' : 'Copy Query Package Anyway'}
                                  </button>
                                  <pre style={{ marginTop: '0.75rem', maxHeight: '160px', overflowY: 'auto', fontSize: '0.72rem', color: 'var(--k-text-muted)', whiteSpace: 'pre-wrap', background: 'rgba(0,0,0,0.25)', padding: '0.75rem', borderRadius: '6px', border: '1px solid var(--k-border)' }}>
                                    {pushResult.query_package}
                                  </pre>
                                </>
                              )}
                            </>
                          )}
                        </motion.div>
                      )}

                      {/* Concept Lock Preview — Test Harness, not Foundry's real Forge.
                          Scoped deliberately narrow: planning artifacts only, no code/repo/deploy.
                          Tests one handoff — can a locked Concept Lock become an actionable
                          implementation blueprint? Gated on a lock exactly like Send to ANCHOR. */}
                      <div style={{ marginTop: '1rem', padding: '1rem', backgroundColor: 'rgba(94,154,255,0.04)', border: '1px solid rgba(94,154,255,0.25)', borderRadius: '8px' }}>
                        <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: '#5e9aff', marginBottom: '0.4rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <Network size={11} /> Concept Lock Preview (Test Harness — Not Real Forge)
                        </div>
                        <div style={{ fontSize: '0.72rem', color: 'var(--k-text-muted)', marginBottom: '0.75rem', fontStyle: 'italic' }}>
                          {buildBlueprint?.note || "Quick sanity check of this Concept Lock's contents — not a build plan. The real build happens in Foundry's Forge."}
                        </div>
                        <button
                          className="korum-button"
                          style={{ width: '100%', backgroundColor: 'rgba(94,154,255,0.12)', color: '#5e9aff', border: '1px solid rgba(94,154,255,0.4)', boxShadow: 'none' }}
                          onClick={handleGenerateBlueprint}
                          disabled={isGeneratingBlueprint || !conceptLock || !conceptLock.id}
                          title={
                            !conceptLock
                              ? 'Lock the concept first — Forge plans from approved patterns, not raw decisions.'
                              : !conceptLock.id
                                ? "Preview unavailable — this Concept Lock wasn't persisted (Neo4j was offline when it was locked)."
                                : undefined
                          }
                        >
                          {isGeneratingBlueprint ? (
                            <><Activity size={14} style={{ animation: 'pulse 1s infinite' }} /> Generating Preview...</>
                          ) : (
                            <><FileCheck size={14} /> Generate Preview Blueprint</>
                          )}
                        </button>
                        {blueprintError && (
                          <div style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: 'var(--k-danger)' }}>{blueprintError}</div>
                        )}

                        {buildBlueprint && (
                          <motion.div
                            initial={{ opacity: 0, y: 6 }}
                            animate={{ opacity: 1, y: 0 }}
                            style={{ marginTop: '0.75rem' }}
                          >
                            <div style={{ marginBottom: '0.75rem' }}>
                              <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', color: '#5e9aff', marginBottom: '0.3rem' }}>Product Brief</div>
                              <div style={{ fontSize: '0.85rem', color: 'var(--k-text-main)' }}>{buildBlueprint.product_brief}</div>
                            </div>
                            <div style={{ marginBottom: '0.75rem' }}>
                              <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', color: '#5e9aff', marginBottom: '0.3rem' }}>Architecture Blueprint</div>
                              <div style={{ fontSize: '0.85rem', color: 'var(--k-text-main)', whiteSpace: 'pre-wrap' }}>{buildBlueprint.architecture_blueprint}</div>
                            </div>

                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '0.75rem' }}>
                              <div>
                                <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', color: '#5e9aff', marginBottom: '0.3rem' }}>Data Model</div>
                                {buildBlueprint.data_model.map((d, i) => (
                                  <div key={i} style={{ fontSize: '0.8rem', color: 'var(--k-text-muted)', display: 'flex', gap: '0.4rem', marginBottom: '0.2rem' }}><ChevronRight size={11} style={{ flexShrink: 0, marginTop: '2px' }} />{d}</div>
                                ))}
                              </div>
                              <div>
                                <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', color: '#5e9aff', marginBottom: '0.3rem' }}>Required Components</div>
                                {buildBlueprint.required_components.map((c, i) => (
                                  <div key={i} style={{ fontSize: '0.8rem', color: 'var(--k-text-muted)', display: 'flex', gap: '0.4rem', marginBottom: '0.2rem' }}><ChevronRight size={11} style={{ flexShrink: 0, marginTop: '2px' }} />{c}</div>
                                ))}
                              </div>
                              <div>
                                <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', color: '#5e9aff', marginBottom: '0.3rem' }}>Dependencies</div>
                                {buildBlueprint.dependencies.map((d, i) => (
                                  <div key={i} style={{ fontSize: '0.8rem', color: 'var(--k-text-muted)', display: 'flex', gap: '0.4rem', marginBottom: '0.2rem' }}><ChevronRight size={11} style={{ flexShrink: 0, marginTop: '2px' }} />{d}</div>
                                ))}
                              </div>
                              <div>
                                <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', color: '#5e9aff', marginBottom: '0.3rem' }}>Validation Gates</div>
                                {buildBlueprint.validation_gates.map((v, i) => (
                                  <div key={i} style={{ fontSize: '0.8rem', color: 'var(--k-text-muted)', display: 'flex', gap: '0.4rem', marginBottom: '0.2rem' }}><ChevronRight size={11} style={{ flexShrink: 0, marginTop: '2px' }} />{v}</div>
                                ))}
                              </div>
                            </div>

                            <div>
                              <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', color: '#5e9aff', marginBottom: '0.3rem' }}>Build Phases</div>
                              {buildBlueprint.build_phases.map((p, i) => (
                                <div key={i} style={{ fontSize: '0.8rem', color: 'var(--k-text-muted)', display: 'flex', gap: '0.4rem', marginBottom: '0.2rem' }}><strong style={{ color: '#5e9aff' }}>{i + 1}.</strong>{p}</div>
                              ))}
                            </div>

                            <div style={{ fontSize: '0.72rem', color: 'var(--k-text-muted)', marginTop: '0.6rem' }}>{buildBlueprint.graph_status}</div>
                          </motion.div>
                        )}
                      </div>
                    </motion.div>
                  )}

                  {/* Graph Injection State */}
                  <div style={{ marginTop: '1rem', padding: '0.75rem', backgroundColor: 'var(--k-surface-hover)', borderRadius: '4px', border: '1px solid var(--k-border)', fontSize: '0.75rem', color: 'var(--k-text-muted)', display: 'flex', alignItems: 'center', gap: '8px' }}>
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
