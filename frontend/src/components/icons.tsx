/** Inline SVG glyphs (school, lock) — self-contained, no icon-font dependency. */

export function SchoolIcon({ size = 22 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M12 3 1 9l11 6 9-4.91V17h2V9L12 3zm0 13L5 12.2v-1.99l7 3.82 7-3.82v1.99L12 16z" />
      <path d="M6 13.18v2.32L12 19l6-3.5v-2.32l-6 3.27-6-3.27z" opacity="0.85" />
    </svg>
  );
}

export function LockIcon({ size = 16 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M12 1a5 5 0 0 0-5 5v3H6a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-9a2 2 0 0 0-2-2h-1V6a5 5 0 0 0-5-5zm-3 8V6a3 3 0 1 1 6 0v3H9z" />
    </svg>
  );
}

export function CheckCircleIcon({ size = 20 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm-1.2 14.2-4-4 1.4-1.4 2.6 2.6 5.6-5.6 1.4 1.4-7 7z" />
    </svg>
  );
}

export function BoltIcon({ size = 20 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M11 21h-1l1-7H6.5a.5.5 0 0 1-.4-.8l7-11h1l-1 7h4.5a.5.5 0 0 1 .4.8l-7 11z" />
    </svg>
  );
}

export function TrophyIcon({ size = 20 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M18 2H6v2H2v3a4 4 0 0 0 4 4h.35A6 6 0 0 0 11 14.92V18H8v2h8v-2h-3v-3.08A6 6 0 0 0 17.65 11H18a4 4 0 0 0 4-4V4h-4V2zM6 9a2 2 0 0 1-2-2V6h2v3zm14-2a2 2 0 0 1-2 2V6h2v1z" />
    </svg>
  );
}
