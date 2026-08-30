import { Check } from "lucide-react";

export const CAMPAIGN_STEPS = [
  "audience",
  "message",
  "senders",
  "schedule",
  "review",
] as const;
export type CampaignStep = (typeof CAMPAIGN_STEPS)[number];

export default function CampaignSteps({
  current,
  complete,
  onChange,
  disabled = false,
}: {
  current: CampaignStep;
  complete: boolean[];
  onChange: (step: CampaignStep) => void;
  disabled?: boolean;
}) {
  const currentIndex = CAMPAIGN_STEPS.indexOf(current);
  return (
    <nav
      className="campaign-step-navigation"
      aria-label={`Campaign setup, step ${currentIndex + 1} of 5`}
    >
      <ol>
        {CAMPAIGN_STEPS.map((step, index) => (
          <li
            key={step}
            className={
              index === currentIndex
                ? "is-current"
                : complete[index] && index < currentIndex
                  ? "is-complete"
                  : ""
            }
          >
            <button
              type="button"
              onClick={() => onChange(step)}
              disabled={disabled}
              aria-current={index === currentIndex ? "step" : undefined}
              aria-label={`${step.charAt(0).toUpperCase() + step.slice(1)}${complete[index] ? ", complete" : ""}`}
            >
              <span className="campaign-nav-number" aria-hidden="true">
                {complete[index] && index < currentIndex ? (
                  <Check size={14} />
                ) : (
                  index + 1
                )}
              </span>
              <span>
                {step.charAt(0).toUpperCase() + step.slice(1)}
              </span>
            </button>
          </li>
        ))}
      </ol>
    </nav>
  );
}
