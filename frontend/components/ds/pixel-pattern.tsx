import { colors } from "@/lib/design/tokens";

const COLUMNS = 5;
const ROWS = 2;
const SIZE = 8;
const GAP = 3;

/** Square n (1-based) of the pattern, as in the reference: every 3rd green, every 4th dark. */
function fillFor(n: number, onGreen: boolean): string {
  if (n % 4 === 0) return onGreen ? colors.bg : colors.ink;
  if (n % 3 === 0) return colors.green;
  return colors.mint;
}

/**
 * A small static pattern of squares in mint, green and ink. Decorative only: hidden from
 * assistive technology, no canvas, no motion. On the green band the dark squares turn
 * white and the green ones get a mint outline so they stay visible.
 */
export function PixelPattern({
  onGreen = false,
  className,
}: {
  onGreen?: boolean;
  className?: string;
}) {
  const width = COLUMNS * SIZE + (COLUMNS - 1) * GAP;
  const height = ROWS * SIZE + (ROWS - 1) * GAP;
  return (
    <svg
      aria-hidden
      focusable="false"
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      className={className}
    >
      {Array.from({ length: COLUMNS * ROWS }, (_, index) => {
        const n = index + 1;
        const fill = fillFor(n, onGreen);
        const outlined = onGreen && fill === colors.green;
        return (
          <rect
            key={n}
            x={(index % COLUMNS) * (SIZE + GAP)}
            y={Math.floor(index / COLUMNS) * (SIZE + GAP)}
            width={SIZE}
            height={SIZE}
            fill={fill}
            stroke={outlined ? colors.mint : undefined}
            strokeWidth={outlined ? 1 : undefined}
          />
        );
      })}
    </svg>
  );
}
