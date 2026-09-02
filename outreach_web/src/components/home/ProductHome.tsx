"use client";

import Link from "next/link";
import { useAuth } from "@clerk/nextjs";
import EnvelopeStory from "./EnvelopeStory";
import GettingStartedStory from "./GettingStartedStory";
import PersonalizationStory from "./PersonalizationStory";
import ScheduleStory from "./ScheduleStory";
import "./product-home.css";
import "./hero.css";
import "./envelope-story.css";
import "./personalization-story.css";
import "./schedule-story.css";
import "./getting-started-story.css";

export default function ProductHome() {
  const { isSignedIn } = useAuth();
  const startHref = isSignedIn ? "/campaigns" : "/sign-up?redirect_url=%2Fwelcome";
  const startLabel = isSignedIn ? "Open app" : "Get started";
  const signInHref = isSignedIn ? "/campaigns" : "/sign-in?redirect_url=%2Fcampaigns";
  const signInLabel = isSignedIn ? "Open app" : "Sign in";

  return (
    <div className="product-home">
      <a className="product-skip" href="#product-main">Skip to content</a>
      <div className="product-stage">
        <header className="product-header">
          <Link className="product-brand" href="/" aria-label="Outreach home">
            <svg viewBox="0 0 36 36" fill="currentColor" aria-hidden="true"><path d="M32.3 2.9 3.8 13.5c-2 .7-2 2.3-.1 2.9l10.4 3.5 3.5 10.5c.7 1.9 2.2 1.9 3-.1L33.2 4.5c.5-1.2.2-2-.9-1.6Z" /></svg>
            <span>OUTREACH</span>
          </Link>
          <Link className="product-sign-in" href={signInHref}>{signInLabel}</Link>
        </header>
        <section id="product-main" className="product-hero" aria-labelledby="product-title" tabIndex={-1}>
          <div className="product-intro">
            <h1 id="product-title">Write one email.<br /><span>Make it personal<br />for everyone.</span></h1>
            <p className="product-lead">Send a personalized email to<br />each contact automatically.</p>
            <Link className="product-hero-cta" href={startHref}>{startLabel}</Link>
          </div>
          <EnvelopeStory />
        </section>
      </div>

      <PersonalizationStory startHref={startHref} startLabel={startLabel} />
      <ScheduleStory />
      <GettingStartedStory
        startHref={startHref}
        startLabel={startLabel}
        signInHref={signInHref}
        signInLabel={signInLabel}
      />
    </div>
  );
}
