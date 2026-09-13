"use client";

import {
  Activity,
  BarChart3,
  BookOpen,
  Check,
  ChevronRight,
  CircleAlert,
  Copy,
  Database,
  Download,
  Gauge,
  GitBranch,
  Image as ImageIcon,
  Layers3,
  LockKeyhole,
  LoaderCircle,
  Menu,
  RefreshCw,
  Sparkles,
  Square,
  WandSparkles,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { API_BASE, api, type Dashboard, type ProjectDetail, type ProjectSummary } from "../lib/api";

type View = "workbench" | "projects" | "observability";
type Health = Awaited<ReturnType<typeof api.health>>;

const sampleImage = `${API_BASE}/api/v1/assets/interior_design_00008_.png`;

export default function Home() {
  const [view, setView] = useState<View>("workbench");
  const [mobileNav, setMobileNav] = useState(false);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [activeProject, setActiveProject] = useState<ProjectDetail | null>(null);
  const [activeCandidate, setActiveCandidate] = useState(0);
  const [projectName, setProjectName] = useState("");
  const [requirement, setRequirement] = useState("20平米侘寂风客厅，带落地窗、亚麻沙发和柔和自然光，保持通透动线");
  const [candidateCount, setCandidateCount] = useState<1 | 3>(3);
  const [lockedFields, setLockedFields] = useState<string[]>(["room", "style", "area", "layout"]);
  const [jobProgress, setJobProgress] = useState(0);
  const [activeJobId, setActiveJobId] = useState("");
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [feedbackState, setFeedbackState] = useState("");
  const [iterationOpen, setIterationOpen] = useState(false);
  const [iterationInstruction, setIterationInstruction] = useState("保持布局与家具位置，只优化灯光层次和材质质感");

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const [healthData, dashboardData, projectData] = await Promise.all([
        api.health(),
        api.dashboard(),
        api.projects(),
      ]);
      setHealth(healthData);
      setDashboard(dashboardData);
      setProjects(projectData);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "API 未连接");
      setHealth(null);
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function waitForJob(jobId: string) {
    let current = await api.job(jobId);
    for (let attempt = 0; attempt < 600 && !["completed", "failed", "canceled"].includes(current.status); attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      current = await api.job(jobId);
      setJobProgress(current.progress);
    }
    if (current.status === "failed") throw new Error(current.error || "生成任务失败");
    if (current.status === "canceled") throw new Error("生成任务已取消");
    if (current.status !== "completed" || !current.project_id) throw new Error("生成任务等待超时");
    return current;
  }

  async function generate() {
    if (requirement.trim().length < 4) return;
    setLoading(true);
    setError("");
    setJobProgress(0);
    try {
      const job = await api.startJob({
        project_name: projectName,
        requirement,
        candidate_count: candidateCount,
        generate_image: true,
        locked_fields: lockedFields,
      }, crypto.randomUUID());
      setActiveJobId(job.id);
      const current = await waitForJob(job.id);
      const project = await api.project(current.project_id!);
      setActiveProject(project);
      setActiveCandidate(0);
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "生成失败");
    } finally {
      setLoading(false);
      setJobProgress(0);
      setActiveJobId("");
    }
  }

  function toggleLock(field: string) {
    setLockedFields((current) => current.includes(field) ? current.filter((item) => item !== field) : [...current, field]);
  }

  async function submitDecision(decision: "采用" | "迭代" | "淘汰") {
    if (!candidate) return;
    setFeedbackState("saving");
    try {
      await api.feedback({
        candidate_id: candidate.id,
        requirement_score: Math.max(1, Math.round((result?.quality.requirement_coverage ?? 80) / 20)),
        visual_score: Math.max(1, Math.round((result?.visual_quality?.overall ?? result?.quality.overall ?? 80) / 20)),
        feasibility_score: 4,
        decision,
        notes: "Web 工作台快速决策",
      });
      setFeedbackState(decision);
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "反馈保存失败");
      setFeedbackState("");
    }
  }

  async function iterateCandidate() {
    if (!candidate || iterationInstruction.trim().length < 4) return;
    setLoading(true);
    setError("");
    setJobProgress(0);
    try {
      await api.feedback({
        candidate_id: candidate.id,
        requirement_score: Math.max(1, Math.round((result?.quality.requirement_coverage ?? 80) / 20)),
        visual_score: Math.max(1, Math.round((result?.visual_quality?.overall ?? result?.quality.overall ?? 80) / 20)),
        feasibility_score: 4,
        decision: "迭代",
        notes: iterationInstruction.trim(),
      });
      const job = await api.iterate(candidate.id, {
        instruction: iterationInstruction.trim(),
        generate_image: true,
        locked_fields: lockedFields,
      }, crypto.randomUUID());
      setActiveJobId(job.id);
      const current = await waitForJob(job.id);
      const project = await api.project(current.project_id!);
      setActiveProject(project);
      setActiveCandidate(project.candidates.length - 1);
      setIterationOpen(false);
      setFeedbackState("已生成迭代版本");
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "迭代失败");
    } finally {
      setLoading(false);
      setJobProgress(0);
      setActiveJobId("");
    }
  }

  async function cancelActiveJob() {
    if (!activeJobId) return;
    try {
      await api.cancelJob(activeJobId);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "取消任务失败");
    }
  }

  async function openProject(id: number) {
    setLoading(true);
    try {
      const project = await api.project(id);
      setActiveProject(project);
      const selectedIndex = project.candidates.findIndex((item) => item.selected === 1);
      setActiveCandidate(selectedIndex >= 0 ? selectedIndex : 0);
      setProjectName(project.name);
      setRequirement(project.requirement);
      const projectLocks = project.structured_requirement.locked_fields ?? project.candidates[0]?.result.locked_fields;
      if (projectLocks?.length) setLockedFields(projectLocks);
      setIterationOpen(false);
      setView("workbench");
      setMobileNav(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "项目读取失败");
    } finally {
      setLoading(false);
    }
  }

  const candidate = activeProject?.candidates[activeCandidate];
  const result = candidate?.result;
  const imageUrl = candidate?.image_path
    ? `${API_BASE}/api/v1/assets/${candidate.image_path.split(/[\\/]/).pop()}`
    : sampleImage;
  const metrics = useMemo(
    () => [
      { label: "项目", value: dashboard?.projects ?? 0 },
      { label: "候选方案", value: dashboard?.candidates ?? 0 },
      { label: "平均质量", value: dashboard?.auto_score ?? "-" },
      { label: "平均耗时", value: dashboard?.avg_duration ? `${dashboard.avg_duration}s` : "-" },
    ],
    [dashboard],
  );

  const navItems = [
    { id: "workbench" as const, label: "生成工作台", icon: WandSparkles },
    { id: "projects" as const, label: "项目记录", icon: Layers3 },
    { id: "observability" as const, label: "模型运行", icon: Activity },
  ];

  return (
    <main className="app-shell">
      <aside className={`sidebar ${mobileNav ? "open" : ""}`}>
        <div className="brand">
          <div className="brand-mark"><Sparkles size={19} /></div>
          <div><strong>InteriorForge</strong><span>DESIGNOPS AI</span></div>
          <button className="mobile-close icon-button" onClick={() => setMobileNav(false)} title="关闭导航"><X size={18} /></button>
        </div>
        <nav>
          {navItems.map((item) => (
            <button key={item.id} className={view === item.id ? "active" : ""} onClick={() => { setView(item.id); setMobileNav(false); }}>
              <item.icon size={18} />{item.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-status">
          <span className={`status-dot ${health ? "online" : ""}`} />
          <div><strong>{health ? "API 已连接" : "API 未连接"}</strong><span>{health?.llm_backend ?? "等待服务"}</span></div>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <button className="menu-button icon-button" onClick={() => setMobileNav(true)} title="打开导航"><Menu size={20} /></button>
          <div>
            <span className="eyebrow">INTERIORFORGE AI · MODEL OPERATIONS</span>
            <h1>{navItems.find((item) => item.id === view)?.label}</h1>
          </div>
          <button className="icon-button" onClick={() => void refresh()} disabled={refreshing} title="刷新数据">
            <RefreshCw size={18} className={refreshing ? "spin" : ""} />
          </button>
        </header>

        {error && <div className="error-banner"><CircleAlert size={17} /><span>{error}</span><button onClick={() => setError("")} title="关闭"><X size={16} /></button></div>}

        {view === "workbench" && (
          <>
            <section className="metric-strip">
              {metrics.map((metric) => <div key={metric.label}><span>{metric.label}</span><strong>{metric.value}</strong></div>)}
            </section>
            <section className="workbench-grid">
              <div className="composer">
                <div className="section-heading"><div><span className="section-index">01</span><h2>设计任务</h2></div><Database size={18} /></div>
                <label>项目名称<input value={projectName} onChange={(event) => setProjectName(event.target.value)} placeholder="自动按风格与空间命名" /></label>
                <label className="grow">空间需求<textarea value={requirement} onChange={(event) => setRequirement(event.target.value)} /></label>
                <div className="lock-section">
                  <span className="field-label"><LockKeyhole size={14} />锁定约束</span>
                  <div className="lock-grid">
                    {[["room", "空间"], ["style", "风格"], ["area", "面积"], ["layout", "布局"], ["materials", "材质"], ["furniture", "家具"], ["lighting", "灯光"]].map(([field, label]) => (
                      <label key={field}><input type="checkbox" checked={lockedFields.includes(field)} onChange={() => toggleLock(field)} /><span>{label}</span></label>
                    ))}
                  </div>
                </div>
                <div className="control-row">
                  <div><span className="field-label">候选数量</span><div className="segmented"><button className={candidateCount === 1 ? "selected" : ""} onClick={() => setCandidateCount(1)}>1 个</button><button className={candidateCount === 3 ? "selected" : ""} onClick={() => setCandidateCount(3)}>3 个</button></div></div>
                  <span className="api-image-badge"><ImageIcon size={16} />API 生图 · 预计 ${((health?.image_estimated_cost_usd ?? 0) * candidateCount).toFixed(4)}</span>
                </div>
                <button className="primary-button" onClick={() => void generate()} disabled={loading || requirement.trim().length < 4}>
                  {loading ? <LoaderCircle className="spin" size={18} /> : <Sparkles size={18} />}{loading ? `正在生成 ${jobProgress}%` : "生成候选方案"}
                </button>
                {loading && <div className="active-job"><div className="job-progress"><i style={{ width: `${jobProgress}%` }} /></div><button onClick={() => void cancelActiveJob()} title="取消当前任务"><Square size={13} />取消任务</button></div>}
              </div>

              <div className="result-pane">
                <div className="section-heading"><div><span className="section-index">02</span><h2>方案检查</h2></div><div className="result-tools"><span className="mode-badge">{result?.generation_mode ?? "SAMPLE"}</span>{activeProject && <a className="icon-button small" href={api.reportUrl(activeProject.id)} title="下载项目报告"><Download size={15} /></a>}</div></div>
                {activeProject ? (
                  <div className="comparison-grid">
                    {activeProject.candidates.map((item, index) => {
                      const filename = item.image_path?.split(/[\\/]/).pop();
                      return <button key={item.id} className={activeCandidate === index ? "selected" : ""} onClick={() => { setActiveCandidate(index); setFeedbackState(""); }}>
                        <div>{filename ? <img src={`${API_BASE}/api/v1/assets/${filename}`} alt={`候选 V${item.version}`} /> : <span className="image-empty"><ImageIcon size={24} /></span>}</div>
                        <span>{item.parent_candidate_id ? <GitBranch size={10} /> : null}V{item.version} · {item.variant}</span><strong>{item.result.decision_score ?? item.result.quality.overall}<small>/100</small></strong>
                      </button>;
                    })}
                  </div>
                ) : (
                  <div className="visual-stage"><img src={imageUrl} alt="室内设计候选效果" /><div className="visual-caption"><span>历史作品样本</span><strong>86<small>/100</small></strong></div></div>
                )}
                {result?.image?.success === false && result.image.error && (
                  <div className="image-status"><CircleAlert size={15} /><span>图片未生成：{result.image.error}</span></div>
                )}
                <div className="score-grid">
                  <Score label="需求覆盖" value={result?.quality.requirement_coverage ?? 92} />
                  <Score label="意图一致" value={result?.quality.intent_alignment ?? 100} />
                  <Score label="交付完整" value={result?.quality.deliverable_completeness ?? 88} />
                  <Score label="图片结果" value={result ? result.visual_quality?.overall ?? null : 82} />
                </div>
                <div className="prompt-output">
                  <div><span>POSITIVE PROMPT</span><button className="icon-button small" title="复制 Prompt" onClick={async () => { await navigator.clipboard.writeText(result?.positive_prompt ?? "wabi-sabi living room, natural linen, warm daylight, balanced circulation, photorealistic interior rendering"); setCopied(true); setTimeout(() => setCopied(false), 1400); }}>{copied ? <Check size={15} /> : <Copy size={15} />}</button></div>
                  <p>{result?.positive_prompt ?? "wabi-sabi living room, natural linen, warm daylight, balanced circulation, photorealistic interior rendering"}</p>
                </div>
                <div className="citation-row"><BookOpen size={16} /><span>{result?.rag_citations.length ?? 4} 条知识引用</span><span>{result?.timings.total ? `${result.timings.total}s` : "离线样本"}</span></div>
                {candidate && <div className="decision-actions"><button onClick={() => void submitDecision("采用")}><Check size={15} />采用</button><button onClick={() => setIterationOpen((current) => !current)}><RefreshCw size={15} />迭代</button><button onClick={() => void submitDecision("淘汰")}><X size={15} />淘汰</button><span>{feedbackState && feedbackState !== "saving" ? `已记录：${feedbackState}` : ""}</span></div>}
                {candidate && iterationOpen && <div className="iteration-panel"><label>迭代要求<textarea value={iterationInstruction} onChange={(event) => setIterationInstruction(event.target.value)} /></label><div><span><LockKeyhole size={13} />继承当前锁定约束</span><button onClick={() => void iterateCandidate()} disabled={loading || iterationInstruction.trim().length < 4}>{loading ? <LoaderCircle className="spin" size={14} /> : <GitBranch size={14} />}生成新版本</button></div></div>}
              </div>
            </section>
          </>
        )}

        {view === "projects" && (
          <section className="records-view">
            <div className="records-head"><div><span className="eyebrow">VERSION HISTORY</span><h2>最近项目</h2></div><span>{projects.length} 个项目</span></div>
            <div className="records-table">
              <div className="table-row table-header"><span>项目</span><span>状态</span><span>候选</span><span>最高分</span><span>更新时间</span><span /></div>
              {projects.length === 0 ? <div className="empty-state"><Layers3 size={28} /><strong>暂无项目记录</strong></div> : projects.map((project) => (
                <button className="table-row" key={project.id} onClick={() => void openProject(project.id)}>
                  <strong>{project.name}</strong><span className="status-pill">{project.status}</span><span>{project.candidate_count}</span><span>{project.best_score ?? "-"}</span><span>{project.updated_at.replace("T", " ").slice(0, 16)}</span><ChevronRight size={17} />
                </button>
              ))}
            </div>
          </section>
        )}

        {view === "observability" && (
          <section className="operations-view">
            <div className="operation-summary">
              <div className="operation-icon"><Activity size={24} /></div>
              <div><span className="eyebrow">RUNTIME STATUS</span><h2>{health ? "模型链路运行正常" : "等待 API 服务"}</h2><p>{health?.observability.active ? "Phoenix Trace 已启用" : "Phoenix Trace 当前未启用"} · 任务队列 {health?.task_queue.connected ? health.task_queue.backend.toUpperCase() : "OFFLINE"}</p></div>
              <span className={`health-badge ${health ? "healthy" : ""}`}>{health ? "HEALTHY" : "OFFLINE"}</span>
            </div>
            <div className="operation-grid">
              <Operation icon={Database} label="模型网关" value={health?.llm_backend ?? "-"} meta={health?.llm_model ?? "未连接"} />
              <Operation icon={Activity} label="追踪服务" value={health?.observability.active ? "Active" : "Disabled"} meta="Phoenix / OpenTelemetry" />
              <Operation icon={Gauge} label="平均耗时" value={dashboard?.avg_duration ? `${dashboard.avg_duration}s` : "-"} meta="全部生成任务" />
              <Operation icon={BarChart3} label="兜底率" value={`${dashboard?.fallback_rate ?? 0}%`} meta="本地模板调用占比" />
              <Operation icon={ImageIcon} label="出图成功率" value={dashboard?.image_success_rate == null ? "-" : `${dashboard.image_success_rate}%`} meta="API 图片任务" />
              <Operation icon={Gauge} label="估算成本" value={`$${(dashboard?.estimated_cost_usd ?? 0).toFixed(4)}`} meta="按配置单价统计" />
            </div>
          </section>
        )}
      </section>
      {mobileNav && <button className="scrim" onClick={() => setMobileNav(false)} aria-label="关闭导航遮罩" />}
    </main>
  );
}

function Score({ label, value }: { label: string; value: number | null }) {
  const displayValue = value == null ? "未评测" : value;
  const width = value == null ? 0 : Math.min(100, Math.max(0, value));
  return <div><span>{label}</span><strong>{displayValue}</strong><i><b style={{ width: `${width}%` }} /></i></div>;
}

function Operation({ icon: Icon, label, value, meta }: { icon: typeof Activity; label: string; value: string; meta: string }) {
  return <div className="operation-item"><Icon size={20} /><span>{label}</span><strong>{value}</strong><small>{meta}</small></div>;
}
