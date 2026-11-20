// Small line-icon set for the CRM shell. Stroke-only, currentColor, 1.6px — the same
// visual language as components/icons.tsx, kept separate so the ML module is untouched.

import type { ReactNode } from "react";

type IconProps = { className?: string };

function Svg({ className, children }: IconProps & { children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className ?? "h-[18px] w-[18px]"}
    >
      {children}
    </svg>
  );
}

export const WaffleIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <rect x="4" y="4" width="6" height="6" rx="1" />
    <rect x="14" y="4" width="6" height="6" rx="1" />
    <rect x="4" y="14" width="6" height="6" rx="1" />
    <rect x="14" y="14" width="6" height="6" rx="1" />
  </Svg>
);

export const SearchIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <circle cx="11" cy="11" r="6.5" />
    <path d="m20 20-3.6-3.6" />
  </Svg>
);

export const BulbIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="M9 18h6M10 21h4" />
    <path d="M12 3a6 6 0 0 0-3.5 10.9c.5.4.8 1 .8 1.6V17h5.4v-1.5c0-.6.3-1.2.8-1.6A6 6 0 0 0 12 3Z" />
  </Svg>
);

export const PlusIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="M12 5v14M5 12h14" />
  </Svg>
);

export const FunnelIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="M4 5h16l-6.2 7.4V19l-3.6-1.8v-4.8L4 5Z" />
  </Svg>
);

export const GearIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.9 1.2V21a2 2 0 1 1-4 0v-.2A1.7 1.7 0 0 0 7 19.4a1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.7 1.7 0 0 0 3.6 15H3a2 2 0 1 1 0-4h.2A1.7 1.7 0 0 0 4.6 7a1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.7 1.7 0 0 0 9 3.6V3a2 2 0 1 1 4 0v.2A1.7 1.7 0 0 0 15 4.6a1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1A1.7 1.7 0 0 0 20.4 9H21a2 2 0 1 1 0 4h-.2a1.7 1.7 0 0 0-1.4 2Z" />
  </Svg>
);

export const HelpIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <circle cx="12" cy="12" r="9" />
    <path d="M9.8 9.2a2.4 2.4 0 1 1 3.5 2.1c-.7.4-1.3 1-1.3 1.9" />
    <path d="M12 16.6h.01" />
  </Svg>
);

export const ChevronDownIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="m6 9 6 6 6-6" />
  </Svg>
);

export const ChevronLeftIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="m15 6-6 6 6 6" />
  </Svg>
);

export const ChevronRightIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="m9 6 6 6-6 6" />
  </Svg>
);

export const HomeIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-4v-6h-6v6H5a1 1 0 0 1-1-1Z" />
  </Svg>
);

export const ClockIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 7.5V12l3 2" />
  </Svg>
);

export const PinIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="M9 4h6l-1 5 3 3v2H7v-2l3-3-1-5Z" />
    <path d="M12 14v6" />
  </Svg>
);

export const DashboardIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <rect x="4" y="4" width="7" height="7" rx="1.4" />
    <rect x="13" y="4" width="7" height="4" rx="1.4" />
    <rect x="13" y="10" width="7" height="10" rx="1.4" />
    <rect x="4" y="13" width="7" height="7" rx="1.4" />
  </Svg>
);

export const TaskIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <rect x="5" y="4" width="14" height="16" rx="2" />
    <path d="M9 9h6M9 13h6M9 17h4" />
  </Svg>
);

export const BuildingIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="M5 20V5a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v15" />
    <path d="M15 9h3a1 1 0 0 1 1 1v10" />
    <path d="M8 8h2M8 12h2M8 16h2M3 20h18" />
  </Svg>
);

export const UserIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <circle cx="12" cy="8.5" r="3.5" />
    <path d="M5 20a7 7 0 0 1 14 0" />
  </Svg>
);

export const LinkIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="M9.5 14.5 14.5 9.5" />
    <path d="M11 6.5 12.8 4.7a3.4 3.4 0 0 1 4.8 4.8L15.8 11" />
    <path d="M13 17.5l-1.8 1.8a3.4 3.4 0 0 1-4.8-4.8L8.2 13" />
  </Svg>
);

export const LeadIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <circle cx="9.5" cy="8" r="3.2" />
    <path d="M3.5 19a6 6 0 0 1 10.2-3.4" />
    <path d="m15 18 2 2 4-4" />
  </Svg>
);

export const MegaphoneIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="M4 10v4h3l8 4V6L7 10H4Z" />
    <path d="M18 9.5a3.5 3.5 0 0 1 0 5" />
  </Svg>
);

export const ServiceIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="M6 20v-5M6 9V4M12 20v-8M12 4v4M18 20v-3M18 13V4" />
    <path d="M4 15h4M10 8h4M16 17h4" />
  </Svg>
);

export const ConfigIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="M4 7h10M18 7h2M4 17h4M12 17h8" />
    <circle cx="16" cy="7" r="2" />
    <circle cx="10" cy="17" r="2" />
  </Svg>
);

export const ArrowLeftIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="M19 12H5M11 6l-6 6 6 6" />
  </Svg>
);

export const SaveIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="M5 4h11l3 3v13H5Z" />
    <path d="M8 4v5h7V4M8 20v-6h8v6" />
  </Svg>
);

export const DotsIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="M12 6h.01M12 12h.01M12 18h.01" strokeWidth={2.6} />
  </Svg>
);

export const CheckIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="m5 12.5 4.5 4.5L19 7" />
  </Svg>
);

export const LockIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <rect x="5" y="10" width="14" height="10" rx="2" />
    <path d="M8.5 10V7.5a3.5 3.5 0 0 1 7 0V10" />
  </Svg>
);

export const TrashIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13M10 11v5M14 11v5" />
  </Svg>
);

export const ShareIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <circle cx="6" cy="12" r="2.5" />
    <circle cx="18" cy="6" r="2.5" />
    <circle cx="18" cy="18" r="2.5" />
    <path d="m8.2 10.8 7.6-3.6M8.2 13.2l7.6 3.6" />
  </Svg>
);

export const MailIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <rect x="3.5" y="5.5" width="17" height="13" rx="2" />
    <path d="m4 7 8 6 8-6" />
  </Svg>
);

export const RefreshIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="M20 11a8 8 0 1 0-.6 4" />
    <path d="M20 5v6h-6" />
  </Svg>
);

export const ColumnsIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <rect x="4" y="5" width="16" height="14" rx="2" />
    <path d="M10 5v14M16 5v14" />
  </Svg>
);

export const FilterLinesIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="M4 7h16M7 12h10M10 17h4" />
  </Svg>
);

export const StarIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="m12 4 2.4 5 5.6.6-4.1 3.8 1.1 5.6-5-2.8-5 2.8 1.1-5.6L4 9.6 9.6 9Z" />
  </Svg>
);
