"use client";

import { useState } from "react";
import useSWR from "swr";
import { Bot, CircleAlert, ListChecks, MailCheck, MailOpen, MailX, MessageSquareReply, MousePointerClick } from "lucide-react";
import { checkResponse, errorMessage, useApiClient } from "@/lib/api";
import {
  ActionMenu,
  MenuAction,
  Notice,
  PageHeading,
  PageState,
  Pager,
  StatusBadge,
} from "@/components/app-ui";

interface DailyActivity {
  date: string;
  sent: number;
  undelivered: number;
  send_errors: number;
  human_replies: number;
  automated_replies: number;
}

interface SendBreakdown {
  id: number | string | null;
  name: string;
  sent: number;
  series: { date: string; sent: number }[];
}

interface Analytics {
  page: number;
  attempts: number;
  sent: number;
  replied: number;
  automated_responses: number;
  opened: number;
  clicked: number;
  open_events: number;
  click_events: number;
  undelivered: number;
  send_errors: number;
  failed: number;
  series: DailyActivity[];
  campaigns: SendBreakdown[];
  senders: SendBreakdown[];
  items: {
    id: number;
    email: string;
    subject: string;
    status: string;
    response_status?: string | null;
    open_count?: number;
    click_count?: number;
    last_opened_at?: string | null;
    last_clicked_at?: string | null;
    responded_at?: string | null;
    created_at: string;
    error_message?: string;
  }[];
}

const ACTIVITY_SEGMENTS = [
  { key: "sent", label: "Sent", className: "is-sent" },
  { key: "undelivered", label: "Undelivered", className: "is-undelivered" },
  { key: "send_errors", label: "Send errors", className: "is-error" },
  { key: "human_replies", label: "Human replies", className: "is-human-reply" },
  { key: "automated_replies", label: "Automated replies", className: "is-automated-reply" },
] as const;

type ActivityKey = (typeof ACTIVITY_SEGMENTS)[number]["key"];

function chartMaximum(values: number[]) {
  return Math.max(4, Math.ceil(Math.max(0, ...values) / 4) * 4);
}

function shouldShowDateLabel(index: number, length: number) {
  return length === 7 || index % 5 === 0 || index === length - 1;
}

function breakdownKey(item: SendBreakdown) {
  return String(item.id ?? "unassigned");
}

function chartIdPart(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-");
}

function ChartTooltip({
  id,
  date,
  entries,
  position,
}: {
  id: string;
  date: string;
  entries: { label: string; value: number; className: string }[];
  position: "start" | "middle" | "end";
}) {
  return (
    <div className={`app-chart-tooltip is-${position}`} id={id} role="tooltip">
      <strong>{date}</strong>
      <div className="app-chart-tooltip-values">
        {entries.map((entry) => (
          <span className="app-chart-tooltip-row" key={entry.label}>
            <span><i className={`app-chart-key ${entry.className}`} aria-hidden="true" />{entry.label}</span>
            <b>{entry.value.toLocaleString()}</b>
          </span>
        ))}
      </div>
    </div>
  );
}

function DailySentChart({
  series,
  label,
  tooltipPrefix,
}: {
  series: { date: string; sent: number }[];
  label: string;
  tooltipPrefix: string;
}) {
  const max = chartMaximum(series.map((item) => item.sent));
  const total = series.reduce((sum, item) => sum + item.sent, 0);
  const [activeDate, setActiveDate] = useState<string | null>(null);

  return (
    <>
      <div
        className="app-bar-chart"
        role="group"
        aria-label={`${label}. ${total.toLocaleString()} emails sent across ${series.length} days. Values are also available in the chart data table.`}
      >
        <div className="app-chart-axis" aria-hidden="true">
          {[4, 3, 2, 1, 0].map((tick) => (
            <span key={tick}>{(max * tick) / 4}</span>
          ))}
        </div>
        <div
          className="app-chart-bars"
          style={{
            gridTemplateColumns: `repeat(${series.length}, minmax(0, 1fr))`,
          }}
        >
          {series.map((item, index) => {
            const isActive = activeDate === item.date;
            const tooltipId = `${chartIdPart(tooltipPrefix)}-tooltip-${item.date}`;
            const position = index < 2 ? "start" : index >= series.length - 2 ? "end" : "middle";
            return (
              <div className={`app-chart-point ${isActive ? "is-active" : ""}`} key={item.date}>
                <button
                  type="button"
                  className="app-chart-hit-area"
                  aria-label={`${item.date}: ${item.sent.toLocaleString()} emails sent`}
                  aria-describedby={isActive ? tooltipId : undefined}
                  onMouseEnter={() => setActiveDate(item.date)}
                  onMouseLeave={() => setActiveDate(null)}
                  onFocus={() => setActiveDate(item.date)}
                  onBlur={() => setActiveDate(null)}
                  onClick={() => setActiveDate(item.date)}
                >
                  <span
                    className="app-chart-bar"
                    style={{ height: `${(item.sent / max) * 100}%` }}
                  />
                  {shouldShowDateLabel(index, series.length) && (
                    <span className="app-chart-label">{item.date.slice(5)}</span>
                  )}
                </button>
                {isActive && (
                  <ChartTooltip
                    id={tooltipId}
                    date={item.date}
                    entries={[{ label: "Sent", value: item.sent, className: "is-sent" }]}
                    position={position}
                  />
                )}
              </div>
            );
          })}
        </div>
      </div>
      <table className="sr-only">
        <caption>{label}</caption>
        <thead>
          <tr>
            <th>Date</th>
            <th>Sent</th>
          </tr>
        </thead>
        <tbody>
          {series.map((item) => (
            <tr key={item.date}>
              <td>{item.date}</td>
              <td>{item.sent}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function DailyActivityChart({ series }: { series: DailyActivity[] }) {
  const dailyTotals = series.map((item) =>
    ACTIVITY_SEGMENTS.reduce((sum, segment) => sum + item[segment.key], 0),
  );
  const max = chartMaximum(dailyTotals);
  const total = dailyTotals.reduce((sum, count) => sum + count, 0);
  const [activeDate, setActiveDate] = useState<string | null>(null);

  return (
    <>
      <div className="app-chart-legend" aria-label="Daily activity legend">
        {ACTIVITY_SEGMENTS.map((segment) => (
          <span className="app-chart-legend-item" key={segment.key}>
            <i className={`app-chart-key ${segment.className}`} aria-hidden="true" />
            {segment.label}
          </span>
        ))}
      </div>
      <div
        className="app-bar-chart"
        role="group"
        aria-label={`Daily delivery and response activity. ${total.toLocaleString()} events across ${series.length} days. Values are also available in the chart data table.`}
      >
        <div className="app-chart-axis" aria-hidden="true">
          {[4, 3, 2, 1, 0].map((tick) => (
            <span key={tick}>{(max * tick) / 4}</span>
          ))}
        </div>
        <div
          className="app-chart-bars"
          style={{
            gridTemplateColumns: `repeat(${series.length}, minmax(0, 1fr))`,
          }}
        >
          {series.map((item, index) => {
            const totalForDay = dailyTotals[index];
            const isActive = activeDate === item.date;
            const tooltipId = `activity-tooltip-${item.date}`;
            const position = index < 2 ? "start" : index >= series.length - 2 ? "end" : "middle";
            return (
              <div className={`app-chart-point ${isActive ? "is-active" : ""}`} key={item.date}>
                <button
                  type="button"
                  className="app-chart-hit-area"
                  aria-label={`${item.date}: ${ACTIVITY_SEGMENTS.map((segment) => `${segment.label} ${item[segment.key].toLocaleString()}`).join(", ")}`}
                  aria-describedby={isActive ? tooltipId : undefined}
                  onMouseEnter={() => setActiveDate(item.date)}
                  onMouseLeave={() => setActiveDate(null)}
                  onFocus={() => setActiveDate(item.date)}
                  onBlur={() => setActiveDate(null)}
                  onClick={() => setActiveDate(item.date)}
                >
                  <span
                    className="app-chart-stack"
                    style={{ height: `${(totalForDay / max) * 100}%` }}
                  >
                    {ACTIVITY_SEGMENTS.map((segment) => {
                      const value = item[segment.key as ActivityKey];
                      return value ? (
                        <span
                          className={`app-chart-stack-segment ${segment.className}`}
                          key={segment.key}
                          style={{ height: `${(value / totalForDay) * 100}%` }}
                        />
                      ) : null;
                    })}
                  </span>
                  {shouldShowDateLabel(index, series.length) && (
                    <span className="app-chart-label">{item.date.slice(5)}</span>
                  )}
                </button>
                {isActive && (
                  <ChartTooltip
                    id={tooltipId}
                    date={item.date}
                    entries={ACTIVITY_SEGMENTS.map((segment) => ({
                      label: segment.label,
                      value: item[segment.key],
                      className: segment.className,
                    }))}
                    position={position}
                  />
                )}
              </div>
            );
          })}
        </div>
      </div>
      <table className="sr-only">
        <caption>Daily delivery and response activity (UTC)</caption>
        <thead>
          <tr>
            <th>Date</th>
            {ACTIVITY_SEGMENTS.map((segment) => <th key={segment.key}>{segment.label}</th>)}
          </tr>
        </thead>
        <tbody>
          {series.map((item) => (
            <tr key={item.date}>
              <td>{item.date}</td>
              {ACTIVITY_SEGMENTS.map((segment) => <td key={segment.key}>{item[segment.key]}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function BreakdownChart({
  title,
  selectorLabel,
  breakdowns,
  selectedKey,
  onSelect,
}: {
  title: string;
  selectorLabel: string;
  breakdowns: SendBreakdown[];
  selectedKey: string;
  onSelect: (key: string) => void;
}) {
  const selected = breakdowns.find((item) => breakdownKey(item) === selectedKey) ?? breakdowns[0];
  const chartTitleId = `${selectorLabel.toLowerCase().replace(/\s+/g, "-")}-chart-title`;

  return (
    <section className="app-panel app-chart app-breakdown-chart" aria-labelledby={chartTitleId}>
      <div className="app-chart-heading">
        <div>
          <h2 id={chartTitleId}>{title}</h2>
          <p className="app-chart-note">Choose an item to see its daily sent volume.</p>
        </div>
        {selected && (
          <label className="app-chart-selector">
            <span>{selectorLabel}</span>
            <select
              className="app-select"
              value={breakdownKey(selected)}
              onChange={(event) => onSelect(event.target.value)}
            >
              {breakdowns.map((item) => (
                <option key={breakdownKey(item)} value={breakdownKey(item)}>{item.name}</option>
              ))}
            </select>
          </label>
        )}
      </div>
      {!selected ? (
        <div className="app-empty" style={{ minHeight: 225 }}>
          <h2>No sent emails in this period</h2>
          <p>Your daily breakdown will appear after a campaign sends.</p>
        </div>
      ) : (
        <>
          <p className="app-chart-total"><strong>{selected.name}</strong> · {selected.sent.toLocaleString()} sent</p>
          <DailySentChart
            series={selected.series}
            label={`Daily emails sent for ${selected.name} (UTC)`}
            tooltipPrefix={selectorLabel}
          />
        </>
      )}
    </section>
  );
}

export default function AnalyticsPage() {
  const { API_URL, authFetch } = useApiClient();
  const [days, setDays] = useState(7);
  const [page, setPage] = useState(1);
  const [selectedCampaign, setSelectedCampaign] = useState("");
  const [selectedSender, setSelectedSender] = useState("");
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  const { data, isLoading, isValidating, error, mutate } = useSWR<Analytics>(
    `${API_URL}/api/analytics?days=${days}&page=${page}`,
    { keepPreviousData: true },
  );
  const exportReport = async () => {
    setBusy(true);
    setActionError("");
    try {
      const response = await authFetch(
        `${API_URL}/api/analytics/export?days=${days}`,
      );
      if (!response.ok) await checkResponse(response);
      const url = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `delivery-last-${days}-days.csv`;
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
      setActionError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="app-page" aria-busy={isValidating}>
      <PageHeading
        title="Analytics"
        description="See how your email delivery is performing."
        actions={
          <>
            <select
              aria-label="Analytics date range"
              className="app-select"
              value={days}
              onChange={(event) => {
                setDays(Number(event.target.value));
                setPage(1);
              }}
            >
              <option value={7}>Last 7 days</option>
              <option value={30}>Last 30 days</option>
            </select>
            <ActionMenu disabled={busy || !data || !!error}>
              <MenuAction onClick={() => void exportReport()}>
                {busy ? "Exporting…" : "Export report"}
              </MenuAction>
            </ActionMenu>
          </>
        }
      />
      <Notice error={actionError} />
      <PageState
        loading={isLoading && !data}
        error={error}
        retry={() => void mutate()}
      />
      {data && !error && (
        <>
          <div className="app-outcome-board">
            <section>
              <h2>Delivery</h2>
              <dl className="app-stats is-delivery-grid">
                <div>
                  <dt className="app-metric-label"><ListChecks size={15} aria-hidden="true" />Attempts</dt>
                  <dd>{data.attempts.toLocaleString()}</dd>
                </div>
                <div>
                  <dt className="app-metric-label is-success"><MailCheck size={15} aria-hidden="true" />Sent</dt>
                  <dd style={{ color: "#00724f" }}>{data.sent.toLocaleString()}</dd>
                </div>
                <div>
                  <dt className="app-metric-label is-undelivered"><MailX size={15} aria-hidden="true" />Undelivered</dt>
                  <dd style={{ color: "#9a4c0b" }}>{data.undelivered.toLocaleString()}</dd>
                </div>
                <div>
                  <dt className="app-metric-label is-error"><CircleAlert size={15} aria-hidden="true" />Send errors</dt>
                  <dd>{data.send_errors.toLocaleString()}</dd>
                </div>
              </dl>
            </section>
            <section>
              <h2>Responses</h2>
              <dl className="app-stats is-response-grid">
                <div>
                  <dt className="app-metric-label is-info"><MessageSquareReply size={15} aria-hidden="true" />Human replies</dt>
                  <dd style={{ color: "#0751ce" }}>{data.replied.toLocaleString()}</dd>
                </div>
                <div>
                  <dt className="app-metric-label is-warning"><Bot size={15} aria-hidden="true" />Automated replies</dt>
                  <dd style={{ color: "#8a5a13" }}>{data.automated_responses.toLocaleString()}</dd>
                </div>
              </dl>
            </section>
            <section>
              <h2>Engagement</h2>
              <dl className="app-stats is-response-grid">
                <div>
                  <dt className="app-metric-label is-info"><MailOpen size={15} aria-hidden="true" />Opened</dt>
                  <dd style={{ color: "#0751ce" }}>{data.opened.toLocaleString()}</dd>
                  <small className="app-secondary">{data.open_events.toLocaleString()} total opens</small>
                </div>
                <div>
                  <dt className="app-metric-label is-success"><MousePointerClick size={15} aria-hidden="true" />Clicked</dt>
                  <dd style={{ color: "#00724f" }}>{data.clicked.toLocaleString()}</dd>
                  <small className="app-secondary">{data.click_events.toLocaleString()} total clicks</small>
                </div>
              </dl>
            </section>
          </div>
          <section className="app-panel app-chart" aria-labelledby="chart-title">
            <div className="app-chart-heading">
              <div>
                <h2 id="chart-title">Daily delivery and replies</h2>
                <p className="app-chart-note">
                  Delivery outcomes are shown on the send date. Replies are shown on the day they were received.
                </p>
              </div>
              <span role="status">{isValidating ? "Updating…" : "Daily totals · UTC"}</span>
            </div>
            {data.series.every((item) =>
              ACTIVITY_SEGMENTS.every((segment) => item[segment.key] === 0),
            ) ? (
              <div className="app-empty" style={{ minHeight: 225 }}>
                <h2>No delivery or reply activity in this period</h2>
                <p>Your results will appear here after a campaign sends or receives a reply.</p>
              </div>
            ) : (
              <DailyActivityChart series={data.series} />
            )}
          </section>
          <div className="app-chart-grid">
            <BreakdownChart
              title="Daily emails sent by campaign"
              selectorLabel="Campaign"
              breakdowns={data.campaigns}
              selectedKey={selectedCampaign}
              onSelect={setSelectedCampaign}
            />
            <BreakdownChart
              title="Daily emails sent by sending email"
              selectorLabel="Sending email"
              breakdowns={data.senders}
              selectedKey={selectedSender}
              onSelect={setSelectedSender}
            />
          </div>
          <details className="app-disclosure">
            <summary>View delivery history</summary>
            <div className="app-disclosure-content">
              {!data.items.length ? (
                <p className="app-muted">
                  No delivery attempts in this period.
                </p>
              ) : (
                <>
                  <div className="app-table-wrap">
                    <table className="app-table">
                      <thead>
                        <tr>
                          <th>Recipient</th>
                          <th>Subject</th>
                          <th>Date / time (UTC)</th>
                          <th>Status</th>
                          <th>Engagement</th>
                          <th>Response</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.items.map((item) => (
                          <tr key={item.id}>
                            <td>{item.email}</td>
                            <td>
                              {item.subject}
                              {item.error_message && (
                                <span className="app-secondary">
                                  {item.error_message}
                                </span>
                              )}
                            </td>
                            <td>
                              {item.created_at.replace("T", " ").slice(0, 16)}
                            </td>
                            <td>
                              <StatusBadge status={item.status} />
                            </td>
                            <td>
                              {item.open_count || item.click_count ? (
                                <span className="app-secondary">
                                  {item.open_count ? `${item.open_count} open${item.open_count === 1 ? "" : "s"}` : ""}
                                  {item.open_count && item.click_count ? " · " : ""}
                                  {item.click_count ? `${item.click_count} click${item.click_count === 1 ? "" : "s"}` : ""}
                                </span>
                              ) : (
                                <span className="app-muted">—</span>
                              )}
                            </td>
                            <td>
                              {item.response_status ? (
                                <StatusBadge status={item.response_status} />
                              ) : (
                                <span className="app-muted">—</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <Pager
                    page={data.page}
                    pageSize={6}
                    total={data.attempts}
                    onChange={setPage}
                  />
                </>
              )}
            </div>
          </details>
          <p className="app-footnote">
            Sent means Gmail accepted the message and no rejection was found.
            Undelivered means the recipient server returned it. Opens rely on
            images loading and may be affected by privacy tools; clicks are the
            stronger engagement signal. Test simulations are excluded.
          </p>
        </>
      )}
    </div>
  );
}
