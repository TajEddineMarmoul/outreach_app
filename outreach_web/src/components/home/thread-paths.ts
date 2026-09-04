export type ThreadPoint = readonly [number, number];

export type SampledThread = {
  d: string;
  tip: { x: number; y: number };
};

// The lab and homepage read the same trigger percentages so a value proven in
// the debugger cannot drift when it is used by the real animation.
export const storyTriggerPercentages = {
  alex: 10,
  sam: 40,
  lena: 82,
  check: 95,
} as const;

export function clampThreadPercentage(value: number) {
  return Math.min(100, Math.max(0, value));
}

export function hasReachedThreadPercentage(progress: number, trigger: number) {
  return clampThreadPercentage(progress) >= clampThreadPercentage(trigger);
}

export function threadPointAtPercentage(path: SVGPathElement, percentage: number) {
  const length = path.getTotalLength();
  const point = path.getPointAtLength(length * clampThreadPercentage(percentage) / 100);
  return { x: point.x, y: point.y };
}

export function sampleThreadToPercentage(path: SVGPathElement, percentage: number): SampledThread {
  const clamped = clampThreadPercentage(percentage);
  const completedLength = path.getTotalLength() * clamped / 100;
  const sampleCount = Math.max(1, Math.ceil(clamped * 3));
  const points = Array.from({ length: sampleCount + 1 }, (_, index) => {
    const point = path.getPointAtLength(completedLength * index / sampleCount);
    return { x: point.x, y: point.y };
  });

  return {
    d: points.map((point, index) => (
      `${index === 0 ? "M" : "L"}${point.x} ${point.y}`
    )).join(" "),
    tip: points[points.length - 1],
  };
}

// A uniform cubic B-spline gives every join matching tangents and curvature.
// The guide points add gentle zigzags without introducing sharp corners.
export function smoothThreadPath(points: readonly ThreadPoint[]) {
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

export const threadPaths = {
  desktop: smoothThreadPath([
    [516, 332], [508, 383], [574, 370], [641, 389], [708, 373],
    [744, 414], [722, 452], [708, 516], [701, 575], [645, 606],
    [558, 575], [476, 598], [392, 556], [307, 580], [222, 612],
    [145, 638], [70, 651], [5, 680], [14, 750], [82, 792],
    [190, 786], [280, 765], [370, 748], [460, 735], [525, 758],
    [575, 782], [610, 812], [655, 798], [704, 811], [758, 793],
    [814, 793],
  ]),
  mobile: smoothThreadPath([
    [198, 226], [190, 271], [250, 252], [310, 243], [365, 258],
    [420, 250], [461, 265], [461, 330], [423, 367], [370, 350],
    [315, 361], [263, 341], [220, 351], [166, 362], [120, 386],
    [76, 395], [8, 415], [12, 465], [70, 500], [130, 520],
    [196, 507], [252, 491], [303, 475], [350, 495], [402, 509],
    [425, 562], [425, 624], [425, 656], [382, 646], [338, 660],
    [286, 645], [230, 656], [176, 640], [120, 648], [90, 639],
    [67, 615], [67, 575],
  ]),
} as const;
