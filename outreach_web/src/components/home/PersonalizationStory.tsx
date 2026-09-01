"use client";

import Link from "next/link";
import { ArrowRight, Bookmark } from "lucide-react";
import { useEffect, useRef, useState } from "react";

const CONTACT_HOLD_MS = 5000;

const contacts = [
  { id: "alex", name: "Alex", company: "Northstar" },
  { id: "sam", name: "Sam", company: "Brightside" },
  { id: "lena", name: "Lena", company: "Fieldwork" },
] as const;

const connectorPaths = [
  "M 289 170 C 289 246, 335 266, 385 270 C 427 274, 453 286, 466 294",
  "M 459 170 C 506 190, 513 238, 495 260 C 485 273, 474 286, 466 294",
  "M 629 170 C 656 218, 632 258, 580 270 C 533 281, 493 286, 466 294",
];

type PersonalizationStoryProps = {
  startHref: string;
  startLabel: string;
};

export default function PersonalizationStory({ startHref, startLabel }: PersonalizationStoryProps) {
  const section = useRef<HTMLElement>(null);
  const [contactTransition, setContactTransition] = useState({ from: 0, to: 0 });
  const [cycleVersion, setCycleVersion] = useState(0);
  const [started, setStarted] = useState(false);
  const [reduceMotion, setReduceMotion] = useState(false);

  const activeIndex = contactTransition.to;
  const previousConnectorPath = connectorPaths[contactTransition.from];
  const activeConnectorPath = connectorPaths[activeIndex];

  useEffect(() => {
    const node = section.current;
    if (!node) return;

    const observer = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return;
      setStarted(true);
      observer.disconnect();
    }, { threshold: .3 });

    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const syncMotionPreference = () => setReduceMotion(media.matches);
    syncMotionPreference();
    media.addEventListener("change", syncMotionPreference);
    return () => media.removeEventListener("change", syncMotionPreference);
  }, []);

  useEffect(() => {
    if (!started) return;
    if (reduceMotion) return;

    const timer = window.setTimeout(() => {
      setContactTransition((current) => ({
        from: current.to,
        to: (current.to + 1) % contacts.length,
      }));
    }, CONTACT_HOLD_MS);

    return () => window.clearTimeout(timer);
  }, [activeIndex, cycleVersion, reduceMotion, started]);

  const selectContact = (index: number) => {
    setContactTransition((current) => ({ from: current.to, to: index }));
    setCycleVersion((version) => version + 1);
  };

  return (
    <section
      ref={section}
      id="personalization"
      className={`personalization-stage${started ? " is-running" : ""}`}
      aria-labelledby="personalization-title"
    >
      <div className="personalization-section">
        <div className="personalization-copy">
          <h2 id="personalization-title">Skip the copy,<br /><span>paste, repeat.</span></h2>
          <p>Write your message once. Outreach<br />{" "}adds each person&apos;s details from your list.</p>
          <Link className="personalization-cta" href={startHref}>
            <span>{startLabel}</span><ArrowRight aria-hidden="true" />
          </Link>
          <small>Preview every email before you send.</small>
          <div className="personalization-save-note">
            <Bookmark aria-hidden="true" />
            <span>Save your message. Use it again next time.</span>
          </div>
        </div>

        <div className="personalization-visual">
          <p className="personalization-example-label">Example contacts</p>

          <div className="personalization-contacts" aria-label="Choose an example contact">
            {contacts.map((contact, index) => {
              const active = index === activeIndex;
              return (
                <button
                  key={contact.id}
                  type="button"
                  className={`personalization-contact personalization-contact--${contact.id}${active ? " is-active" : ""}`}
                  aria-pressed={active}
                  onClick={() => selectContact(index)}
                >
                  <span className="personalization-photo" aria-hidden="true" />
                  <svg className="personalization-contact-ring" viewBox="0 0 100 100" aria-hidden="true">
                    <circle className="personalization-ring-track" cx="50" cy="50" r="47" pathLength="100" />
                  </svg>
                  <strong>{contact.name}</strong>
                  <span>{contact.company}</span>
                </button>
              );
            })}
          </div>

          <svg className="personalization-connectors" viewBox="0 0 720 760" preserveAspectRatio="none" aria-hidden="true">
            <path className={started ? "is-active" : ""} d={activeConnectorPath}>
              {started && !reduceMotion && previousConnectorPath !== activeConnectorPath && (
                <animate
                  key={`${activeIndex}-${cycleVersion}`}
                  attributeName="d"
                  from={previousConnectorPath}
                  to={activeConnectorPath}
                  dur="520ms"
                  calcMode="spline"
                  keyTimes="0;1"
                  keySplines=".65 0 .35 1"
                  fill="freeze"
                />
              )}
            </path>
          </svg>

          <div className="personalization-card-stack" aria-live="off">
            <div key={`ribbon-${contacts[activeIndex].id}`} className="personalization-ribbon" aria-hidden="true" />
            {contacts.map((contact, index) => {
              const rank = (index - activeIndex + contacts.length) % contacts.length;
              const position = rank === 0 ? "is-active" : rank === 1 ? "is-next" : "is-back";
              return (
                <article
                  key={contact.id}
                  className={`personalization-preview-card ${position}`}
                  aria-hidden={rank !== 0}
                >
                  <p>A preview for {contact.name}</p>
                  <h3>Hi <mark>{contact.name},</mark></h3>
                  <p className="personalization-message">Could <mark>{contact.company}</mark> use a hand<br className="personalization-desktop-break" /> with its website?</p>
                  <p className="personalization-signoff">Happy to send over a few ideas.</p>
                </article>
              );
            })}
          </div>

          <p className="personalization-disclaimer">Illustrative profiles. No email is sent.</p>
        </div>
      </div>
    </section>
  );
}
