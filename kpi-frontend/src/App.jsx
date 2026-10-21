import React, { useState, useEffect, useMemo } from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Line,
  Scatter,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";

/* --- Design Tokens --- */
const C = {
  bg: "#080B10",
  panel: "#0E131C",
  panelHover: "#131A26",
  border: "#1C2433",
  borderBright: "#283447",
  text: "#E6EDF3",
  textDim: "#8B949E",
  textFaint: "#484F58",
  cyan: "#38BDF8",
  violet: "#A78BFA",
  green: "#34D399",
  amber: "#FBBF24",
  red: "#F87171",
  mono: "'JetBrains Mono', 'Fira Code', Menlo, monospace",
  sans: "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
};

const CAT_COLORS = [C.cyan, C.violet, C.amber, C.green, C.red];

/* --- Currency & Number Formatters --- */
const fmtMoney = (v, decimals = true) => {
  if (v === null || v === undefined || isNaN(v)) return "$0";
  const abs = Math.abs(v);
  const sign = v < 0 ? "-" : "";
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `${sign}$${(abs / 1_000).toFixed(decimals ? 1 : 0)}k`;
  return `${sign}$${abs.toLocaleString("en-US", { maximumFractionDigits: decimals ? 2 : 0 })}`;
};

const fmtPct = (v) => {
  if (v === null || v === undefined || isNaN(v)) return "N/A";
  const sign = v > 0 ? "+" : "";
  return `${sign}${Number(v).toFixed(1)}%`;
};

const fmtDate = (str) => {
  if (!str) return "";
  const d = new Date(str);
  if (isNaN(d.getTime())) return str;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
};

const sevColor = (sev) => {
  if (sev === "CRITICAL") return C.red;
  if (sev === "WARNING") return C.amber;
  return C.cyan;
};

/* --- Small Atomic Components --- */
function Panel({ children, style = {} }) {
  return (
    <div
      style={{
        background: C.panel,
        border: `1px solid ${C.border}`,
        borderRadius: 10,
        padding: "16px 20px",
        boxSizing: "border-box",
        ...style,
      }}
    >
      {children}
    </div>
  );
}

function Eyebrow({ children }) {
  return (
    <div
      style={{
        fontFamily: C.mono,
        fontSize: 11,
        color: C.textDim,
        textTransform: "uppercase",
        letterSpacing: "0.08em",
        marginBottom: 10,
      }}
    >
      {children}
    </div>
  );
}

function SeverityBadge({ severity }) {
  const isCrit = severity === "CRITICAL";
  return (
    <span
      style={{
        fontFamily: C.mono,
        fontSize: 10.5,
        fontWeight: 700,
        padding: "2px 8px",
        borderRadius: 4,
        background: isCrit ? "rgba(248, 113, 113, 0.15)" : "rgba(251, 191, 36, 0.15)",
        color: isCrit ? C.red : C.amber,
        border: `1px solid ${isCrit ? "rgba(248, 113, 113, 0.3)" : "rgba(251, 191, 36, 0.3)"}`,
      }}
    >
      {severity}
    </span>
  );
}

function KpiCard({ label, value, sub, subColor = C.textDim, accent = C.cyan }) {
  return (
    <Panel style={{ flex: 1, minWidth: 170, padding: "14px 18px" }}>
      <div style={{ fontFamily: C.mono, fontSize: 11, color: C.textDim, textTransform: "uppercase" }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 700, color: accent, margin: "6px 0 3px 0", letterSpacing: "-0.02em" }}>
        {value}
      </div>
      <div style={{ fontSize: 11.5, color: subColor, fontFamily: C.sans }}>{sub}</div>
    </Panel>
  );
}

function AlertTicker({ alerts = [] }) {
  if (!alerts || alerts.length === 0) {
    return (
      <div
        style={{
          background: "#0D1119",
          border: `1px solid ${C.border}`,
          borderRadius: 8,
          padding: "10px 16px",
          fontFamily: C.mono,
          fontSize: 12,
          color: C.green,
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        <span style={{ width: 8, height: 8, borderRadius: "50%", background: C.green }} />
        ALL SYSTEMS NOMINAL — Trailing metrics and anomaly detectors operating within defined bounds.
      </div>
    );
  }

  const track = [...alerts, ...alerts];
  return (
    <div
      style={{
        background: "#0D1119",
        border: `1px solid ${C.border}`,
        borderRadius: 8,
        overflow: "hidden",
        position: "relative",
      }}
    >
      <div
        className="ticker-track"
        style={{
          display: "flex",
          width: "max-content",
          animation: "ticker-scroll 45s linear infinite",
          padding: "9px 0",
        }}
      >
        {track.map((a, i) => (
          <div
            key={i}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              fontFamily: C.mono,
              fontSize: 12,
              color: C.textDim,
              whiteSpace: "nowrap",
              padding: "0 24px",
              borderRight: `1px solid ${C.border}`,
            }}
          >
            <SeverityBadge severity={a.severity} />
            <span style={{ color: sevColor(a.severity), fontWeight: 600 }}>{a.alert_type.replace(/_/g, " ")}:</span>
            <span>{a.message}</span>
          </div>
        ))}
      </div>
      <style>{`
        @keyframes ticker-scroll {
          from { transform: translateX(0); }
          to   { transform: translateX(-50%); }
        }
        .ticker-track:hover { animation-play-state: paused; }
      `}</style>
    </div>
  );
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div
      style={{
        background: "#0D1119",
        border: `1px solid ${C.borderBright}`,
        borderRadius: 8,
        padding: "10px 14px",
        fontFamily: C.mono,
        fontSize: 12,
        color: C.text,
      }}
    >
      <div style={{ color: C.textFaint, marginBottom: 6, fontWeight: 600 }}>{fmtDate(label)} ({label})</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color, display: "flex", justifyContent: "space-between", gap: 16, margin: "2px 0" }}>
          <span>{p.name}:</span>
          <span style={{ fontWeight: 600 }}>
            {typeof p.value === "number" ? fmtMoney(p.value) : p.value}
          </span>
        </div>
      ))}
    </div>
  );
}

/* ============================================================
   MAIN INTERACTIVE KPI DASHBOARD COMPONENT
   ============================================================ */
export default function KpiDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Functional interactive filters
  const [timeRange, setTimeRange] = useState("90d"); // '30d', '90d', '365d', 'all', '2014', '2013', '2012', '2011'
  const [selectedRegion, setSelectedRegion] = useState("ALL");
  const [selectedCategory, setSelectedCategory] = useState("ALL");

  useEffect(() => {
    fetch("/dashboard_data.json")
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to fetch dashboard_data.json`);
        return res.json();
      })
      .then((payload) => {
        setData(payload);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  // Filter continuous daily dataset according to user selection
  const filteredDaily = useMemo(() => {
    if (!data || !data.kpi_daily) return [];
    let list = [...data.kpi_daily];

    if (timeRange === "30d") {
      list = list.slice(-30);
    } else if (timeRange === "90d") {
      list = list.slice(-90);
    } else if (timeRange === "365d") {
      list = list.slice(-365);
    } else if (["2011", "2012", "2013", "2014"].includes(timeRange)) {
      list = list.filter((d) => d.kpi_date.startsWith(timeRange));
    }

    return list;
  }, [data, timeRange]);

  // Compute metrics specifically for the selected reporting period
  const periodMetrics = useMemo(() => {
    if (!filteredDaily.length) {
      return { revenue: 0, profit: 0, orders: 0, margin: 0, returnRate: 0, activeDays: 0 };
    }
    const revenue = filteredDaily.reduce((acc, d) => acc + (d.revenue || 0), 0);
    const profit = filteredDaily.reduce((acc, d) => acc + (d.profit || 0), 0);
    const orders = filteredDaily.reduce((acc, d) => acc + (d.orders || 0), 0);
    const returnedOrders = filteredDaily.reduce((acc, d) => acc + (d.returned_orders || 0), 0);
    const activeDays = filteredDaily.filter((d) => d.is_active_day === 1).length;

    const margin = revenue > 0 ? (profit / revenue) * 100 : 0;
    const returnRate = orders > 0 ? (returnedOrders / orders) * 100 : 0;

    return { revenue, profit, orders, margin, returnRate, activeDays };
  }, [filteredDaily]);

  // Merge history + forecast for chart visualization
  const chartData = useMemo(() => {
    if (!filteredDaily.length) return [];
    const hist = filteredDaily.map((d) => ({
      date: d.kpi_date,
      revenue: d.revenue,
      revenue_7d_avg: d.revenue_7d_avg,
      anomaly: d.is_anomaly ? d.revenue : null,
      forecast: null,
      lower_bound: null,
      upper_bound: null,
    }));

    // Show 14-day forecast when looking at the latest periods ('30d', '90d', 'all')
    const showForecast = ["30d", "90d", "all"].includes(timeRange) && data?.forecast?.length;
    if (showForecast) {
      const fc = data.forecast.map((f) => ({
        date: f.date,
        revenue: null,
        revenue_7d_avg: null,
        anomaly: null,
        forecast: f.forecast_revenue,
        lower_bound: f.lower_bound,
        upper_bound: f.upper_bound,
      }));
      if (hist.length) {
        fc.unshift({
          ...hist[hist.length - 1],
          forecast: hist[hist.length - 1].revenue,
          lower_bound: hist[hist.length - 1].revenue,
          upper_bound: hist[hist.length - 1].revenue,
        });
      }
      return [...hist, ...fc];
    }

    return hist;
  }, [filteredDaily, data, timeRange]);

  // Filter regional data
  const filteredRegions = useMemo(() => {
    if (!data || !data.region_weekly) return [];
    const maxWeek = data.region_weekly.reduce((m, r) => (r.week > m ? r.week : m), "");
    let list = data.region_weekly.filter((r) => r.week === maxWeek);
    if (selectedRegion !== "ALL") {
      list = list.filter((r) => r.region === selectedRegion);
    }
    return list.sort((a, b) => b.revenue - a.revenue);
  }, [data, selectedRegion]);

  // Filter top products by category selection
  const filteredProducts = useMemo(() => {
    if (!data || !data.top_products) return [];
    let list = [...data.top_products];
    if (selectedCategory !== "ALL") {
      list = list.filter((p) => p.category === selectedCategory);
    }
    return list.slice(0, 8);
  }, [data, selectedCategory]);

  if (loading) {
    return (
      <div style={{ background: C.bg, color: C.text, minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: C.mono }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 18, color: C.cyan, marginBottom: 8 }}>Initializing Analytics Platform...</div>
          <div style={{ fontSize: 12, color: C.textDim }}>Loading pipeline warehouse payload from /dashboard_data.json</div>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div style={{ background: C.bg, color: C.text, minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: C.mono }}>
        <Panel style={{ maxWidth: 500, borderColor: C.red, textAlign: "center" }}>
          <div style={{ fontSize: 16, color: C.red, fontWeight: 700, marginBottom: 8 }}>Dashboard Load Error</div>
          <div style={{ fontSize: 12.5, color: C.textDim, marginBottom: 16 }}>{error}</div>
          <div style={{ fontSize: 11, color: C.textFaint }}>
            Ensure you have run <code>python scheduler/run_pipeline.py</code> to generate the payload.
          </div>
        </Panel>
      </div>
    );
  }

  const { summary, alerts, category_breakdown, metadata } = data;

  return (
    <div
      style={{
        background: C.bg,
        color: C.text,
        fontFamily: C.sans,
        padding: "24px 28px",
        minHeight: "100vh",
        boxSizing: "border-box",
      }}
    >
      {/* --- HEADER --- */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 14, marginBottom: 20 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ width: 10, height: 10, borderRadius: "50%", background: C.green, boxShadow: `0 0 10px ${C.green}` }} />
            <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0, letterSpacing: "-0.01em" }}>
              Business KPI Monitoring &amp; Sales Analytics Platform
            </h1>
          </div>
          <div style={{ fontFamily: C.mono, fontSize: 12, color: C.textDim, marginTop: 6 }}>
            SQLite Warehouse · Recursive CTE Calendar · Window Lag Analytics · Automated Anomaly Alerts
          </div>
        </div>
        <div style={{ fontFamily: C.mono, fontSize: 11.5, color: C.textDim, textAlign: "right" }}>
          <div>LAST PIPELINE RUN</div>
          <div style={{ color: C.cyan, fontWeight: 600 }}>{data.generated_at}</div>
          <div style={{ color: C.textFaint, fontSize: 10.5 }}>{metadata?.scope}</div>
        </div>
      </div>

      {/* --- ALERT TICKER --- */}
      <div style={{ marginBottom: 18 }}>
        <AlertTicker alerts={alerts} />
      </div>

      {/* --- INTERACTIVE FILTER BAR --- */}
      <Panel style={{ marginBottom: 20, padding: "12px 18px", display: "flex", flexWrap: "wrap", gap: 18, alignItems: "center", justifyContent: "space-between", background: "#0B0F17" }}>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 14, alignItems: "center" }}>
          {/* Time Horizon Filter */}
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontFamily: C.mono, fontSize: 11, color: C.textDim }}>PERIOD:</span>
            <div style={{ display: "flex", background: C.panel, borderRadius: 6, border: `1px solid ${C.border}`, padding: 2 }}>
              {[
                { id: "30d", label: "30D" },
                { id: "90d", label: "90D" },
                { id: "365d", label: "1Y" },
                { id: "2014", label: "2014" },
                { id: "2013", label: "2013" },
                { id: "all", label: "ALL" },
              ].map((t) => (
                <button
                  key={t.id}
                  onClick={() => setTimeRange(t.id)}
                  style={{
                    background: timeRange === t.id ? C.borderBright : "transparent",
                    color: timeRange === t.id ? C.text : C.textDim,
                    border: "none",
                    borderRadius: 4,
                    padding: "4px 10px",
                    fontFamily: C.mono,
                    fontSize: 11,
                    cursor: "pointer",
                    fontWeight: timeRange === t.id ? 700 : 500,
                  }}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {/* Region Dropdown Filter */}
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontFamily: C.mono, fontSize: 11, color: C.textDim }}>REGION:</span>
            <select
              value={selectedRegion}
              onChange={(e) => setSelectedRegion(e.target.value)}
              style={{
                background: C.panel,
                color: C.text,
                border: `1px solid ${C.border}`,
                borderRadius: 6,
                padding: "4px 10px",
                fontFamily: C.mono,
                fontSize: 11.5,
                outline: "none",
                cursor: "pointer",
              }}
            >
              <option value="ALL">All Regions</option>
              <option value="Central">Central</option>
              <option value="East">East</option>
              <option value="South">South</option>
              <option value="West">West</option>
            </select>
          </div>

          {/* Category Dropdown Filter */}
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontFamily: C.mono, fontSize: 11, color: C.textDim }}>CATEGORY:</span>
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              style={{
                background: C.panel,
                color: C.text,
                border: `1px solid ${C.border}`,
                borderRadius: 6,
                padding: "4px 10px",
                fontFamily: C.mono,
                fontSize: 11.5,
                outline: "none",
                cursor: "pointer",
              }}
            >
              <option value="ALL">All Categories</option>
              <option value="Technology">Technology</option>
              <option value="Furniture">Furniture</option>
              <option value="Office Supplies">Office Supplies</option>
            </select>
          </div>
        </div>

        {/* Reset Filter Button */}
        {(timeRange !== "90d" || selectedRegion !== "ALL" || selectedCategory !== "ALL") && (
          <button
            onClick={() => {
              setTimeRange("90d");
              setSelectedRegion("ALL");
              setSelectedCategory("ALL");
            }}
            style={{
              background: "rgba(248, 113, 113, 0.1)",
              border: `1px solid rgba(248, 113, 113, 0.3)`,
              color: C.red,
              borderRadius: 6,
              padding: "4px 10px",
              fontFamily: C.mono,
              fontSize: 11,
              cursor: "pointer",
            }}
          >
            Reset Filters
          </button>
        )}
      </Panel>

      {/* --- DYNAMIC KPI SUMMARY CARDS --- */}
      <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginBottom: 20 }}>
        <KpiCard
          label="Period Revenue"
          value={fmtMoney(periodMetrics.revenue)}
          sub={`${periodMetrics.activeDays} active sales days in selection`}
          accent={C.cyan}
        />
        <KpiCard
          label="Period Net Profit"
          value={fmtMoney(periodMetrics.profit)}
          sub={`Margin: ${periodMetrics.margin.toFixed(1)}%`}
          subColor={periodMetrics.profit >= 0 ? C.green : C.red}
          accent={periodMetrics.profit >= 0 ? C.green : C.red}
        />
        <KpiCard
          label="Transactions"
          value={periodMetrics.orders.toLocaleString()}
          sub={`All-Time Total: ${summary?.total_orders?.toLocaleString()} unique orders`}
          accent={C.text}
        />
        <KpiCard
          label="Order Return Rate"
          value={`${periodMetrics.returnRate.toFixed(1)}%`}
          sub={periodMetrics.returnRate > 10 ? "Exceeds 10% operational limit" : "Within target limit (<=10%)"}
          subColor={periodMetrics.returnRate > 10 ? C.amber : C.green}
          accent={periodMetrics.returnRate > 10 ? C.amber : C.green}
        />
        <KpiCard
          label="Active Alerts"
          value={String(alerts?.length || 0)}
          sub={`${alerts?.filter((a) => a.severity === "CRITICAL").length || 0} critical breaches`}
          subColor={alerts?.length ? C.red : C.green}
          accent={alerts?.length ? C.red : C.green}
        />
      </div>

      {/* --- MAIN REVENUE TREND & FORECAST CHART --- */}
      <Panel style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12, flexWrap: "wrap", gap: 8 }}>
          <div>
            <Eyebrow>Daily Revenue Trend · 7-Day Moving Avg · Statistical Anomalies · 14-Day Horizon</Eyebrow>
            <div style={{ fontSize: 11.5, color: C.textDim, fontFamily: C.mono }}>
              Displaying: {filteredDaily.length} calendar days ({filteredDaily[0]?.kpi_date} → {filteredDaily[filteredDaily.length - 1]?.kpi_date})
            </div>
          </div>
          <div style={{ display: "flex", gap: 16, fontFamily: C.mono, fontSize: 11, color: C.textDim }}>
            <span><span style={{ color: C.cyan }}>■</span> Revenue</span>
            <span><span style={{ color: C.textDim }}>---</span> 7d Calendar Avg</span>
            <span><span style={{ color: C.violet }}>---</span> 14d Forecast</span>
            <span><span style={{ color: C.red }}>●</span> Anomaly Dot</span>
          </div>
        </div>

        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart data={chartData} margin={{ top: 8, right: 12, left: -10, bottom: 0 }}>
            <defs>
              <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={C.cyan} stopOpacity={0.25} />
                <stop offset="100%" stopColor={C.cyan} stopOpacity={0.0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke={C.border} vertical={false} />
            <XAxis dataKey="date" tickFormatter={fmtDate} tick={{ fill: C.textFaint, fontSize: 10.5, fontFamily: C.mono }} axisLine={{ stroke: C.border }} tickLine={false} minTickGap={35} />
            <YAxis tickFormatter={(v) => fmtMoney(v, false)} tick={{ fill: C.textFaint, fontSize: 10.5, fontFamily: C.mono }} axisLine={false} tickLine={false} width={58} />
            <Tooltip content={<ChartTooltip />} />
            <Area type="monotone" dataKey="revenue" name="Daily Revenue" stroke={C.cyan} strokeWidth={2} fill="url(#revGrad)" connectNulls dot={false} />
            <Line type="monotone" dataKey="revenue_7d_avg" name="7d Moving Avg" stroke={C.textDim} strokeWidth={1.5} strokeDasharray="3 3" dot={false} connectNulls />
            <Line type="monotone" dataKey="forecast" name="Forecast (Additive Seasonality)" stroke={C.violet} strokeWidth={2} strokeDasharray="5 4" dot={false} connectNulls />
            <Scatter dataKey="anomaly" name="Anomaly (Z-Score / IsoForest)" fill={C.red} shape="circle" />
          </ComposedChart>
        </ResponsiveContainer>
      </Panel>

      {/* --- REGIONAL WEEKLY & CATEGORY SHARE ROW --- */}
      <div style={{ display: "flex", gap: 20, flexWrap: "wrap", marginBottom: 20 }}>
        {/* Region Bar Chart */}
        <Panel style={{ flex: 2, minWidth: 320 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <Eyebrow>Regional Performance · Latest Weekly Snapshot</Eyebrow>
            <span style={{ fontFamily: C.mono, fontSize: 10.5, color: C.textFaint }}>Week of {filteredRegions[0]?.week}</span>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={filteredRegions} margin={{ top: 8, right: 10, left: -12, bottom: 0 }}>
              <CartesianGrid stroke={C.border} vertical={false} />
              <XAxis dataKey="region" tick={{ fill: C.textDim, fontSize: 11.5, fontFamily: C.sans }} axisLine={{ stroke: C.border }} tickLine={false} />
              <YAxis tickFormatter={(v) => fmtMoney(v, false)} tick={{ fill: C.textFaint, fontSize: 10.5, fontFamily: C.mono }} axisLine={false} tickLine={false} width={54} />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload || !payload.length) return null;
                  const item = payload[0].payload;
                  return (
                    <div style={{ background: "#0D1119", border: `1px solid ${C.borderBright}`, borderRadius: 8, padding: "8px 12px", fontFamily: C.mono, fontSize: 12 }}>
                      <div style={{ color: C.text, fontWeight: 700 }}>{item.region} Region</div>
                      <div style={{ color: C.cyan, margin: "2px 0" }}>Revenue: {fmtMoney(item.revenue)}</div>
                      <div style={{ color: item.profit >= 0 ? C.green : C.red }}>Profit: {fmtMoney(item.profit)}</div>
                      <div style={{ color: item.is_partial_week ? C.amber : item.wow_pct < 0 ? C.red : C.green, marginTop: 4 }}>
                        {item.is_partial_week ? "Partial Week (WoW Suppressed)" : `${fmtPct(item.wow_pct)} WoW`}
                      </div>
                    </div>
                  );
                }}
              />
              <Bar dataKey="revenue" radius={[4, 4, 0, 0]}>
                {filteredRegions.map((r, i) => (
                  <Cell
                    key={i}
                    fill={r.is_partial_week ? C.cyan : r.wow_pct < -25 ? C.red : r.wow_pct < 0 ? C.amber : C.cyan}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Panel>

        {/* Category Share Donut */}
        <Panel style={{ flex: 1, minWidth: 260 }}>
          <Eyebrow>Category Contribution &amp; Margins</Eyebrow>
          <ResponsiveContainer width="100%" height={170}>
            <PieChart>
              <Pie
                data={category_breakdown}
                dataKey="revenue"
                nameKey="category"
                innerRadius={48}
                outerRadius={75}
                paddingAngle={4}
                stroke="none"
              >
                {category_breakdown.map((_, i) => (
                  <Cell key={i} fill={CAT_COLORS[i % CAT_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload || !payload.length) return null;
                  const item = payload[0].payload;
                  return (
                    <div style={{ background: "#0D1119", border: `1px solid ${C.borderBright}`, borderRadius: 8, padding: "8px 12px", fontFamily: C.mono, fontSize: 12 }}>
                      <div style={{ color: C.text, fontWeight: 700 }}>{item.category}</div>
                      <div style={{ color: C.cyan }}>{fmtMoney(item.revenue)} ({item.revenue_share_pct}%)</div>
                      <div style={{ color: item.profit_margin_pct >= 10 ? C.green : C.amber }}>
                        Margin: {item.profit_margin_pct}%
                      </div>
                    </div>
                  );
                }}
              />
            </PieChart>
          </ResponsiveContainer>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: 6, justifyContent: "center" }}>
            {category_breakdown.map((c, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 6, fontFamily: C.mono, fontSize: 11, color: C.textDim }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: CAT_COLORS[i % CAT_COLORS.length], display: "inline-block" }} />
                {c.category} ({c.revenue_share_pct}%)
              </div>
            ))}
          </div>
        </Panel>
      </div>

      {/* --- TOP PRODUCTS & ALERT HISTORY ROW --- */}
      <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
        {/* Top Products */}
        <Panel style={{ flex: 1, minWidth: 320 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <Eyebrow>Top Revenue SKUs (DENSE_RANK)</Eyebrow>
            {selectedCategory !== "ALL" && (
              <span style={{ fontFamily: C.mono, fontSize: 10.5, color: C.cyan }}>Filtered: {selectedCategory}</span>
            )}
          </div>
          <div>
            {filteredProducts.map((p, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  gap: 12,
                  padding: "8px 0",
                  borderBottom: i < filteredProducts.length - 1 ? `1px solid ${C.border}` : "none",
                  alignItems: "center",
                }}
              >
                <div style={{ fontSize: 12.5, color: C.textDim, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 260 }}>
                  <span style={{ color: C.textFaint, fontFamily: C.mono, marginRight: 8 }}>
                    #{p.revenue_rank || i + 1}
                  </span>
                  {p.product_name}
                </div>
                <div style={{ textAlign: "right", flexShrink: 0 }}>
                  <div style={{ fontFamily: C.mono, fontSize: 12.5, color: C.cyan }}>{fmtMoney(p.revenue)}</div>
                  <div style={{ fontFamily: C.mono, fontSize: 10, color: p.profit_margin_pct >= 0 ? C.green : C.red }}>
                    {p.profit_margin_pct}% margin
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Panel>

        {/* Operational Alert History */}
        <Panel style={{ flex: 1, minWidth: 320 }}>
          <Eyebrow>Operational Alert History · Latest Evaluation</Eyebrow>
          <div style={{ maxHeight: 310, overflowY: "auto" }}>
            {(!alerts || alerts.length === 0) && (
              <div style={{ color: C.green, fontFamily: C.mono, fontSize: 12.5, padding: "12px 0" }}>
                No active threshold breaches or statistical anomalies.
              </div>
            )}
            {alerts &&
              alerts.map((a, i) => (
                <div
                  key={i}
                  style={{
                    display: "flex",
                    gap: 10,
                    padding: "9px 0",
                    borderBottom: i < alerts.length - 1 ? `1px solid ${C.border}` : "none",
                    alignItems: "flex-start",
                  }}
                >
                  <SeverityBadge severity={a.severity} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontFamily: C.mono, fontSize: 11.5, color: sevColor(a.severity), fontWeight: 600 }}>
                      {a.alert_type.replace(/_/g, " ")} · Trigger: {a.metric_value}
                    </div>
                    <div style={{ fontSize: 12, color: C.textDim, marginTop: 2, lineHeight: 1.4 }}>{a.message}</div>
                  </div>
                </div>
              ))}
          </div>
        </Panel>
      </div>

      {/* --- FOOTER & METHODOLOGY DISCLOSURES --- */}
      <div style={{ marginTop: 24, paddingTop: 16, borderTop: `1px solid ${C.border}`, fontFamily: C.mono, fontSize: 11, color: C.textFaint, textAlign: "center", lineHeight: 1.6 }}>
        <div>
          Data Source: Superstore US Commercial Sales (10K facts, 2011–2014) · Pipeline Orchestrator: <code>scheduler/run_pipeline.py</code>
        </div>
        <div style={{ marginTop: 4 }}>
          Methodology: Continuous Daily Calendar (zero-filled) · Bounded Order Return Rates (0–100%) · Incomplete-week anomaly suppression · Holt-Winters additive weekly seasonality
        </div>
      </div>
    </div>
  );
}
