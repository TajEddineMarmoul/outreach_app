"use client";

import { useState } from "react";
import useSWR from "swr";
import { Bot, CircleAlert, ListChecks, MailCheck, MailX, MessageSquareReply } from "lucide-react";
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

interface Analytics {
  page: number;
  attempts: number;
  sent: number;
  replied: number;
  automated_responses: number;
  undelivered: number;
  send_errors: number;
  failed: number;
  series: { date: string; sent: number }[];
  items: {
    id: number;
    email: string;
    subject: string;
    status: string;
    response_status?: string | null;
    responded_at?: string | null;
    created_at: string;
    error_message?: string;
  }[];
}

export default function AnalyticsPage() {
  const { API_URL, authFetch } = useApiClient();
  const [days, setDays] = useState(7);
  const [page, setPage] = useState(1);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  const { data, isLoading, isValidating, error, mutate } = useSWR<Analytics>(
    `${API_URL}/api/analytics?days=${days}&page=${page}`,
    { keepPreviousData: true },
  );
  const max = Math.max(
    4,
    Math.ceil(
      Math.max(0, ...(data?.series.map((item) => item.sent) || [])) / 4,
    ) * 4,
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
          </div>
          <section
            className="app-panel app-chart"
            aria-labelledby="chart-title"
          >
            <div className="app-chart-heading">
              <h2 id="chart-title">Emails sent</h2>
              <span role="status">
                {isValidating ? "Updating…" : "Daily totals · UTC"}
              </span>
            </div>
            {data.attempts === 0 ? (
              <div className="app-empty" style={{ minHeight: 225 }}>
                <h2>No delivery attempts in this period</h2>
                <p>Your results will appear here after a campaign sends.</p>
              </div>
            ) : (
              <>
                <div
                  className="app-bar-chart"
                  role="img"
                  aria-label={`Daily emails sent over the last ${data.series.length} days. Total: ${data.sent}. Values are also available in the chart data table.`}
                >
                  <div className="app-chart-axis" aria-hidden="true">
                    {[4, 3, 2, 1, 0].map((tick) => (
                      <span key={tick}>{(max * tick) / 4}</span>
                    ))}
                  </div>
                  <div
                    className="app-chart-bars"
                    style={{
                      gridTemplateColumns: `repeat(${data.series.length}, minmax(0, 1fr))`,
                    }}
                  >
                    {data.series.map((item, index) => (
                      <div className="app-chart-point" key={item.date}>
                        <div
                          className="app-chart-bar"
                          title={`${item.date}: ${item.sent} sent`}
                          style={{ height: `${(item.sent / max) * 100}%` }}
                        />
                        {(data.series.length === 7 ||
                          index % 5 === 0 ||
                          index === data.series.length - 1) && (
                          <span className="app-chart-label">
                            {item.date.slice(5)}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
                <table className="sr-only">
                  <caption>Daily emails sent (UTC)</caption>
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Sent</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.series.map((item) => (
                      <tr key={item.date}>
                        <td>{item.date}</td>
                        <td>{item.sent}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </section>
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
            Undelivered means the recipient server returned it. Send errors happen
            before Gmail accepts it. Replies exclude automated responses. Test
            simulations are excluded; opens and clicks are not tracked.
          </p>
        </>
      )}
    </div>
  );
}
