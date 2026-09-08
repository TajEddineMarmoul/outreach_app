export interface DeliveryProgressInput {
  totalRecipients?: number;
  sentCount?: number;
  undeliveredCount?: number;
  sendErrorCount?: number;
  skippedCount?: number;
}

type OutcomeKey = "sent" | "undelivered" | "send-errors" | "skipped" | "remaining";

export interface DeliveryOutcome {
  key: OutcomeKey;
  count: number;
  label: string;
}

export interface DeliveryProgress {
  totalRecipients: number;
  processedCount: number;
  remainingCount: number;
  isComplete: boolean;
  outcomes: DeliveryOutcome[];
}

function count(value: number | undefined) {
  return Math.max(0, Math.floor(value || 0));
}

export function getDeliveryProgress({
  totalRecipients,
  sentCount,
  undeliveredCount,
  sendErrorCount,
  skippedCount,
}: DeliveryProgressInput): DeliveryProgress {
  const total = count(totalRecipients);
  const sent = count(sentCount);
  const undelivered = count(undeliveredCount);
  const sendErrors = count(sendErrorCount);
  const skipped = count(skippedCount);
  const finalOutcomes = sent + undelivered + sendErrors + skipped;
  const remaining = Math.max(0, total - finalOutcomes);

  return {
    totalRecipients: total,
    processedCount: Math.min(total, finalOutcomes),
    remainingCount: remaining,
    isComplete: total > 0 && remaining === 0,
    outcomes: [
      { key: "sent", count: sent, label: "sent" },
      { key: "undelivered", count: undelivered, label: "undelivered" },
      { key: "send-errors", count: sendErrors, label: "send errors" },
      { key: "skipped", count: skipped, label: "skipped" },
      { key: "remaining", count: remaining, label: "remaining" },
    ],
  };
}

export function deliveryProgressLabel(progress: DeliveryProgress) {
  if (!progress.totalRecipients) return "No recipients yet";
  if (progress.isComplete) {
    return `Finished · ${progress.totalRecipients} of ${progress.totalRecipients} processed`;
  }
  return `${progress.processedCount} of ${progress.totalRecipients} processed · ${progress.remainingCount} remaining`;
}

export function deliveryOutcomeSummary(progress: DeliveryProgress) {
  const outcomes = progress.outcomes.filter(
    (outcome) => outcome.key !== "remaining" && outcome.count > 0,
  );
  return outcomes.length
    ? outcomes.map((outcome) => `${outcome.count} ${outcome.label}`).join(", ")
    : "No delivery results yet";
}

export default function DeliveryOutcomeBar({
  progress,
  showLegend = true,
  className = "",
}: {
  progress: DeliveryProgress;
  showLegend?: boolean;
  className?: string;
}) {
  if (!progress.totalRecipients) return null;

  const outcomeSummary = deliveryOutcomeSummary(progress);
  const stateSummary = progress.isComplete
    ? `Delivery finished: ${outcomeSummary}. All ${progress.totalRecipients} recipients have a final result.`
    : `${outcomeSummary}. ${progress.remainingCount} recipient${progress.remainingCount === 1 ? "" : "s"} remaining.`;

  return (
    <div className={`delivery-outcome ${className}`.trim()}>
      <div
        className="delivery-outcome-track"
        role="img"
        aria-label={stateSummary}
      >
        {progress.outcomes.map(
          (outcome) =>
            outcome.count > 0 && (
              <span
                key={outcome.key}
                className={`delivery-outcome-segment is-${outcome.key}`}
                style={{ flexGrow: outcome.count }}
                aria-hidden="true"
              />
            ),
        )}
      </div>
      {showLegend && (
        <ul className="delivery-outcome-legend" aria-label="Delivery outcome breakdown">
          {progress.outcomes.map((outcome) => (
            <li key={outcome.key}>
              <span className={`delivery-outcome-dot is-${outcome.key}`} aria-hidden="true" />
              <span>{outcome.label}</span>
              <strong>{outcome.count}</strong>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
