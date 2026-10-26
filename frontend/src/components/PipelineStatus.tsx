import { useEffect, useState } from "react";

interface Readiness {
  status: "ready" | "degraded";
  checks: Record<string, { status: string; detail: string }>;
  note: string;
}

export function PipelineStatus() {
  const [report, setReport] = useState<Readiness | null>(null);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    let alive = true;
    const check = async () => {
      try {
        const response = await fetch("/api/v1/ready", { signal: controller.signal });
        const data = await response.json();
        if (!data.checks) throw new Error("Unexpected readiness response");
        if (alive) { setReport(data); setOffline(false); }
      } catch {
        if (alive) setOffline(true);
      }
    };
    void check();
    const timer = setInterval(check, 30_000);
    return () => { alive = false; controller.abort(); clearInterval(timer); };
  }, []);

  return (
    <details className="pipeline-status">
      <summary>
        <span className={`status-dot${offline || report?.status === "degraded" ? " status-dot--warning" : ""}`} aria-hidden="true" />
        {offline ? "Backend unreachable" : report ? report.status === "ready" ? "Local services ready" : "Some services need attention" : "Checking local services…"}
        <span className="pipeline-status__hint">Pipeline details</span>
      </summary>
      {report && !offline && <>
        <ul>{Object.entries(report.checks).map(([name, check]) => (
          <li key={name}><strong>{name === "laws" ? "IFAB index" : name === "ai" ? "AI" : "Redis"}</strong><span>{check.detail}</span></li>
        ))}</ul>
        <p>{report.note}</p>
      </>}
      {offline && <p>Start the Flask API on port 8080. The next check runs automatically.</p>}
    </details>
  );
}
