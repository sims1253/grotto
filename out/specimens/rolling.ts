// rolling.ts -- exponential moving average
import { lruCache } from "./cache";

export const DEFAULT_DECAY = 0.92;

export function rollingMean(values: number[], decay: number = DEFAULT_DECAY): number {
  /** Exponentially-smoothed mean of `values`. */
  let acc = 0;
  for (const x of values) {
    acc = decay * acc + (1 - decay) * x;
  }
  return acc;
}

console.log(rollingMean([1, 2, 3]));
