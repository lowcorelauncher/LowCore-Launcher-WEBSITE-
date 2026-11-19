import * as React from "react";
import { createFileRoute } from "@tanstack/react-router";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { LinuxIcon } from "@/components/linux-icon";
import {
  Zap,
  Gauge,
  Layers,
  UsersRound,
  PackageSearch,
  ShieldCheck,
  Download as DownloadIcon,
  ArrowRight,
  MessageSquare,
  Github,
  Search,
  CloudDownload,
  Puzzle,
  Palette,
  AppWindow,
  FolderOpen,
  BadgeDollarSign,
  Sparkles,
  EyeOff,
  Infinity as InfinityIcon,
} from "lucide-react";


export const SITE_PRODUCT_NAME = "LowCore Client";

export const PERFORMANCE_STATS = [
  { value: "100 MB", label: "Client footprint", detail: "A compact install" },
  { value: "~0.5 MB", label: "RAM at idle", detail: "When the client is idle" },
  { value: "15–20 MB", label: "RAM in use", detail: "While the client is running" },
] as const;

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: `${SITE_PRODUCT_NAME} — Launch Faster. Play Smoother.` },
      {
        name: "description",
        content:
          "LowCore Client is a lightweight native Minecraft client with instant boot, automatic full optimization, isolated instances, Modrinth integration, and a clean 0/62 VirusTotal scan.",
      },
      { property: "og:title", content: `${SITE_PRODUCT_NAME} — Launch Faster. Play Smoother.` },
      {
        property: "og:description",
        content:
          "A lightweight native Minecraft client built for quick launches, easy mod management, and low memory use.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

const DOWNLOAD_URL =
  "https://github.com/lowcorelauncher/LowCore-Launcher-WEBSITE-/releases/latest/download/LowCoreClientSetup.exe";
const LINUX_URL =
  "https://github.com/lowcorelauncher/LowCore-Launcher-WEBSITE-/releases/latest/download/LowCoreClient-Linux.zip";
const DISCORD_URL = "https://discord.gg/PxF3vqqstC";
const GITHUB_URL = "https://github.com/lowcorelauncher/LowCore-Launcher-WEBSITE-";

type VisitorOs = "unknown" | "windows" | "linux" | "other";

function startDirectDownload(url: string, filename: string) {
  const downloadLink = document.createElement("a");
  downloadLink.href = url;
  downloadLink.download = filename;
  downloadLink.rel = "noopener noreferrer";
  document.body.appendChild(downloadLink);
  downloadLink.click();
  downloadLink.remove();
}

function useVisitorOs(): VisitorOs {
  const [os, setOs] = React.useState<VisitorOs>("unknown");
  React.useEffect(() => {
    const ua = window.navigator.userAgent;
    if (/Android|iPhone|iPad/i.test(ua)) setOs("other");
    else if (/Linux|X11/i.test(ua)) setOs("linux");
    else if (/Win/i.test(ua)) setOs("windows");
    else setOs("other");
  }, []);
  return os;
}

const primaryButtonClass =
  "btn-glow btn-glow-hover group inline-flex items-center gap-3 rounded-xl bg-primary px-7 py-4 text-base font-semibold text-primary-foreground transition-all hover:scale-[1.02] active:scale-[0.98]";
const secondaryButtonClass =
  "glass-card card-lift inline-flex items-center gap-3 rounded-xl px-6 py-4 text-base font-semibold text-foreground transition-all hover:scale-[1.02] active:scale-[0.98]";

function PlatformDownloadButtons() {
  const os = useVisitorOs();
  const linuxPrimary = os === "linux";
  const [discordInvitationOpen, setDiscordInvitationOpen] = React.useState(false);

  const windowsButton = (
    <a
      href={DOWNLOAD_URL}
      download="LowCoreClientSetup.exe"
      onClick={(event) => {
        event.preventDefault();
        startDirectDownload(DOWNLOAD_URL, "LowCoreClientSetup.exe");
        setDiscordInvitationOpen(true);
      }}
      className={cn(
        "order-2 sm:order-none",
        linuxPrimary ? secondaryButtonClass : primaryButtonClass,
      )}
    >
      <DownloadIcon className="h-5 w-5 transition-transform group-hover:translate-y-0.5" />
      <span className="flex flex-col items-start leading-tight">
        <span>Download for Windows (.exe)</span>
        <span className="text-xs font-normal opacity-80">v1.3 • Windows 64-bit</span>
      </span>
    </a>
  );

  const linuxButton = (
    <LinuxDownloadButton
      onDownloadInstructionsClosed={() => {
        window.setTimeout(() => setDiscordInvitationOpen(true), 200);
      }}
      className={cn(
        "order-1 sm:order-none",
        linuxPrimary ? primaryButtonClass : secondaryButtonClass,
      )}
    />
  );

  return (
    <>
      <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
        {linuxPrimary ? (
          <React.Fragment key="linux-first">
            {linuxButton}
            {windowsButton}
          </React.Fragment>
        ) : (
          <React.Fragment key="windows-first">
            {windowsButton}
            {linuxButton}
          </React.Fragment>
        )}
      </div>
      <Dialog open={discordInvitationOpen} onOpenChange={setDiscordInvitationOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="font-display">
              Join the Discord for notifications about new updates?
            </DialogTitle>
            <DialogDescription>
              Get LowCore release announcements and updates in the community server.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">Maybe later</Button>
            </DialogClose>
            <Button asChild className="bg-primary text-primary-foreground hover:bg-primary/90">
              <a href={DISCORD_URL} target="_blank" rel="noopener noreferrer">
                <MessageSquare className="h-4 w-4" />
                Join Discord
              </a>
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function LinuxDownloadButton({
  className,
  onDownloadInstructionsClosed,
}: {
  className: string;
  onDownloadInstructionsClosed: () => void;
}) {
  const [open, setOpen] = React.useState(false);
  return (
    <>
      <a
        href={LINUX_URL}
        download="LowCoreClient-Linux.zip"
        className={className}
        onClick={(event) => {
          event.preventDefault();
          startDirectDownload(LINUX_URL, "LowCoreClient-Linux.zip");
          setOpen(true);
        }}
      >
        <LinuxIcon className="h-5 w-5" />
        <span className="flex flex-col items-start leading-tight">
          <span>Download for Linux</span>
          <span className="text-xs font-normal opacity-80">v1.3 (x64 .zip)</span>
        </span>
      </a>
      <Dialog
        open={open}
        onOpenChange={(nextOpen) => {
          setOpen(nextOpen);
          if (!nextOpen) onDownloadInstructionsClosed();
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="font-display">Linux installation instructions</DialogTitle>
            <DialogDescription>
              Your download has started. After it finishes, open a terminal in the extracted folder and run:
            </DialogDescription>
          </DialogHeader>
          <pre className="overflow-x-auto rounded-lg bg-card px-4 py-3 font-mono text-xs leading-relaxed text-foreground ring-1 ring-border">
            bash install.sh
          </pre>
          <div className="space-y-3 text-sm text-muted-foreground">
            <h3 className="font-semibold text-foreground">Troubleshooting</h3>
            <p>
              If it asks for <code className="rounded bg-card px-1.5 py-0.5 font-mono text-xs text-foreground">libxcb-cursor0</code> or fails with an xcb error, run:
            </p>
            <pre className="overflow-x-auto rounded-lg bg-card px-4 py-3 font-mono text-xs leading-relaxed text-foreground ring-1 ring-border">
              sudo apt update &amp;&amp; sudo apt install -y libxcb-cursor0
            </pre>
            <p>
              On Ubuntu/GNOME, if the desktop shortcut does not open, right-click the desktop icon and choose <strong className="text-foreground">Allow Launching</strong>.
            </p>
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button className="bg-primary text-primary-foreground hover:bg-primary/90">
                Got it
              </Button>
            </DialogClose>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

const NAV_LINKS = [
  { label: "Features", href: "#features" },
  { label: "Mods", href: "#mods" },
  { label: "Customize", href: "#customize" },
  { label: "Performance", href: "#performance" },
  { label: "Free", href: "#free" },
  { label: "Security", href: "#security" },
  { label: "Discord", href: DISCORD_URL, external: true },
];

const FEATURES = [
  {
    icon: Zap,
    title: "Instant Boot Time",
    body: "Zero Chromium or Electron bloat. Starts instantly with native speed.",
  },
  {
    icon: Gauge,
    title: "Automatic Full Optimization",
    body: "Automatically equips Sodium, Lithium, FerriteCore, and performance mods with zero duplicates.",
  },
  {
    icon: Layers,
    title: "Instance Isolation",
    body: "Keep separate mods, configs, and worlds — or import from Lunar, Prism, Modrinth & more.",
  },
  {
    icon: UsersRound,
    title: "Seamless Accounts",
    body: "Switch between Microsoft accounts and offline profiles effortlessly.",
  },
  {
    icon: PackageSearch,
    title: "Modrinth Integration",
    body: "Search mods with full hover previews, Read More details, and one-click installs.",
  },
  {
    icon: ShieldCheck,
    title: "Verified Clean",
    body: "Built with native toolchains, 0/62 clean scan on VirusTotal, zero malware flags.",
  },
];


function Logo() {
  return (
    <a href="#top" className="flex items-center gap-2.5">
      <img src="/lowcore-logo.png" alt="LowCore logo" className="h-8 w-8" />
      <span className="font-display text-lg font-bold tracking-tight text-foreground">
        LowCore Client
      </span>
    </a>
  );
}

function Navbar() {
  return (
    <header className="glass-nav fixed inset-x-0 top-0 z-50">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Logo />
        <nav className="hidden items-center gap-7 md:flex">
          {NAV_LINKS.map((link) => (
            <a
              key={link.label}
              href={link.href}
              {...("external" in link ? { target: "_blank", rel: "noopener noreferrer" } : {})}
              className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              {link.label}
            </a>
          ))}
        </nav>
        <a
          href="#download"
          className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition-all hover:opacity-90"
        >
          Download Now
        </a>
      </div>
    </header>
  );
}

function Hero() {
  return (
    <section id="top" className="hero-aurora relative overflow-hidden pt-16">
      <div className="grid-fade absolute inset-0" aria-hidden="true" />
      <div className="relative mx-auto max-w-6xl px-4 pb-16 pt-12 sm:px-6 sm:pb-20 sm:pt-20">
        <div className="grid items-center gap-12 lg:grid-cols-[minmax(0,0.88fr)_minmax(0,1.12fr)] lg:gap-10">
          <div className="max-w-xl">
            <div className="mb-6 flex flex-wrap gap-2">
              <span className="chip">Native Minecraft client</span>
              <span className="chip chip-mint">
                <ShieldCheck className="h-3.5 w-3.5" />
                VirusTotal 0/62
              </span>
              <span className="chip">100 MB footprint</span>
            </div>
            <h1 className="font-display text-5xl font-bold leading-[1.04] text-foreground sm:text-6xl">
              LowCore
              <br />
              <span className="text-coral">Client.</span>
            </h1>
            <p className="mt-5 font-display text-xl font-semibold text-foreground sm:text-2xl">
              Launch Faster. Play Smoother.
            </p>
            <p className="mt-4 max-w-lg text-base leading-relaxed text-muted-foreground sm:text-lg">
              A lightweight, easy-to-use Minecraft client that keeps instances, mods, accounts,
              and settings together — so you can get in and play without the busywork.
            </p>
            <div className="mt-8">
              <PlatformDownloadButtons />
            </div>
            <div className="mt-4 flex flex-wrap gap-3">
              <a
                href={DISCORD_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="glass-card card-lift inline-flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold text-foreground"
              >
                <MessageSquare className="h-4 w-4 text-mint" />
                Join Discord
              </a>
              <a
                href={GITHUB_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="glass-card card-lift inline-flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold text-foreground"
              >
                <Github className="h-4 w-4" />
                GitHub
              </a>
            </div>
          </div>

          <div className="relative mx-auto w-full max-w-2xl lg:max-w-none">
            <div className="overflow-hidden rounded-lg border border-border bg-card shadow-2xl">
              <img
                src="/launcher-hero.png"
                alt="LowCore Client Play screen showing its active Minecraft instance and launch controls"
                width={922}
                height={872}
                className="block w-full"
              />
            </div>
            <div className="mt-3 flex items-center justify-between border-t border-border pt-3 text-xs text-muted-foreground">
              <span>Everything you need, in one place.</span>
              <span className="font-semibold text-coral">LOWCORE CLIENT / v1.3</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function PerformanceSnapshot() {
  return (
    <section
      id="performance"
      className="scroll-mt-20 border-y border-border bg-card/30 py-14 sm:py-20"
      aria-labelledby="performance-title"
    >
      <div className="mx-auto grid max-w-6xl gap-9 px-4 sm:px-6 lg:grid-cols-[0.8fr_1.2fr] lg:items-center lg:gap-14">
        <div className="max-w-md">
          <p className="font-display text-sm font-semibold uppercase tracking-widest text-coral">
            Performance snapshot
          </p>
          <h2 id="performance-title" className="mt-3 font-display text-3xl font-bold text-foreground sm:text-4xl">
            Lightweight by design.
          </h2>
          <p className="mt-4 leading-relaxed text-muted-foreground">
            LowCore Client stays out of the way when you are not using it, and keeps its footprint
            small while you play.
          </p>
        </div>
        <div className="grid divide-y divide-border sm:grid-cols-3 sm:divide-x sm:divide-y-0">
          {PERFORMANCE_STATS.map((stat) => (
            <div key={stat.label} className="py-5 sm:px-5 sm:py-2 lg:px-6">
              <p className="text-xs font-semibold uppercase text-muted-foreground">{stat.label}</p>
              <p className="mt-2 font-display text-4xl font-bold text-coral sm:text-3xl lg:text-4xl">
                {stat.value}
              </p>
              <p className="mt-2 text-sm text-muted-foreground">{stat.detail}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Features() {
  return (
    <section id="features" className="relative mx-auto max-w-6xl scroll-mt-20 px-4 py-20 sm:px-6 sm:py-28">
      <div className="max-w-2xl">
        <p className="font-display text-sm font-semibold uppercase tracking-widest text-coral">
          Features
        </p>
        <h2 className="mt-3 font-display text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
          Everything you need. Nothing you don't.
        </h2>
        <p className="mt-4 text-muted-foreground">
          Built from scratch for speed — no wrappers, no webviews, no wasted megabytes.
        </p>
      </div>

      <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map((feature) => (
          <div
            key={feature.title}
            className="glass-card card-lift group rounded-2xl p-6"
          >
            <div className="inline-flex rounded-xl bg-coral/10 p-3 text-coral ring-1 ring-coral/20 transition-colors group-hover:bg-coral/15">
              <feature.icon className="h-6 w-6" />
            </div>
            <h3 className="mt-5 font-display text-lg font-semibold text-foreground">
              {feature.title}
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{feature.body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function ModsSection() {
  const points = [
    {
      icon: Search,
      title: "One search box for everything",
      body: "Find mods, resource packs, and shaders from a single, clean search bar.",
    },
    {
      icon: Puzzle,
      title: "Dependency resolution built in",
      body: "Pick a mod and LowCore resolves every dependency for your instance automatically.",
    },
    {
      icon: CloudDownload,
      title: "Install with one click",
      body: "Download straight to the selected instance — no manual file juggling.",
    },
  ];

  return (
    <section id="mods" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-20 sm:px-6 sm:py-28">
      <div className="grid items-center gap-12 lg:grid-cols-2">
        <div className="relative order-2 lg:order-1">
          <div className="glass-card card-lift overflow-hidden rounded-2xl shadow-2xl">
            <img
              src="/launcher-mods.png"
              alt="LowCore Content Browser searching mods with one-click download to a selected instance"
              width={896}
              height={797}
              className="block w-full"
            />
          </div>
        </div>
        <div className="order-1 lg:order-2">
          <p className="font-display text-sm font-semibold uppercase tracking-widest text-coral">
            Mod Management
          </p>
          <h2 className="mt-3 font-display text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
            Easy mod management, zero headaches.
          </h2>
          <p className="mt-4 leading-relaxed text-muted-foreground">
            Managing mods is lightning-fast and easy: search, click, done. LowCore resolves
            every dependency for you and installs straight into your instance — everything
            handled in one place, without touching a single folder.
          </p>
          <div className="mt-8 space-y-5">
            {points.map((point) => (
              <div key={point.title} className="flex items-start gap-4">
                <div className="inline-flex shrink-0 rounded-xl bg-coral/10 p-2.5 text-coral ring-1 ring-coral/20">
                  <point.icon className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="font-display font-semibold text-foreground">{point.title}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                    {point.body}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function Customization() {
  const points = [
    {
      icon: Palette,
      title: "Make it yours",
      body: "Client themes built right in — switch the whole launcher look, like OLED Black, from a single dropdown.",
    },
    {
      icon: AppWindow,
      title: "Tune your game window",
      body: "Set your own width and height, or start straight into fullscreen. It remembers it for next time.",
    },
    {
      icon: FolderOpen,
      title: "Your folders, your rules",
      body: "Choose exactly where your instances, libraries, auto Java, and downloads live — everything stays where you put it.",
    },
  ];

  return (
    <section id="customize" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-20 sm:px-6 sm:py-28">
      <div className="grid items-center gap-12 lg:grid-cols-2">
        <div>
          <p className="font-display text-sm font-semibold uppercase tracking-widest text-coral">
            Easy to Use &amp; Customizable
          </p>
          <h2 className="mt-3 font-display text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
            Simple on the surface. Deep where it counts.
          </h2>
          <p className="mt-4 leading-relaxed text-muted-foreground">
            LowCore is easy to use out of the box and customizable where it matters: themes,
            resolutions, folders, accounts and instances — all handled in one clean place,
            with no config files or tech skills required.
          </p>
          <div className="mt-8 space-y-5">
            {points.map((point) => (
              <div key={point.title} className="flex items-start gap-4">
                <div className="inline-flex shrink-0 rounded-xl bg-coral/10 p-2.5 text-coral ring-1 ring-coral/20">
                  <point.icon className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="font-display font-semibold text-foreground">{point.title}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                    {point.body}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="relative">
          <div className="glass-card card-lift overflow-hidden rounded-2xl shadow-2xl">
            <img
              src="/launcher-settings.png"
              alt="LowCore Client settings screen with theme, window resolution, logging, and custom folder options"
              width={893}
              height={796}
              className="block w-full"
            />
          </div>
        </div>
      </div>
    </section>
  );
}

function FreeSection() {
  return (
    <section
      id="free"
      className="relative scroll-mt-20 border-y border-border bg-card/40 py-20 sm:py-28"
    >
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <p className="font-display text-sm font-semibold uppercase tracking-widest text-mint">
            100% Free
          </p>
          <h2 className="mt-3 font-display text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
            The entire client is fully free.
          </h2>
          <p className="mt-4 leading-relaxed text-muted-foreground">
            No price tag. No premium tiers. No ads, no locked features, no catch. Every
            instance, every mod, every setting — everything in LowCore is completely free,
            and it always will be. Just download it and play.
          </p>
        </div>

        <div className="mt-12 grid grid-cols-2 gap-4 md:grid-cols-4">
          {[
            { icon: BadgeDollarSign, value: "$0", label: "Cost, forever" },
            { icon: Sparkles, value: "All", label: "Features unlocked" },
            { icon: EyeOff, value: "0", label: "Ads or trackers" },
            { icon: InfinityIcon, value: "Forever", label: "Free updates" },
          ].map((stat) => (
            <div key={stat.label} className="glass-card card-lift rounded-2xl p-5">
              <stat.icon className="h-5 w-5 text-mint" />
              <div className="mt-4 font-display text-2xl font-bold text-foreground sm:text-3xl">
                {stat.value}
              </div>
              <div className="mt-1 text-sm text-muted-foreground">{stat.label}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Security() {
  return (
    <section id="security" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-20 sm:px-6 sm:py-28">
      <div className="glass-card card-lift relative overflow-hidden rounded-3xl p-8 sm:p-12">
        <div
          className="absolute -right-24 -top-24 h-64 w-64 rounded-full bg-mint/10 blur-3xl"
          aria-hidden="true"
        />
        <div className="relative flex flex-col items-start gap-8 sm:flex-row sm:items-center">
          <div className="inline-flex rounded-2xl bg-mint/10 p-4 text-mint ring-1 ring-mint/25">
            <ShieldCheck className="h-10 w-10" />
          </div>
          <div className="flex-1">
            <p className="font-display text-sm font-semibold uppercase tracking-widest text-mint">
              Security
            </p>
            <h2 className="mt-3 font-display text-3xl font-bold tracking-tight text-foreground">
              Verified clean. 0/62.
            </h2>
            <p className="mt-4 max-w-xl leading-relaxed text-muted-foreground">
              LowCore is compiled with native toolchains and ships a fully clean
              VirusTotal report — zero malware flags across all 62 engines. Your worlds,
              your accounts, your machine: untouched.
            </p>
          </div>
          <a
            href="#download"
            className="group inline-flex items-center gap-2 whitespace-nowrap rounded-xl bg-secondary px-6 py-3 text-sm font-semibold text-secondary-foreground ring-1 ring-border transition-colors hover:bg-accent"
          >
            Get the installer
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
          </a>
        </div>
      </div>
    </section>
  );
}

function Download() {
  const steps = [
    {
      title: "Download",
      body: "Grab the installer for your platform — LowCoreClientSetup.exe v1.3 on Windows or the Linux .zip.",
    },
    {
      title: "Run the installer wizard",
      body: "A few clicks and you're done. No administrator rights needed.",
    },
    {
      title: "Launch & play",
      body: "Open it from your desktop shortcut and jump straight into your worlds.",
    },
  ];

  return (
    <section
      id="download"
      className="hero-aurora relative scroll-mt-20 border-t border-border py-20 sm:py-28"
    >
      <div className="grid-fade absolute inset-0" aria-hidden="true" />
      <div className="relative mx-auto max-w-6xl px-4 sm:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <p className="font-display text-sm font-semibold uppercase tracking-widest text-coral">
            Download
          </p>
          <h2 className="mt-3 font-display text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
            Ready in under a minute.
          </h2>
        </div>

        <div className="mt-12 grid gap-5 md:grid-cols-3">
          {steps.map((step, index) => (
            <div key={step.title} className="glass-card card-lift relative rounded-2xl p-6">
              <div className="font-display text-5xl font-bold text-coral/25">
                {String(index + 1).padStart(2, "0")}
              </div>
              <h3 className="mt-3 font-display text-lg font-semibold text-foreground">
                {step.title}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{step.body}</p>
            </div>
          ))}
        </div>

        <div className="mt-12 flex flex-col items-center">
          <PlatformDownloadButtons />
        </div>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t border-border py-10">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-6 px-4 sm:flex-row sm:px-6">
        <div className="flex flex-col items-center gap-3 sm:items-start">
          <Logo />
          <p className="text-center text-xs text-muted-foreground sm:text-left">
            Copyright © 2026 LowCore. Not an official Minecraft product, not approved by or
            associated with Mojang or Microsoft.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <a
            href={DISCORD_URL}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Discord"
            className="glass-card card-lift rounded-xl p-2.5 text-muted-foreground transition-colors hover:text-foreground"
          >
            <MessageSquare className="h-5 w-5" />
          </a>
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="GitHub"
            className="glass-card card-lift rounded-xl p-2.5 text-muted-foreground transition-colors hover:text-foreground"
          >
            <Github className="h-5 w-5" />
          </a>
        </div>
      </div>
    </footer>
  );
}

function Index() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        <Hero />
        <PerformanceSnapshot />
        <Features />
        <ModsSection />
        <Customization />
        <FreeSection />
        <Security />
        <Download />
      </main>
      <Footer />
    </div>
  );
}
