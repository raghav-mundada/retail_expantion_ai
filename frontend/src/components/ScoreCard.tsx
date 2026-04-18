"use client";
import type { AnalysisResult } from "@/lib/api";
import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
  Tooltip,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
} from "recharts";

interface ScoreCardProps {
  result: AnalysisResult;
  brand: "walmart" | "target";
}

function getRankColor(score: number): string {
  if (score >= 85) return "#10b981";
  if (score >= 70) return "#3b82f6";
  if (score >= 55) return "#f59e0b";
  return "#ef4444";
}

function getDimColor(score: number): string {
  if (score >= 75) return "#10b981";
  if (score >= 55) return "#3b82f6";
  if (score >= 35) return "#f59e0b";
  return "#ef4444";
}

function formatRevenue(n: number): string {
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  return `$${(n / 1e3).toFixed(0)}K`;
}

function formatVisits(n: number): string {
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return String(n);
}

export default function ScoreCard({ result, brand }: ScoreCardProps) {
  const { score, demographics, competitors, simulation, neighborhood, brand_fit } = result;
  const rankColor = getRankColor(score.total_score);

  const radarData = [
    { dim: "Demand", value: score.demand_score },
    { dim: "Competition", value: score.competition_score },
    { dim: "Access", value: score.accessibility_score },
    { dim: "Neighborhood", value: score.neighborhood_score },
    { dim: "Brand Fit", value: score.brand_fit_score },
    { dim: "Risk", value: score.risk_score },
  ];

  const forecastData = [
    { month: "Open", revenue: simulation.predicted_annual_revenue_usd * 0.55 / 12 },
    { month: "3mo", revenue: simulation.predicted_annual_revenue_usd * 0.75 / 12 },
    { month: "6mo", revenue: simulation.predicted_annual_revenue_usd * 0.88 / 12 },
    { month: "12mo", revenue: simulation.predicted_annual_revenue_usd / 12 },
    { month: "18mo", revenue: simulation.predicted_annual_revenue_usd * 1.08 / 12 },
    { month: "24mo", revenue: simulation.predicted_annual_revenue_usd * 1.15 / 12 },
  ];

  const dimensions = [
    { label: "Market Demand", key: "demand_score", score: score.demand_score },
    { label: "Competitive Position", key: "competition_score", score: score.competition_score },
    { label: "Accessibility", key: "accessibility_score", score: score.accessibility_score },
    { label: "Neighborhood Quality", key: "neighborhood_score", score: score.neighborhood_score },
    { label: "Brand Fit", key: "brand_fit_score", score: score.brand_fit_score },
    { label: "Risk Profile", key: "risk_score", score: score.risk_score },
  ];

  const brandColor = brand === "walmart" ? "#004c91" : "#cc0000";

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "auto" }}>
      {/* Score Header */}
      <div className="score-header">
        <div style={{ display: "flex", align: "flex-start", justifyContent: "space-between" }}>
          <div>
            <div className="score-big">{score.total_score.toFixed(0)}</div>
            <div style={{ display: "flex", gap: 6, alignItems: "center", marginTop: 4 }}>
              <span
                className="score-rank-badge"
                style={{
                  background: `${rankColor}20`,
                  color: rankColor,
                  border: `1px solid ${rankColor}40`,
                }}
              >
                {score.rank_label}
              </span>
              <span className="placer-badge">PLACER.AI ✓</span>
            </div>
            <div className="score-label" style={{ marginTop: 6, fontSize: 11, color: "#7a9ab8" }}>
              {result.address_label}
            </div>
          </div>

          {/* Mini radar */}
          <div style={{ width: 110, height: 100, flexShrink: 0 }}>
            <RadarChart
              cx={55}
              cy={50}
              outerRadius={35}
              width={110}
              height={100}
              data={radarData}
            >
                <PolarGrid stroke="rgba(255,255,255,0.06)" />
                <PolarAngleAxis
                  dataKey="dim"
                  tick={{ fontSize: 7, fill: "#3d5a73" }}
                />
                <Radar
                  dataKey="value"
                  stroke="#00d4ff"
                  fill="#00d4ff"
                  fillOpacity={0.15}
                  strokeWidth={1.5}
                />
              </RadarChart>
          </div>
        </div>

        {/* Brand recommendation */}
        <div
          style={{
            marginTop: 10,
            padding: "8px 10px",
            background: `rgba(${brand === "walmart" ? "0,76,145" : "204,0,0"},0.12)`,
            border: `1px solid rgba(${brand === "walmart" ? "0,76,145" : "204,0,0"},0.3)`,
            borderRadius: 6,
            fontSize: 11,
            color: brand === "walmart" ? "#5aa3e8" : "#f87171",
          }}
        >
          <strong>{brand === "walmart" ? "🔵 Walmart" : "🔴 Target"}</strong> ·{" "}
          {brand_fit.recommended_format}
        </div>
      </div>

      {/* Dimension bars */}
      <div className="dimensions">
        {dimensions.map(({ label, score: dimScore }) => (
          <div key={label} className="dimension-row">
            <div className="dimension-label">
              <span>{label}</span>
              <span className="dimension-score">{dimScore.toFixed(0)}</span>
            </div>
            <div className="dimension-bar">
              <div
                className="dimension-fill"
                style={{
                  width: `${dimScore}%`,
                  background: getDimColor(dimScore),
                }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Key metrics */}
      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-label">Year-1 Revenue</div>
          <div className="metric-value" style={{ color: "#10b981" }}>
            {formatRevenue(simulation.predicted_annual_revenue_usd)}
          </div>
          <div className="metric-sub">
            {formatRevenue(simulation.confidence_interval_low)}–
            {formatRevenue(simulation.confidence_interval_high)} range
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Monthly Visits</div>
          <div className="metric-value">{formatVisits(simulation.predicted_monthly_visits)}</div>
          <div className="metric-sub">{simulation.pct_will_visit.toFixed(1)}% of trade area HHs</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Market Share</div>
          <div className="metric-value">{simulation.market_share_24mo.toFixed(1)}%</div>
          <div className="metric-sub">at 24 months · {simulation.market_share_6mo.toFixed(1)}% at 6mo</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Median Income</div>
          <div className="metric-value">
            ${(demographics.median_income / 1000).toFixed(0)}K
          </div>
          <div className="metric-sub">{demographics.family_households_pct.toFixed(0)}% family HHs</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Trade Area Pop.</div>
          <div className="metric-value">{(demographics.population / 1000).toFixed(0)}K</div>
          <div className="metric-sub">{demographics.household_count.toLocaleString()} households</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Competitors</div>
          <div
            className="metric-value"
            style={{ color: competitors.big_box_count > 4 ? "#ef4444" : "#10b981" }}
          >
            {competitors.big_box_count}
          </div>
          <div className="metric-sub">
            {competitors.underserved ? "⚡ Underserved area" : `${competitors.total_count} total retail`}
          </div>
        </div>
      </div>

      {/* Revenue Forecast Chart — use explicit width to avoid ResponsiveContainer 0-size issue */}
      <div className="forecast-container" style={{ overflow: "hidden" }}>
        <div className="forecast-title">Revenue Ramp Forecast · Monthly ($)</div>
        <AreaChart
          width={340}
          height={90}
          data={forecastData}
          margin={{ top: 0, right: 8, bottom: 0, left: 0 }}
        >
          <defs>
            <linearGradient id="revenueGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#00d4ff" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#00d4ff" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
          <XAxis dataKey="month" tick={{ fontSize: 9, fill: "#3d5a73" }} axisLine={false} tickLine={false} />
          <YAxis
            tick={{ fontSize: 9, fill: "#3d5a73" }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v) => `$${(v / 1e6).toFixed(1)}M`}
          />
          <Tooltip
            contentStyle={{
              background: "rgba(5,10,20,0.95)",
              border: "1px solid rgba(255,255,255,0.1)",
              borderRadius: 6,
              fontSize: 11,
            }}
            formatter={(v: number) => [`$${(v / 1e6).toFixed(2)}M`, "Revenue"]}
            labelStyle={{ color: "#7a9ab8" }}
          />
          <Area
            type="monotone"
            dataKey="revenue"
            stroke="#00d4ff"
            strokeWidth={2}
            fill="url(#revenueGrad)"
          />
        </AreaChart>
      </div>


      {/* Why this wins */}
      <div className="reasons-section">
        <div className="reasons-title">
          <span style={{ fontSize: 12 }}>✅</span> Why This Site Wins
        </div>
        {score.why_this_wins.map((reason, i) => (
          <div key={i} className="reason-item">
            <div className="reason-dot" />
            <span>{reason}</span>
          </div>
        ))}
      </div>

      {/* Top Risks */}
      <div className="reasons-section">
        <div className="reasons-title" style={{ color: "#f59e0b" }}>
          <span style={{ fontSize: 12 }}>⚠️</span> Key Risks
        </div>
        {score.top_risks.map((risk, i) => (
          <div key={i} className="risk-item">
            <div className="risk-dot" />
            <span>{risk}</span>
          </div>
        ))}
      </div>

      {/* Brand Fit Narrative */}
      <div className="reasons-section" style={{ borderBottom: "none", paddingBottom: 20 }}>
        <div
          className="reasons-title"
          style={{ color: brand === "walmart" ? "#5aa3e8" : "#f87171" }}
        >
          <span style={{ fontSize: 12 }}>{brand === "walmart" ? "🔵" : "🔴"}</span> Brand Fit Analysis
        </div>
        <div className="reason-item" style={{ marginBottom: 0 }}>
          <div className="reason-dot" style={{ background: brand === "walmart" ? "#5aa3e8" : "#f87171" }} />
          <span style={{ lineHeight: 1.6 }}>{brand_fit.reasoning}</span>
        </div>

        {/* School district info */}
        <div
          style={{
            marginTop: 10,
            padding: "8px 10px",
            background: "rgba(16,185,129,0.08)",
            border: "1px solid rgba(16,185,129,0.2)",
            borderRadius: 6,
            fontSize: 11,
            color: "#7a9ab8",
          }}
        >
          🎓 School District Quality: {neighborhood.school_quality_index.toFixed(0)}/100 ·
          Neighborhood Stability: {neighborhood.neighborhood_stability.toFixed(0)}/100
        </div>
      </div>
    </div>
  );
}
