"use client";

import Link from "next/link";
import { type CSSProperties, useLayoutEffect, useRef, useState } from "react";
import {
  clampThreadPercentage,
  hasReachedThreadPercentage,
  sampleThreadToPercentage,
  storyTriggerPercentages,
  threadPaths,
  threadPointAtPercentage,
} from "./thread-paths";
import "./line-animation-lab.css";

type Trigger = {
  id: string;
  label: string;
  percentage: number;
  color: string;
};

type PathPoint = {
  x: number;
  y: number;
};

const initialTriggers: Trigger[] = [
  { id: "alex", label: "Alex", percentage: storyTriggerPercentages.alex, color: "#0062ff" },
  { id: "sam", label: "Sam", percentage: storyTriggerPercentages.sam, color: "#6d5dfc" },
  { id: "lena", label: "Lena", percentage: storyTriggerPercentages.lena, color: "#e84c8b" },
  { id: "check", label: "Check", percentage: storyTriggerPercentages.check, color: "#00b985" },
];

export default function LineAnimationLab() {
  const sourcePathRef = useRef<SVGPathElement>(null);
  const [progress, setProgress] = useState(0);
  const [tip, setTip] = useState<PathPoint>({ x: 516, y: 332 });
  const [progressPath, setProgressPath] = useState("M516 332");
  const [triggers, setTriggers] = useState(initialTriggers);
  const [triggerPoints, setTriggerPoints] = useState<Record<string, PathPoint>>({});

  useLayoutEffect(() => {
    const path = sourcePathRef.current;
    if (!path) return;

    const completed = sampleThreadToPercentage(path, progress);
    setTip(completed.tip);
    setProgressPath(completed.d);
    setTriggerPoints(Object.fromEntries(
      triggers.map((trigger) => [trigger.id, threadPointAtPercentage(path, trigger.percentage)]),
    ));
  }, [progress, triggers]);

  const updateTrigger = (id: string, percentage: number) => {
    const nextPercentage = clampThreadPercentage(Number.isFinite(percentage) ? percentage : 0);
    setTriggers((current) => current.map((trigger) => (
      trigger.id === id ? { ...trigger, percentage: nextPercentage } : trigger
    )));
  };

  return (
    <main className="line-lab">
      <header className="line-lab__header">
        <div>
          <p className="line-lab__eyebrow">Animation debugger</p>
          <h1>Line percentage lab</h1>
          <p>Move the slider. Every marker is calculated from the real SVG path length.</p>
        </div>
        <Link href="/" className="line-lab__home-link">Back to homepage</Link>
      </header>

      <div className="line-lab__workspace">
        <aside className="line-lab__controls" aria-label="Animation controls">
          <section className="line-lab__control-card line-lab__progress-card">
            <div className="line-lab__control-heading">
              <div>
                <span>Line progress</span>
                <small>One-to-one, with no easing</small>
              </div>
              <output htmlFor="line-progress">{progress.toFixed(1)}%</output>
            </div>
            <input
              id="line-progress"
              className="line-lab__range"
              type="range"
              min="0"
              max="100"
              step="0.1"
              value={progress}
              onChange={(event) => setProgress(Number(event.target.value))}
              aria-label="Line progress percentage"
            />
            <div className="line-lab__presets" aria-label="Progress presets">
              {[0, 25, 50, 75, 100].map((percentage) => (
                <button
                  key={percentage}
                  type="button"
                  className={progress === percentage ? "is-active" : undefined}
                  onClick={() => setProgress(percentage)}
                >
                  {percentage}%
                </button>
              ))}
            </div>
            <p className="line-lab__coordinates">
              Current point <span>x {tip.x.toFixed(1)}</span><span>y {tip.y.toFixed(1)}</span>
            </p>
          </section>

          <section className="line-lab__control-card">
            <div className="line-lab__section-heading">
              <div>
                <span>Popup positions</span>
                <small>Change a percentage to move that popup.</small>
              </div>
            </div>
            <div className="line-lab__trigger-list">
              {triggers.map((trigger) => (
                <div className="line-lab__trigger-control" key={trigger.id}>
                  <label htmlFor={`trigger-${trigger.id}`}>
                    <i style={{ background: trigger.color }} aria-hidden="true" />
                    {trigger.label}
                  </label>
                  <input
                    id={`trigger-${trigger.id}`}
                    type="range"
                    min="0"
                    max="100"
                    step="1"
                    value={trigger.percentage}
                    onChange={(event) => updateTrigger(trigger.id, Number(event.target.value))}
                    aria-label={`${trigger.label} popup percentage`}
                  />
                  <div className="line-lab__number-wrap">
                    <input
                      type="number"
                      min="0"
                      max="100"
                      step="1"
                      value={trigger.percentage}
                      onChange={(event) => updateTrigger(trigger.id, Number(event.target.value))}
                      aria-label={`${trigger.label} exact popup percentage`}
                    />
                    <span>%</span>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <p className="line-lab__note">
            A popup becomes visible when line progress reaches its percentage. Its anchor dot is the exact point returned by <code>getPointAtLength</code>.
          </p>
        </aside>

        <section className="line-lab__canvas-card" aria-label="Interactive line preview">
          <div className="line-lab__canvas-heading">
            <div>
              <span>Live path</span>
              <small>The pale line is the full route. Blue is the completed part.</small>
            </div>
            <strong>{progress.toFixed(1)}%</strong>
          </div>

          <div className="line-lab__canvas">
            <svg viewBox="0 300 880 570" role="img" aria-label={`Line drawn to ${progress.toFixed(1)} percent`}>
              <defs>
                <filter id="line-lab-tip-shadow" x="-100%" y="-100%" width="300%" height="300%">
                  <feDropShadow dx="0" dy="5" stdDeviation="5" floodColor="#003bb7" floodOpacity=".28" />
                </filter>
              </defs>

              <path ref={sourcePathRef} className="line-lab__route-guide" data-line-source d={threadPaths.desktop} />
              <path
                className="line-lab__route-progress"
                data-line-progress
                d={progressPath}
              />

              {triggers.map((trigger) => {
                const point = triggerPoints[trigger.id];
                if (!point) return null;
                const visible = hasReachedThreadPercentage(progress, trigger.percentage);
                const triggerStyle = { "--trigger-color": trigger.color } as CSSProperties;

                return (
                  <g
                    key={trigger.id}
                    className="line-lab__trigger"
                    data-trigger={trigger.id}
                    data-visible={visible}
                    transform={`translate(${point.x} ${point.y})`}
                    style={triggerStyle}
                  >
                    <circle className="line-lab__trigger-guide" r="8" />
                    <text className="line-lab__trigger-percentage" y="25" textAnchor="middle">
                      {trigger.percentage}%
                    </text>
                    <g className={`line-lab__popup ${visible ? "is-visible" : ""}`}>
                      <rect x="-62" y="-72" width="124" height="52" rx="13" />
                      <path d="M-9 -21 L0 -9 L9 -21 Z" />
                      <circle cy="-49" r="7" />
                      <text x="13" y="-44" textAnchor="middle">{trigger.label}</text>
                    </g>
                  </g>
                );
              })}

              <g className="line-lab__tip" data-tip transform={`translate(${tip.x} ${tip.y})`}>
                <circle className="line-lab__tip-halo" r="18" />
                <circle className="line-lab__tip-dot" r="9" />
                <text y="-28" textAnchor="middle">{progress.toFixed(1)}%</text>
              </g>
            </svg>
          </div>
        </section>
      </div>
    </main>
  );
}
