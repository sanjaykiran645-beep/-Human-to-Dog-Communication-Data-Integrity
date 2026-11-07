export default function Logo({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 36 36" aria-hidden="true">
      <rect width="36" height="36" rx="11" fill="#382820" />
      <rect x="1.5" y="1.5" width="33" height="33" rx="9.5" fill="none" stroke="#D8C9A7" strokeOpacity="0.35" />
      <path
        d="M8 20.5c4.6-9 15.4-9 20 0"
        fill="none"
        stroke="#D8C9A7"
        strokeWidth="2.2"
        strokeLinecap="round"
      />
      <path
        d="M11.5 20.5c3.3-5.8 9.7-5.8 13 0"
        fill="none"
        stroke="#A66B55"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <circle cx="18" cy="24" r="2.6" fill="#762F3D" stroke="#F7F2E8" strokeWidth="1.2" />
    </svg>
  );
}
