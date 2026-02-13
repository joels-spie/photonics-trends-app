import { useEffect, useMemo, useState } from "react";
import Plot from "react-plotly.js";
import { getConfig, postJson } from "./api";
import type { AppConfigResponse } from "./types";

type Tab = "Overview" | "Publishers" | "Journals" | "Institutions" | "Emerging Topics" | "Gap Analysis" | "Time-to-Pub";

type AnalyzeResult = Record<string, any>;

const tabs: Tab[] = ["Overview", "Publishers", "Journals", "Institutions", "Emerging Topics", "Gap Analysis", "Time-to-Pub"];

function csvFromRows(rows: Record<string, any>[]): string {
  if (!rows.length) return "";
  const headers = Array.from(new Set(rows.flatMap((r) => Object.keys(r))));
  const lines = [headers.join(",")];
  for (const row of rows) {
    lines.push(headers.map((h) => JSON.stringify(row[h] ?? "")).join(","));
  }
  return lines.join("\n");
}

function download(name: string, content: string, mime: string): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export default function App() {
  const [config, setConfig] = useState<AppConfigResponse | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("Overview");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, AnalyzeResult>>({});

  const [topicKey, setTopicKey] = useState("silicon_photonics");
  const [adHocQuery, setAdHocQuery] = useState("silicon photonics OR photonic integrated circuit");
  const [fromDate, setFromDate] = useState("2018-01-01");
  const [untilDate, setUntilDate] = useState(new Date().toISOString().slice(0, 10));
  const [docTypes, setDocTypes] = useState<string[]>(["journal-article", "proceedings-article"]);
  const [publishers, setPublishers] = useState<string[]>(["SPIE", "IEEE", "Optica"]);
  const [maxRecords, setMaxRecords] = useState(1200);
  const [refreshCache, setRefreshCache] = useState(false);

  useEffect(() => {
    getConfig().then(setConfig).catch((e) => setError(String(e)));
  }, []);

  const basePayload = useMemo(
    () => ({
      topic_key: topicKey || null,
      ad_hoc_query: adHocQuery || null,
      from_pub_date: fromDate,
      until_pub_date: untilDate,
      doc_types: docTypes,
      publishers,
      max_records: maxRecords,
      refresh_cache: refreshCache,
    }),
    [topicKey, adHocQuery, fromDate, untilDate, docTypes, publishers, maxRecords, refreshCache]
  );

  async function run(endpoint: string) {
    setLoading(true);
    setError(null);
    try {
      const payload: Record<string, unknown> = { ...basePayload };
      if (endpoint === "/api/analyze/emerging_topics") {
        delete payload.topic_key;
        payload.max_records_per_topic = Math.max(400, Math.floor(maxRecords / 3));
      }
      if (endpoint === "/api/analyze/gap_analysis") {
        delete payload.topic_key;
        payload.max_records_per_topic = Math.max(400, Math.floor(maxRecords / 3));
        payload.target_publisher = "SPIE";
      }
      if (endpoint === "/api/analyze/compare_publishers") {
        payload.publishers = publishers;
      }
      const result = await postJson<AnalyzeResult>(endpoint, payload);
      setResults((prev) => ({ ...prev, [endpoint]: result }));
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  function endpointForTab(tab: Tab): string {
    if (tab === "Overview") return "/api/analyze/topic";
    if (tab === "Publishers") return "/api/analyze/compare_publishers";
    if (tab === "Journals") return "/api/analyze/topic";
    if (tab === "Institutions") return "/api/analyze/institutions";
    if (tab === "Emerging Topics") return "/api/analyze/emerging_topics";
    if (tab === "Gap Analysis") return "/api/analyze/gap_analysis";
    return "/api/analyze/time_to_pub";
  }

  function copyQuery() {
    navigator.clipboard.writeText(JSON.stringify(basePayload, null, 2));
  }

  function exportConfig() {
    download("query-config.json", JSON.stringify(basePayload, null, 2), "application/json");
  }

  const endpoint = endpointForTab(activeTab);
  const tabResult = results[endpoint];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <h1>Photonics Publishing Intelligence</h1>
        <p className="sub">Crossref-driven trend and competitive dashboard (V1)</p>

        <label>Topic</label>
        <select value={topicKey} onChange={(e) => setTopicKey(e.target.value)}>
          {config?.topics.map((t) => (
            <option key={t.key} value={t.key}>{t.name}</option>
          ))}
        </select>

        <label>Ad-hoc query</label>
        <input value={adHocQuery} onChange={(e) => setAdHocQuery(e.target.value)} />

        <label>Date range</label>
        <div className="row">
          <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
          <input type="date" value={untilDate} onChange={(e) => setUntilDate(e.target.value)} />
        </div>

        <label>Document types</label>
        <div className="row">
          <label><input type="checkbox" checked={docTypes.includes("journal-article")} onChange={() => setDocTypes((prev) => prev.includes("journal-article") ? prev.filter((x) => x !== "journal-article") : [...prev, "journal-article"])} />Journal</label>
          <label><input type="checkbox" checked={docTypes.includes("proceedings-article")} onChange={() => setDocTypes((prev) => prev.includes("proceedings-article") ? prev.filter((x) => x !== "proceedings-article") : [...prev, "proceedings-article"])} />Proceedings</label>
        </div>

        <label>Publishers</label>
        <select multiple value={publishers} onChange={(e) => setPublishers(Array.from(e.target.selectedOptions).map((o) => o.value))}>
          {config?.publishers.map((p) => (
            <option key={p.name} value={p.name}>{p.name}</option>
          ))}
        </select>

        <label>Max records</label>
        <input type="number" min={100} step={100} value={maxRecords} onChange={(e) => setMaxRecords(Number(e.target.value))} />

        <label className="inline"><input type="checkbox" checked={refreshCache} onChange={(e) => setRefreshCache(e.target.checked)} />Refresh cache</label>

        <div className="button-stack">
          <button onClick={() => run(endpoint)}>Run Current Tab</button>
          <button onClick={copyQuery}>Copy Query</button>
          <button onClick={exportConfig}>Export Config</button>
        </div>
      </aside>

      <main className="main-panel">
        <nav className="tabs">
          {tabs.map((tab) => (
            <button key={tab} className={tab === activeTab ? "active" : ""} onClick={() => setActiveTab(tab)}>{tab}</button>
          ))}
        </nav>

        {loading && <p>Loading...</p>}
        {error && <p className="error">{error}</p>}

        {!loading && tabResult && (
          <section>
            <p className="meta">Records: {tabResult.record_count ?? "n/a"} | Cached calls: {tabResult.meta?.cached_responses ?? 0} | Live calls: {tabResult.meta?.live_responses ?? 0} | Last API call: {tabResult.meta?.last_api_call_at ?? "n/a"}</p>
            {tabResult.coverage && (
              <p className="meta">
                Coverage: abstract {(tabResult.coverage.abstract_rate * 100).toFixed(1)}%, affiliation {(tabResult.coverage.affiliation_rate * 100).toFixed(1)}%, accepted-date {(tabResult.coverage.accepted_date_rate * 100).toFixed(1)}%
              </p>
            )}
            {(tabResult.meta?.warnings || []).length > 0 && <p className="warn">{tabResult.meta.warnings.join(" | ")}</p>}

            {activeTab === "Overview" && tabResult.overview && (
              <>
                <h2>Topic Trend</h2>
                <Plot
                  data={[{ x: Object.keys(tabResult.overview.per_year), y: Object.values(tabResult.overview.per_year), type: "scatter", mode: "lines+markers", marker: { color: "#0f766e" } }]}
                  layout={{ title: "Publications per Year", paper_bgcolor: "#f8fafc", plot_bgcolor: "#f8fafc", margin: { t: 40, b: 35, l: 40, r: 20 } }}
                  style={{ width: "100%", height: 320 }}
                />
                <p>CAGR: {tabResult.overview.cagr ? `${(tabResult.overview.cagr * 100).toFixed(1)}%` : "n/a"}</p>
              </>
            )}

            {activeTab === "Publishers" && tabResult.comparison && (
              <>
                <h2>Publisher Market Share</h2>
                <Plot
                  data={Object.entries(tabResult.comparison.market_share).map(([pub, series]) => ({
                    x: Object.keys(series as Record<string, number>),
                    y: Object.values(series as Record<string, number>),
                    type: "scatter",
                    mode: "lines+markers",
                    name: pub,
                  }))}
                  layout={{ title: "Market Share Over Time", yaxis: { tickformat: ".0%" }, paper_bgcolor: "#f8fafc", plot_bgcolor: "#f8fafc" }}
                  style={{ width: "100%", height: 340 }}
                />
              </>
            )}

            {activeTab === "Journals" && tabResult.journals && (
              <>
                <h2>Top Journals</h2>
                <button onClick={() => download("journals.csv", csvFromRows(tabResult.journals.top_journals), "text/csv")}>Export CSV</button>
                <table>
                  <thead><tr><th>Journal</th><th>Count</th></tr></thead>
                  <tbody>
                    {tabResult.journals.top_journals.map((row: any) => (
                      <tr key={row.journal}><td>{row.journal}</td><td>{row.count}</td></tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}

            {activeTab === "Institutions" && tabResult.institutions && (
              <>
                <h2>Top Institutions</h2>
                <button onClick={() => download("institutions.csv", csvFromRows(tabResult.institutions.top_institutions), "text/csv")}>Export CSV</button>
                <table>
                  <thead><tr><th>Institution</th><th>Count</th></tr></thead>
                  <tbody>
                    {tabResult.institutions.top_institutions.map((row: any) => (
                      <tr key={row.institution}><td>{row.institution}</td><td>{row.count}</td></tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}

            {activeTab === "Emerging Topics" && tabResult.result && (
              <>
                <h2>Emerging Topics</h2>
                <button onClick={() => download("emerging_topics.csv", csvFromRows(tabResult.result.ranked_topics), "text/csv")}>Export CSV</button>
                <table>
                  <thead><tr><th>Topic</th><th>Volume</th><th>Growth</th></tr></thead>
                  <tbody>
                    {tabResult.result.ranked_topics.map((row: any) => (
                      <tr key={row.topic_key}><td>{row.topic_name}</td><td>{row.total_volume}</td><td>{row.growth_rate ? `${(row.growth_rate * 100).toFixed(1)}%` : "n/a"}</td></tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}

            {activeTab === "Gap Analysis" && tabResult.result && (
              <>
                <h2>Competitive Gaps</h2>
                <button onClick={() => download("gap_analysis.csv", csvFromRows(tabResult.result.opportunities), "text/csv")}>Export CSV</button>
                <table>
                  <thead><tr><th>Topic</th><th>Growth</th><th>SPIE Share</th><th>Opportunity</th></tr></thead>
                  <tbody>
                    {tabResult.result.opportunities.map((row: any) => (
                      <tr key={row.topic_key}><td>{row.topic_name}</td><td>{(row.overall_growth * 100).toFixed(1)}%</td><td>{(row.target_share * 100).toFixed(1)}%</td><td>{row.opportunity_score.toFixed(2)}</td></tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}

            {activeTab === "Time-to-Pub" && tabResult.time_to_publication && (
              <>
                <h2>Time-to-Publication</h2>
                <p>Created→Published avg days: {tabResult.time_to_publication.metrics.created_to_published_days?.toFixed(1) ?? "n/a"}</p>
                <p>Accepted→Published avg days: {tabResult.time_to_publication.metrics.accepted_to_published_days?.toFixed(1) ?? "n/a"}</p>
                <p>Coverage meter: created {(tabResult.time_to_publication.coverage.created_to_published_rate * 100).toFixed(1)}%, accepted {(tabResult.time_to_publication.coverage.accepted_to_published_rate * 100).toFixed(1)}%</p>
                <Plot
                  data={[
                    {
                      x: Object.keys(tabResult.time_to_publication.trend.created_to_published),
                      y: Object.values(tabResult.time_to_publication.trend.created_to_published),
                      type: "scatter",
                      mode: "lines+markers",
                      name: "Created→Published",
                    },
                    {
                      x: Object.keys(tabResult.time_to_publication.trend.accepted_to_published),
                      y: Object.values(tabResult.time_to_publication.trend.accepted_to_published),
                      type: "scatter",
                      mode: "lines+markers",
                      name: "Accepted→Published",
                    },
                  ]}
                  layout={{ title: "Lag Trend (Days)", paper_bgcolor: "#f8fafc", plot_bgcolor: "#f8fafc" }}
                  style={{ width: "100%", height: 340 }}
                />
              </>
            )}

            <button onClick={() => download(`${activeTab.toLowerCase().replace(/[^a-z]+/g, "_")}.json`, JSON.stringify(tabResult, null, 2), "application/json")}>Export JSON</button>
          </section>
        )}
      </main>
    </div>
  );
}
