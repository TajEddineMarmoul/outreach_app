function CalendarIllustration() {
  const clockTicks = Array.from({ length: 12 }, (_, index) => index * 30);

  return (
    <svg
      className="schedule-illustration"
      viewBox="0 0 920 560"
      role="img"
      aria-label="An example sending calendar set for weekdays from 9 AM to 4 PM, with an envelope, clock, and paper plane"
    >
      <defs>
        <linearGradient id="schedule-blue" x1="0" y1="0" x2="1" y2="1">
          <stop stopColor="#1070ff" />
          <stop offset="1" stopColor="#0048f2" />
        </linearGradient>
        <linearGradient id="schedule-blue-dark" x1="0" y1="0" x2="1" y2="1">
          <stop stopColor="#0b5eff" />
          <stop offset="1" stopColor="#062eaa" />
        </linearGradient>
        <linearGradient id="schedule-paper" x1="0" y1="0" x2=".8" y2="1">
          <stop stopColor="#ffffff" />
          <stop offset="1" stopColor="#eef3fc" />
        </linearGradient>
        <linearGradient id="schedule-metal" x1="0" y1="0" x2="1" y2="1">
          <stop stopColor="#ffffff" />
          <stop offset=".55" stopColor="#f7f9ff" />
          <stop offset="1" stopColor="#cbd4e5" />
        </linearGradient>
        <filter id="schedule-shadow" x="-30%" y="-30%" width="160%" height="180%">
          <feDropShadow dx="0" dy="13" stdDeviation="14" floodColor="#183260" floodOpacity=".25" />
        </filter>
        <filter id="schedule-soft-shadow" x="-40%" y="-40%" width="180%" height="190%">
          <feDropShadow dx="0" dy="8" stdDeviation="8" floodColor="#183260" floodOpacity=".22" />
        </filter>
      </defs>

      <path className="schedule-flight-path" d="M70 452 C190 520 337 455 478 475 C645 500 744 427 808 292" />

      <g className="schedule-calendar" filter="url(#schedule-shadow)" transform="translate(124 35) rotate(4 270 240)">
        <path d="M493 76 L535 104 L550 412 L489 438 Z" fill="url(#schedule-blue-dark)" stroke="#0733a4" strokeWidth="2" />
        <rect x="74" y="87" width="447" height="369" rx="12" fill="#dce4f1" stroke="#aebbd0" strokeWidth="1.5" />
        <rect x="61" y="74" width="447" height="369" rx="12" fill="#eef3fb" stroke="#bdc8d9" strokeWidth="1.5" />
        <rect x="48" y="61" width="447" height="369" rx="12" fill="url(#schedule-paper)" stroke="#c3ccdc" strokeWidth="1.5" />
        <path d="M48 73 Q48 61 60 61 H483 Q495 61 495 73 V93 H48 Z" fill="url(#schedule-blue)" />

        <text className="schedule-calendar-title" x="271" y="130" textAnchor="middle">Your sending week</text>
        <rect x="65" y="143" width="413" height="245" rx="6" fill="#ffffff55" stroke="#c9d3e3" strokeWidth="1.2" />
        {[1, 2, 3, 4].map((column) => (
          <line key={column} x1={65 + column * 82.6} y1="143" x2={65 + column * 82.6} y2="388" stroke="#cbd5e4" strokeWidth="1" />
        ))}
        <line x1="65" y1="210" x2="478" y2="210" stroke="#d4dcea" strokeWidth="1" />
        {[
          ["Mon", 106], ["Tue", 188], ["Wed", 271], ["Thu", 353], ["Fri", 436],
        ].map(([day, x]) => (
          <text key={day} className="schedule-calendar-day" x={x} y="180" textAnchor="middle">{day}</text>
        ))}
        <rect x="55" y="222" width="433" height="58" rx="8" fill="url(#schedule-blue)" />
        <text className="schedule-calendar-time" x="271" y="260" textAnchor="middle">9 AM to 4 PM</text>
        <text className="schedule-calendar-utc" x="271" y="367" textAnchor="middle">UTC</text>

        <g className="schedule-ring">
          <ellipse cx="103" cy="70" rx="12" ry="9" fill="#00288e" opacity=".85" />
          <path d="M103 70 C87 21 135 4 136 53 C136 71 127 88 116 93" fill="none" stroke="url(#schedule-blue-dark)" strokeWidth="11" strokeLinecap="round" />
          <path d="M104 69 C93 29 124 17 127 52" fill="none" stroke="#5392ff" strokeWidth="2.5" strokeLinecap="round" opacity=".75" />
        </g>
        <g className="schedule-ring">
          <ellipse cx="420" cy="70" rx="12" ry="9" fill="#00288e" opacity=".85" />
          <path d="M420 70 C404 21 452 4 453 53 C453 71 444 88 433 93" fill="none" stroke="url(#schedule-blue-dark)" strokeWidth="11" strokeLinecap="round" />
          <path d="M421 69 C410 29 441 17 444 52" fill="none" stroke="#5392ff" strokeWidth="2.5" strokeLinecap="round" opacity=".75" />
        </g>
      </g>

      <g className="schedule-envelope-art" filter="url(#schedule-soft-shadow)" transform="translate(24 364) rotate(-7 76 58)">
        <rect width="150" height="112" rx="8" fill="url(#schedule-paper)" stroke="#b9c4d8" strokeWidth="1.3" />
        <path d="M2 9 L70 66 Q75 70 80 66 L148 9" fill="#fff" stroke="#aebbd0" strokeWidth="1.3" />
        <path d="M2 106 L61 55 Q75 44 89 55 L148 106" fill="#f8faff" stroke="#c7d0df" strokeWidth="1.2" />
      </g>

      <g className="schedule-plane-art" transform="translate(756 217) rotate(-4 60 46)">
        <path d="M0 35 L127 0 L53 99 L40 57 Z" fill="url(#schedule-blue)" stroke="#0048d8" strokeWidth="1.2" />
        <path d="M40 57 L127 0 L58 73 Z" fill="#003dc3" />
        <path d="M58 73 L127 0 L53 99 Z" fill="#126cff" />
      </g>

      <g className="schedule-clock-art" filter="url(#schedule-soft-shadow)" transform="translate(635 398)">
        <circle cx="57" cy="57" r="54" fill="url(#schedule-metal)" stroke="#aab7ce" strokeWidth="2" />
        <circle cx="57" cy="57" r="43" fill="#fff" stroke="#d4ddea" strokeWidth="1.4" />
        {clockTicks.map((rotation) => (
          <line key={rotation} x1="57" y1="20" x2="57" y2="25" stroke="#0656f7" strokeWidth="2" strokeLinecap="round" transform={`rotate(${rotation} 57 57)`} />
        ))}
        <path d="M57 57 L57 35 M57 57 L76 67" fill="none" stroke="#075cf6" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="57" cy="57" r="4" fill="#075cf6" />
      </g>

      <text className="schedule-illustration-caption" x="386" y="542" textAnchor="middle">An example Autopilot schedule.</text>
    </svg>
  );
}

function SendIcon() {
  return (
    <svg viewBox="0 0 160 132" aria-hidden="true">
      <defs>
        <linearGradient id="send-icon-blue" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#3184ff" /><stop offset="1" stopColor="#0757ef" /></linearGradient>
        <filter id="send-icon-shadow" x="-30%" y="-30%" width="160%" height="180%"><feDropShadow dx="0" dy="8" stdDeviation="7" floodColor="#19386f" floodOpacity=".22" /></filter>
      </defs>
      <g filter="url(#send-icon-shadow)">
        <rect x="8" y="17" width="144" height="104" rx="8" fill="#fff" stroke="#ccd5e5" />
        <path d="M9 114 L67 63 Q80 52 93 63 L151 114" fill="#f8faff" stroke="#c5cfdf" />
        <path d="M8 22 L69 77 Q80 86 91 77 L152 22 Q150 17 143 17 H17 Q10 17 8 22 Z" fill="url(#send-icon-blue)" stroke="#0754ea" />
      </g>
    </svg>
  );
}

function ReviewIcon() {
  return (
    <svg viewBox="0 0 160 132" aria-hidden="true">
      <defs>
        <linearGradient id="review-paper" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#fff" /><stop offset="1" stopColor="#e8edf6" /></linearGradient>
        <filter id="review-shadow" x="-30%" y="-30%" width="160%" height="180%"><feDropShadow dx="0" dy="8" stdDeviation="7" floodColor="#19386f" floodOpacity=".22" /></filter>
      </defs>
      <g filter="url(#review-shadow)" transform="rotate(5 80 66)">
        <path d="M30 8 H133 V96 L105 124 H30 Z" fill="url(#review-paper)" stroke="#d5dce8" />
        <path d="M105 124 V99 Q105 96 109 96 H133" fill="#cfd7e5" opacity=".9" />
        <path d="M58 72 L74 88 L106 50" fill="none" stroke="#0760f7" strokeWidth="9" strokeLinecap="round" strokeLinejoin="round" />
      </g>
    </svg>
  );
}

function PauseIcon() {
  return (
    <svg viewBox="0 0 160 132" aria-hidden="true">
      <defs>
        <linearGradient id="pause-paper" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#fff" /><stop offset="1" stopColor="#e9edf5" /></linearGradient>
        <filter id="pause-shadow" x="-30%" y="-30%" width="160%" height="180%"><feDropShadow dx="0" dy="8" stdDeviation="7" floodColor="#19386f" floodOpacity=".22" /></filter>
      </defs>
      <g filter="url(#pause-shadow)">
        <circle cx="80" cy="66" r="57" fill="url(#pause-paper)" stroke="#d6deea" />
        <rect x="58" y="43" width="13" height="49" rx="4" fill="#075cf6" />
        <rect x="89" y="43" width="13" height="49" rx="4" fill="#075cf6" />
      </g>
    </svg>
  );
}

export default function ScheduleStory() {
  return (
    <section id="schedule-story" className="schedule-story" aria-labelledby="schedule-story-title">
      <div className="schedule-story-top">
        <div className="schedule-story-visual">
          <CalendarIllustration />
        </div>

        <div className="schedule-story-copy">
          <h2 id="schedule-story-title">Set the time.<br /><span>Get on with<br />your day.</span></h2>
          <p className="schedule-story-lead">Pick your days and times. Outreach sends<br />on your schedule after you launch.</p>
          <p>Send now, schedule for later, or use Autopilot.</p>
          <p>Your timezone. Your daily limits.</p>
        </div>
      </div>

      <div className="schedule-story-safety">
        <div className="schedule-story-safety-inner">
          <h3>Nothing sends until you say so.</h3>
          <div className="schedule-story-features">
            <article>
              <div className="schedule-feature-icon"><SendIcon /></div>
              <div><h4>Send from your Gmail</h4><p>Choose the account<br />people hear from.</p></div>
            </article>
            <article>
              <div className="schedule-feature-icon"><ReviewIcon /></div>
              <div><h4>Review before launch</h4><p>Check your contacts,<br />message and timing.</p></div>
            </article>
            <article>
              <div className="schedule-feature-icon"><PauseIcon /></div>
              <div><h4>Pause when you need</h4><p>Follow progress and<br />pause future sends.</p></div>
            </article>
          </div>
        </div>
      </div>
    </section>
  );
}
