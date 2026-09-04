"use client";

import { useId, useLayoutEffect, useRef } from "react";
import {
  hasReachedThreadPercentage,
  sampleThreadToPercentage,
  storyTriggerPercentages,
  threadPaths,
} from "./thread-paths";

const people = [
  { id: "alex", name: "Alex", fruit: "apples", emoji: "🍎", progress: storyTriggerPercentages.alex },
  { id: "sam", name: "Sam", fruit: "bananas", emoji: "🍌", progress: storyTriggerPercentages.sam },
  { id: "lena", name: "Lena", fruit: "strawberries", emoji: "🍓", progress: storyTriggerPercentages.lena },
];

const THREAD_START = 750;
const THREAD_DURATION = 3000;
const CHECK_PROGRESS = storyTriggerPercentages.check;
const EASE_IN_OUT = "ease-in-out";

function easeInOutProgressAtTime(time: number) {
  let low = 0;
  let high = 1;
  for (let index = 0; index < 24; index++) {
    const parameter = (low + high) / 2;
    const inverse = 1 - parameter;
    const x = 3 * inverse ** 2 * parameter * .42
      + 3 * inverse * parameter ** 2 * .58
      + parameter ** 3;
    if (x < time) low = parameter;
    else high = parameter;
  }
  const parameter = (low + high) / 2;
  return 3 * parameter ** 2 - 2 * parameter ** 3;
}

function TypedLine({ children, x, y }: { children: string; x: number; y: number }) {
  let variable = false;
  return (
    <text x={x} y={y} xmlSpace="preserve">
      {Array.from(children).map((character, index) => {
        if (character === "[") variable = true;
        const blue = variable;
        if (character === "]") variable = false;
        return <tspan key={index} className="template-character" fill={blue ? "#0055ff" : undefined}>{character}</tspan>;
      })}
    </text>
  );
}

function Envelope({ person }: { person?: typeof people[number] }) {
  const id = useId().replace(/:/g, "");
  const template = !person;
  const bottom = template ? 260 : person.id === "lena" ? 210 : 240;
  const fold = template ? 174 : person.id === "lena" ? 133 : 153;
  const letterX = person?.id === "lena" ? 40 : 43;
  const fill = (name: string) => `url(#${id}-${name})`;

  return (
    <div
      className={`story-envelope story-envelope--${person?.id ?? "template"}`}
      data-thread-trigger={person?.id}
    >
      {template && <p className="story-template-label">You write this once</p>}
      <div className="envelope-reveal">
        <div className="envelope-float">
          <svg className="envelope-paperwork" viewBox={`0 0 280 ${bottom}`} aria-hidden="true">
            <defs>
              <linearGradient id={`${id}-back`} x1="0" y1="0" x2="1" y2="1">
                <stop stopColor={template ? "#127bff" : "#f4f8ff"} />
                <stop offset="1" stopColor={template ? "#0346f6" : "#e8effc"} />
              </linearGradient>
              <linearGradient id={`${id}-paper`} x1="0" y1="0" x2=".6" y2="1">
                <stop stopColor="#fff" /><stop offset="1" stopColor="#fcfdff" />
              </linearGradient>
              <linearGradient id={`${id}-left`} x1="0" y1="0" x2="1" y2="1">
                <stop stopColor={template ? "#308dff" : "#fff"} />
                <stop offset="1" stopColor={template ? "#0062fa" : "#f1f6fe"} />
              </linearGradient>
              <linearGradient id={`${id}-right`} x1="1" y1="0" x2="0" y2="1">
                <stop stopColor={template ? "#0048ff" : "#fff"} />
                <stop offset="1" stopColor={template ? "#0059fb" : "#f0f5fd"} />
              </linearGradient>
              <linearGradient id={`${id}-front`} x1=".3" y1="0" x2=".6" y2="1">
                <stop stopColor={template ? "#2585ff" : "#fff"} />
                <stop offset="1" stopColor={template ? "#0061ff" : "#f3f7fd"} />
              </linearGradient>
              <clipPath id={`${id}-clip`}><rect x="-2" y="-4" width="284" height={bottom + 5} rx="13" /></clipPath>
            </defs>
            <g stroke={template ? "#60a1ff" : "#cbdcff"} strokeWidth="1.2" strokeLinejoin="round">
              <path d={`M1 103 Q1 95 9 89 L126 13 Q140 3 154 13 L271 89 Q279 95 279 103 V${bottom - 14} Q279 ${bottom - 1} 265 ${bottom - 1} H15 Q1 ${bottom - 1} 1 ${bottom - 14} Z`} fill={fill("back")} />
              <path d="M4 99 L136 187 Q140 191 145 187 L276 99" fill="none" opacity=".4" />
              <g clipPath={fill("clip")}>
                <g className="envelope-letter">
                  <rect x="23" y="2" width="234" height="214" rx="10" fill={fill("paper")} stroke="#c5d8ff" strokeWidth="1.6" />
                  <g className={`envelope-letter-text ${template ? "is-template" : ""}`} stroke="none" fill="#080e4b">
                    {template ? <>
                      <TypedLine x={46} y={58}>Hi [Name],</TypedLine>
                      <TypedLine x={46} y={102}>I like [Fruit].</TypedLine>
                    </> : <>
                      <text x={letterX} y="57">Hi<tspan dx="7" fill="#0055ff">{person.name}</tspan>,</text>
                      <text x={letterX} y="102">I like<tspan dx="7" fill="#0055ff">{person.fruit}</tspan><tspan className="envelope-fruit" dx="7">{person.emoji}</tspan></text>
                    </>}
                  </g>
                </g>
              </g>
              <path d={`M1 101 L147 197 L14 ${bottom - 1} Q1 ${bottom - 1} 1 ${bottom - 14} Z`} fill={fill("left")} />
              <path d={`M279 101 L133 197 L266 ${bottom - 1} Q279 ${bottom - 1} 279 ${bottom - 14} Z`} fill={fill("right")} />
              <path d={`M5 ${bottom - 6} L123 ${fold + 3} Q140 ${fold - 9} 157 ${fold + 3} L275 ${bottom - 6} Q272 ${bottom - 1} 265 ${bottom - 1} H15 Q8 ${bottom - 1} 5 ${bottom - 6} Z`} fill={fill("front")} />
              <path d={`M3 105 V${bottom - 15} Q3 ${bottom - 3} 16 ${bottom - 3} H264 Q277 ${bottom - 3} 277 ${bottom - 15} V105`} fill="none" stroke={template ? "#8bbfff" : "#a9c8ff"} opacity=".55" />
            </g>
          </svg>
        </div>
      </div>
    </div>
  );
}

export default function EnvelopeStory() {
  const scene = useRef<HTMLDivElement>(null);
  const animations = useRef<Animation[]>([]);

  useLayoutEffect(() => {
    const root = scene.current;
    if (!root) return;
    const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    const mobileLayout = window.matchMedia("(max-width: 1100px) and (orientation: portrait)");
    let threadFrame: number | null = null;

    const clear = () => {
      if (threadFrame !== null) cancelAnimationFrame(threadFrame);
      threadFrame = null;
      animations.current.forEach((animation) => animation.cancel());
      animations.current = [];
      root.removeAttribute("data-thread-animating");
      root.querySelectorAll<HTMLElement>("[data-thread-trigger]").forEach((element) => {
        element.removeAttribute("data-thread-visible");
      });
    };
    const animate = (selector: string, frames: Keyframe[], options: KeyframeAnimationOptions) => {
      const created: Animation[] = [];
      root.querySelectorAll(selector).forEach((element) => {
        const animation = element.animate(frames, { fill: "both", ...options });
        animations.current.push(animation);
        created.push(animation);
      });
      return created;
    };
    const start = () => {
      clear();
      const activeLayout = mobileLayout.matches ? "mobile" : "desktop";
      const sourcePath = root.querySelector<SVGPathElement>(`.story-thread--${activeLayout} [data-thread-source]`);
      const progressPath = root.querySelector<SVGPathElement>(`.story-thread--${activeLayout} [data-thread-progress]`);

      // With reduced motion (or no JavaScript), the complete illustration is shown.
      if (preference.matches || !sourcePath || !progressPath) {
        root.querySelectorAll<SVGPathElement>("[data-thread-progress]").forEach((path) => {
          const source = path.parentElement?.querySelector<SVGPathElement>("[data-thread-source]");
          if (source) path.setAttribute("d", source.getAttribute("d") ?? "");
        });
        return;
      }

      const animationStartedAt = performance.now();
      progressPath.setAttribute("d", sampleThreadToPercentage(sourcePath, 0).d);
      progressPath.dataset.progress = "0";
      root.querySelectorAll<HTMLElement>("[data-thread-trigger]").forEach((element) => {
        element.dataset.threadVisible = "false";
      });
      root.dataset.threadAnimating = "true";

      const pop = [
        { opacity: 0, transform: "translateY(20px) scale(.86)" },
        { opacity: 1, transform: "translateY(10px) scale(.93)", offset: .18 },
        { opacity: 1, transform: "translateY(-3px) scale(1.025)", offset: .76 },
        { opacity: 1, transform: "translateY(0) scale(1)" },
      ];
      // The template has its own short intro. Recipient visibility is not
      // scheduled: it is toggled below by the live path percentage itself.
      animate(".story-envelope--template .envelope-reveal", pop, {
        duration: 300, delay: 40, easing: EASE_IN_OUT,
      });
      animate(".story-envelope--template .envelope-letter", [
        { transform: "translateY(119px)" },
        { transform: "translateY(-4px)", offset: .8 },
        { transform: "translateY(0)" },
      ], { duration: 520, delay: 130, easing: EASE_IN_OUT });
      animate(".story-envelope--template .envelope-float", [
        { transform: "translate(0, 0) rotate(0deg)" },
        { transform: "translate(2px, -6px) rotate(.65deg)", offset: .5 },
        { transform: "translate(0, 0) rotate(0deg)" },
      ], { duration: 4700, delay: 690, iterations: Infinity, easing: EASE_IN_OUT });
      animate(".story-template-label", [{ opacity: 0 }, { opacity: 1 }], { duration: 220, delay: 160, easing: EASE_IN_OUT });
      root.querySelectorAll(".template-character").forEach((character, index) => {
        animations.current.push(character.animate([{ opacity: 0 }, { opacity: 1 }], {
          duration: 1, delay: 300 + index * 15 + (index > 9 ? 60 : 0), fill: "both", easing: EASE_IN_OUT,
        }));
      });

      animate(`.story-thread--${activeLayout} [data-thread-sway]`, [
        { transform: "translateY(0)" },
        { transform: "translateY(-4px)", offset: .5 },
        { transform: "translateY(0)" },
      ], { duration: 6400, delay: THREAD_START, iterations: Infinity, easing: EASE_IN_OUT });

      const drawThread = (now: number) => {
        const time = Math.min(1, Math.max(0, (now - animationStartedAt - THREAD_START) / THREAD_DURATION));
        const progress = easeInOutProgressAtTime(time);
        const percentage = progress * 100;
        progressPath.setAttribute("d", sampleThreadToPercentage(sourcePath, percentage).d);
        progressPath.dataset.progress = percentage.toFixed(3);
        people.forEach(({ id, progress: trigger }) => {
          const target = root.querySelector<HTMLElement>(`[data-thread-trigger="${id}"]`);
          if (target) target.dataset.threadVisible = String(hasReachedThreadPercentage(percentage, trigger));
        });
        const delivered = root.querySelector<HTMLElement>("[data-thread-trigger=check]");
        if (delivered) delivered.dataset.threadVisible = String(hasReachedThreadPercentage(percentage, CHECK_PROGRESS));
        if (time < 1) threadFrame = requestAnimationFrame(drawThread);
        else threadFrame = null;
      };
      threadFrame = requestAnimationFrame(drawThread);
    };

    start();
    const respectReducedMotion = () => start();
    const restartForLayout = () => start();
    preference.addEventListener("change", respectReducedMotion);
    mobileLayout.addEventListener("change", restartForLayout);
    return () => {
      clear();
      preference.removeEventListener("change", respectReducedMotion);
      mobileLayout.removeEventListener("change", restartForLayout);
    };
  }, []);

  return (
    <div className="envelope-story" ref={scene}>
      <div className="story-art" role="img" aria-label="Write one template: Hi [Name], I like [Fruit]. A blue thread carries it to three personal emails: Alex likes apples, Sam likes bananas, and Lena likes strawberries. Each person gets their own email.">
        {(["desktop", "mobile"] as const).map((layout) => (
          <svg key={layout} className={`story-thread story-thread--${layout}`} viewBox={layout === "desktop" ? "0 0 1042 941" : "0 0 600 670"} fill="none" aria-hidden="true">
            <g data-thread-sway>
              <path data-thread-source d={threadPaths[layout]} vectorEffect="non-scaling-stroke" />
              <path data-thread-progress d={threadPaths[layout]} vectorEffect="non-scaling-stroke" />
            </g>
          </svg>
        ))}
        <Envelope />
        {people.map((person) => <Envelope key={person.id} person={person} />)}
        <div className="story-delivered" data-thread-trigger="check" aria-hidden="true">
          <span className="story-delivered-icon-shell">
            <svg className="story-delivered-icon" viewBox="0 0 52 52" fill="none">
              <defs><linearGradient id="story-check-green" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#00d3a0" /><stop offset="1" stopColor="#00b47d" /></linearGradient></defs>
              <circle cx="26" cy="26" r="25" fill="url(#story-check-green)" />
              <path className="story-check-stroke" d="m15 26 8 8 15-17" stroke="white" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" pathLength="1" strokeDasharray="1 1" />
            </svg>
          </span>
          <p className="story-delivered-text">Each person gets<br />their own email.</p>
        </div>
      </div>
    </div>
  );
}
