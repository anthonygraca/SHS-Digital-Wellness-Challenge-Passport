/** Inline SVG glyphs (school, download, lock…) — self-contained, no icon-font dependency. */

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

/** The prototype's "download" glyph — the export affordance on screen A1. */
export function DownloadIcon({ size = 19 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M12 3a1 1 0 0 1 1 1v9.59l3.29-3.3a1 1 0 1 1 1.42 1.42l-5 5a1 1 0 0 1-1.42 0l-5-5a1 1 0 1 1 1.42-1.42l3.29 3.3V4a1 1 0 0 1 1-1z" />
      <path d="M4 18a1 1 0 0 1 1 1v1h14v-1a1 1 0 1 1 2 0v1a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-1a1 1 0 0 1 1-1z" />
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

export function SensorsIcon({ size = 20 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M7.76 16.24 6.35 17.65A7.98 7.98 0 0 1 4 12c0-2.21.9-4.21 2.35-5.65l1.41 1.41A5.98 5.98 0 0 0 6 12c0 1.66.67 3.16 1.76 4.24zm8.48 0A5.98 5.98 0 0 0 18 12c0-1.66-.67-3.16-1.76-4.24l1.41-1.41A7.98 7.98 0 0 1 20 12c0 2.21-.9 4.21-2.35 5.65l-1.41-1.41zM12 10a2 2 0 1 1 0 4 2 2 0 0 1 0-4zM3.51 20.49A11.96 11.96 0 0 1 0 12c0-3.31 1.34-6.31 3.51-8.49l1.42 1.42A9.97 9.97 0 0 0 2 12c0 2.76 1.12 5.26 2.93 7.07l-1.42 1.42zm16.98 0-1.42-1.42A9.97 9.97 0 0 0 22 12c0-2.76-1.12-5.26-2.93-7.07l1.42-1.42A11.96 11.96 0 0 1 24 12c0 3.31-1.34 6.31-3.51 8.49z" />
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

/** Material's `auto_awesome` — the mockup's mark for Guide-authored feedback (S6). */
export function AutoAwesomeIcon({ size = 20 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      focusable="false"
    >
      <path d="m19 9 1.25-2.75L23 5l-2.75-1.25L19 1l-1.25 2.75L15 5l2.75 1.25L19 9zm-7.5.5L9 4 6.5 9.5 1 12l5.5 2.5L9 20l2.5-5.5L17 12l-5.5-2.5zM19 15l-1.25 2.75L15 19l2.75 1.25L19 23l1.25-2.75L23 19l-2.75-1.25L19 15z" />
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

/** The prototype's "emergency" glyph — the crisis card's header mark (FR-E3). */
export function EmergencyIcon({ size = 20 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M10 2h4v5.13l4.44-2.56 2 3.46L15.99 10.6l4.45 2.57-2 3.46L14 14.07V19h-4v-4.93l-4.44 2.56-2-3.46 4.45-2.57L3.56 8.03l2-3.46L10 7.13V2z" />
    </svg>
  );
}

/** The prototype's "call" glyph — every crisis resource is a tel: link. */
export function PhoneIcon({ size = 20 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M6.62 10.79a15.05 15.05 0 0 0 6.59 6.59l2.2-2.2a1 1 0 0 1 1.02-.24c1.12.37 2.33.57 3.57.57a1 1 0 0 1 1 1V20a1 1 0 0 1-1 1A17 17 0 0 1 3 4a1 1 0 0 1 1-1h3.5a1 1 0 0 1 1 1c0 1.25.2 2.45.57 3.57a1 1 0 0 1-.25 1.02l-2.2 2.2z" />
    </svg>
  );
}
