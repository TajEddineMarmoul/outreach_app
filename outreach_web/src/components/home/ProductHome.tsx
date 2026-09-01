"use client";

import Link from "next/link";
import { useAuth } from "@clerk/nextjs";
import { ArrowRight, ChevronDown, FileSpreadsheet, Mail, SlidersHorizontal } from "lucide-react";
import EnvelopeStory from "./EnvelopeStory";
import PersonalizationStory from "./PersonalizationStory";
import "./product-home.css";
import "./hero.css";
import "./envelope-story.css";
import "./personalization-story.css";

export default function ProductHome() {
  const { isSignedIn } = useAuth();
  const startHref = isSignedIn ? "/campaigns" : "/sign-up?redirect_url=%2Fwelcome";
  const startLabel = isSignedIn ? "Open app" : "Get started";

  return (
    <div className="product-home">
      <a className="product-skip" href="#product-main">Skip to content</a>
      <div className="product-stage">
        <header className="product-header">
          <Link className="product-brand" href="/" aria-label="Outreach home">
            <svg viewBox="0 0 36 36" fill="currentColor" aria-hidden="true"><path d="M32.3 2.9 3.8 13.5c-2 .7-2 2.3-.1 2.9l10.4 3.5 3.5 10.5c.7 1.9 2.2 1.9 3-.1L33.2 4.5c.5-1.2.2-2-.9-1.6Z" /></svg>
            <span>OUTREACH</span>
          </Link>
          <Link className="product-sign-in" href={isSignedIn ? "/campaigns" : "/sign-in?redirect_url=%2Fcampaigns"}>{isSignedIn ? "Open app" : "Sign in"}</Link>
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

      <div className="product-content">
        <section id="features" className="product-features" aria-label="What you can do with Outreach">
          <article><FileSpreadsheet size={23} strokeWidth={1.6} aria-hidden="true" /><h2>Bring your own contacts</h2><p>Import from CSV, pasted rows, or Google Sheets. Keep the fields that matter to you.</p></article>
          <article><Mail size={23} strokeWidth={1.6} aria-hidden="true" /><h2>Write once. Make it personal.</h2><p>Use your contact fields, save templates, and preview each message before sending.</p></article>
          <article><SlidersHorizontal size={23} strokeWidth={1.6} aria-hidden="true" /><h2>Stay in control</h2><p>Choose your senders and timing. Follow sending progress and pause when you need to.</p></article>
        </section>

        <section id="how-it-works" className="product-how" aria-labelledby="how-title">
          <div><p className="product-eyebrow">A clear place to start</p><h2 id="how-title">What is a campaign?</h2><p>A campaign is simply a group of people, a message, and a plan for sending it.</p></div>
          <ol><li><span>1</span><div><h3>Choose your audience</h3><p>Import your list and review your contacts.</p></div></li><li><span>2</span><div><h3>Write your message</h3><p>Add your words and check a personalized preview.</p></div></li><li><span>3</span><div><h3>Review and launch</h3><p>Choose senders and timing, then confirm when you’re ready.</p></div></li></ol>
        </section>

        <section className="product-questions" aria-labelledby="questions-title">
          <h2 id="questions-title">Before you get started</h2>
          <div>
            <details><summary>Will importing my contacts send an email?<ChevronDown size={18} aria-hidden="true" /></summary><p>No. Importing builds your audience. You write your message, choose your senders and schedule, and confirm on Review before sending can start.</p></details>
            <details><summary>Can I use my own spreadsheet columns?<ChevronDown size={18} aria-hidden="true" /></summary><p>Yes. Include a column named email in the first row. Other columns are optional, and you can use them to personalize your message.</p></details>
            <details><summary>Can I import from a Google Sheets link?<ChevronDown size={18} aria-hidden="true" /></summary><p>Yes, if Outreach can access the public sheet. For a restricted sheet, copy and paste the rows or export it as a CSV instead.</p></details>
          </div>
        </section>
      </div>

      <footer className="product-footer"><Link className="product-brand" href="/">OUTREACH</Link><p>A clearer way to manage your outreach.</p><Link className="product-text-link" href={startHref}>{startLabel} <ArrowRight size={16} aria-hidden="true" /></Link></footer>
    </div>
  );
}
