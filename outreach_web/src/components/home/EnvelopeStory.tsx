"use client";

import { useEffect, useId, useRef } from "react";

const people = [
  { id: "alex", name: "Alex", fruit: "apples", emoji: "🍎" },
  { id: "sam", name: "Sam", fruit: "bananas", emoji: "🍌" },
  { id: "lena", name: "Lena", fruit: "strawberries", emoji: "🍓" },
];

// Draw the route through 3.75 seconds and begin the delivery pop just before
// the endpoint so the badge settles on the same frame as the completed line.
const THREAD_START = 750;
const THREAD_DURATION = 3000;
const CHECK_LEAD = 800;
const EASE_IN_OUT = "ease-in-out";
const RECIPIENT_LEAD = 100;

type ThreadPoint = readonly [number, number];

function easeInOutTimeForProgress(progress: number) {
  // Convert a position along the line back to the time of the matching point
  // on CSS ease-in-out. This keeps each envelope synchronized with the moving
  // tip even though the thread now accelerates and decelerates.
  let low = 0;
  let high = 1;
  for (let index = 0; index < 24; index++) {
    const parameter = (low + high) / 2;
    const easedProgress = 3 * parameter ** 2 - 2 * parameter ** 3;
    if (easedProgress < progress) low = parameter;
    else high = parameter;
  }
  const parameter = (low + high) / 2;
  const inverse = 1 - parameter;
  return 3 * inverse ** 2 * parameter * .42
    + 3 * inverse * parameter ** 2 * .58
    + parameter ** 3;
}

// A uniform cubic B-spline gives every join matching tangents AND curvature.
// The guide points shape broad bends without hand-joined corners or flat spots.
function smoothThreadPath(points: readonly ThreadPoint[]) {
  const first = points[0];
  const last = points[points.length - 1];
  const guide = [first, first, ...points, last, last];
  let path = `M${first[0]} ${first[1]}`;
  for (let index = 0; index < guide.length - 3; index++) {
    const [, a, b, c] = guide.slice(index, index + 4);
    path += ` C${(2 * a[0] + b[0]) / 3} ${(2 * a[1] + b[1]) / 3}`;
    path += ` ${(a[0] + 2 * b[0]) / 3} ${(a[1] + 2 * b[1]) / 3}`;
    path += ` ${(a[0] + 4 * b[0] + c[0]) / 6} ${(a[1] + 4 * b[1] + c[1]) / 6}`;
  }
  return path;
}

const threadPaths = {
  desktop: smoothThreadPath([
    [516, 332], [508, 383], [608, 376], [734, 381], [744, 414],
    [722, 452], [708, 516], [701, 575], [633, 603], [515, 583],
    [399, 556], [307, 573], [188, 616], [70, 651], [5, 680],
    [14, 750], [80, 790], [205, 792], [357, 760], [496, 738],
    [575, 775], [605, 814], [690, 807], [814, 793],
  ]),
  mobile: smoothThreadPath([
    [198, 226], [190, 271], [282, 246], [365, 248], [461, 265],
    [461, 330], [405, 363], [312, 350], [232, 345], [166, 362],
    [76, 395], [8, 415], [12, 465], [100, 510], [209, 517],
    [278, 490], [332, 475], [402, 509], [425, 562], [425, 624],
    [425, 656], [338, 656], [198, 646], [90, 639], [67, 615], [67, 575],
  ]),
};

function threadProgressAtTarget(root: HTMLDivElement, mobile: boolean, target: Element) {
  const path = root.querySelector<SVGPathElement>(`.story-thread--${mobile ? "mobile" : "desktop"} [data-thread]`);
  const svg = path?.ownerSVGElement;
  if (!path || !svg) return 0;
  const frame = svg.getBoundingClientRect();
  const viewBox = svg.viewBox.baseVal;

  const length = path.getTotalLength();
  const samples = Array.from({ length: 401 }, (_, index) => ({
    progress: index / 400,
    point: path.getPointAtLength(length * index / 400),
  }));

  const bounds = target.getBoundingClientRect();
  // Compare in SVG coordinates so zoom, centered frames and screen size do
  // not change the percentage where the moving line reaches a target.
  const left = (bounds.left - frame.left) / frame.width * viewBox.width;
  const right = (bounds.right - frame.left) / frame.width * viewBox.width;
  const top = (bounds.top - frame.top) / frame.height * viewBox.height;
  const bottom = (bounds.bottom - frame.top) / frame.height * viewBox.height;
  const arrival = samples.find(({ point }) => point.x >= left && point.x <= right && point.y >= top && point.y <= bottom);
  const closest = arrival ?? samples.reduce((best, sample) => {
    const distance = (p: ThreadPoint) => (p[0] - (left + right) / 2) ** 2 + (p[1] - (top + bottom) / 2) ** 2;
    return distance([sample.point.x, sample.point.y]) < distance([best.point.x, best.point.y]) ? sample : best;
  });
  return closest.progress;
}

function threadTimeAtProgress(progress: number) {
  return THREAD_START + easeInOutTimeForProgress(progress) * THREAD_DURATION;
}

function envelopeArrivals(root: HTMLDivElement, mobile: boolean) {
  return people.map(({ id }) => {
    const target = root.querySelector(`.story-envelope--${id}`)!;
    const progress = threadProgressAtTarget(root, mobile, target);
    return {
      id,
      progress,
      delay: Math.max(THREAD_START, threadTimeAtProgress(progress) - RECIPIENT_LEAD),
    };
  });
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
    <div className={`story-envelope story-envelope--${person?.id ?? "template"}`}>
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

  useEffect(() => {
    const root = scene.current;
    if (!root) return;
    const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    const mobileLayout = window.matchMedia("(max-width: 1100px) and (orientation: portrait)");
    let resizeTimer: number | undefined;
    let measuredWidth = root.getBoundingClientRect().width;
    let measuredHeight = root.getBoundingClientRect().height;

    const clear = () => {
      animations.current.forEach((animation) => animation.cancel());
      animations.current = [];
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
      // With reduced motion (or no JavaScript), the complete illustration is shown.
      if (preference.matches) return;

      const pop = [
        { opacity: 0, transform: "translateY(20px) scale(.86)" },
        { opacity: 1, transform: "translateY(10px) scale(.93)", offset: .18 },
        { opacity: 1, transform: "translateY(-3px) scale(1.025)", offset: .76 },
        { opacity: 1, transform: "translateY(0) scale(1)" },
      ];
      const deliveredPop = [
        { transform: "scale(.58)" },
        { transform: "scale(1.1)", offset: .68 },
        { transform: "scale(1)" },
      ];
      // Trigger envelopes when the moving tip enters their position, rather
      // than stopping the line and starting a new section for each recipient.
      [{ id: "template", delay: 40 }, ...envelopeArrivals(root, mobileLayout.matches)].forEach(({ id, delay }, index) => {
        const target = `.story-envelope--${id}`;
        animate(`${target} .envelope-reveal`, pop, {
          duration: id === "template" ? 300 : 230,
          delay,
          easing: EASE_IN_OUT,
        });
        animate(`${target} .envelope-letter`, [
          { transform: "translateY(119px)" },
          { transform: "translateY(-4px)", offset: .8 },
          { transform: "translateY(0)" },
        ], {
          duration: id === "template" ? 520 : 290,
          delay: delay + (id === "template" ? 90 : 30),
          easing: EASE_IN_OUT,
        });
        animate(`${target} .envelope-float`, [
          { transform: "translate(0, 0) rotate(0deg)" },
          { transform: `translate(${index % 2 ? -2 : 2}px, -6px) rotate(${index % 2 ? -.65 : .65}deg)`, offset: .5 },
          { transform: "translate(0, 0) rotate(0deg)" },
        ], { duration: 4700 + index * 530, delay: delay + 650, iterations: Infinity, easing: EASE_IN_OUT });
      });
      animate(".story-template-label", [{ opacity: 0 }, { opacity: 1 }], { duration: 220, delay: 160, easing: EASE_IN_OUT });
      root.querySelectorAll(".template-character").forEach((character, index) => {
        animations.current.push(character.animate([{ opacity: 0 }, { opacity: 1 }], {
          duration: 1, delay: 300 + index * 15 + (index > 9 ? 60 : 0), fill: "both", easing: EASE_IN_OUT,
        }));
      });

      const activeLayout = mobileLayout.matches ? "mobile" : "desktop";
      const activeThread = `.story-thread--${activeLayout} [data-thread]`;
      animate(activeThread, [{ strokeDashoffset: 1 }, { strokeDashoffset: 0 }], {
        delay: THREAD_START, duration: THREAD_DURATION, easing: EASE_IN_OUT,
      });
      animate(`.story-thread--${activeLayout} [data-thread-sway]`, [
        { transform: "translateY(0)" },
        { transform: "translateY(-4px)", offset: .5 },
        { transform: "translateY(0)" },
      ], { duration: 6400, delay: THREAD_START, iterations: Infinity, easing: EASE_IN_OUT });
      // The badge is fully visible when the moving tip reaches it. Its start
      // follows that target percentage instead of a fixed global timestamp.
      const deliveredTarget = root.querySelector(".story-delivered-icon-shell")!;
      const deliveredProgress = threadProgressAtTarget(root, mobileLayout.matches, deliveredTarget);
      const deliveredArrival = threadTimeAtProgress(deliveredProgress);
      const deliveredStart = Math.max(THREAD_START, deliveredArrival - CHECK_LEAD);
      const deliveredDuration = Math.max(1, deliveredArrival - deliveredStart);
      animate(".story-delivered-icon", [{ opacity: 0 }, { opacity: 1 }], { duration: 1, delay: deliveredStart, easing: EASE_IN_OUT });
      animate(".story-delivered-icon", deliveredPop, { duration: deliveredDuration, delay: deliveredStart, easing: EASE_IN_OUT });
      animate(".story-delivered-text", [{ opacity: 0, transform: "translateX(-5px)" }, { opacity: 1, transform: "translateX(0)" }], { duration: Math.min(400, deliveredDuration), delay: deliveredStart, easing: EASE_IN_OUT });
    };

    start();
    const respectReducedMotion = () => {
      if (preference.matches) clear();
    };
    const resizeObserver = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      if (Math.abs(width - measuredWidth) < 1 && Math.abs(height - measuredHeight) < 1) return;
      measuredWidth = width;
      measuredHeight = height;
      window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(start, 120);
    });
    resizeObserver.observe(root);
    preference.addEventListener("change", respectReducedMotion);
    return () => {
      resizeObserver.disconnect();
      window.clearTimeout(resizeTimer);
      clear();
      preference.removeEventListener("change", respectReducedMotion);
    };
  }, []);

  return (
    <div className="envelope-story" ref={scene}>
      <div className="story-art" role="img" aria-label="Write one template: Hi [Name], I like [Fruit]. A blue thread carries it to three personal emails: Alex likes apples, Sam likes bananas, and Lena likes strawberries. Each person gets their own email.">
        {(["desktop", "mobile"] as const).map((layout) => (
          <svg key={layout} className={`story-thread story-thread--${layout}`} viewBox={layout === "desktop" ? "0 0 1042 941" : "0 0 600 670"} fill="none" aria-hidden="true">
            <g data-thread-sway>
              <path data-thread d={threadPaths[layout]} pathLength="1" strokeDasharray="1 1" strokeDashoffset="0" vectorEffect="non-scaling-stroke" />
            </g>
          </svg>
        ))}
        <Envelope />
        {people.map((person) => <Envelope key={person.id} person={person} />)}
        <div className="story-delivered" aria-hidden="true">
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
