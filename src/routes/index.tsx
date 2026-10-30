import { createFileRoute } from "@tanstack/react-router";
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


export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "LowCore Launcher — Launch Faster. Play Smoother." },
      {
        name: "description",
        content:
          "LowCore is an ultra-lightweight native Minecraft launcher: instant boot, pre-configured optimization mods, instance isolation, Modrinth integration and a clean 0/62 VirusTotal scan.",
      },
      { property: "og:title", content: "LowCore Launcher — Launch Faster. Play Smoother." },
      {
        property: "og:description",
        content:
          "A bloat-free, native Minecraft launcher built for pure performance, instance isolation, and ultra-low RAM usage.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

const DOWNLOAD_URL =
  "https://github.com/lowcorelauncher/LowCore-Launcher-WEBSITE-/releases/download/v1.0.0/LowCoreLauncherSetup.exe";
const DISCORD_URL = "https://discord.gg/PxF3vqqstC";
const GITHUB_URL = "https://github.com/lowcore/launcher";

const NAV_LINKS = [
  { label: "Features", href: "#features" },
  { label: "Mods", href: "#mods" },
  { label: "Customize", href: "#customize" },
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
    title: "Built-in Optimization Stack",
    body: "Pre-configured with Sodium, Lithium, and FerriteCore for maximum FPS.",
  },
  {
    icon: Layers,
    title: "Instance Isolation",
    body: "Keep separate mods, configs, and worlds without corrupting standard folders.",
  },
  {
    icon: UsersRound,
    title: "Seamless Accounts",
    body: "Switch between Microsoft accounts and offline profiles effortlessly.",
  },
  {
    icon: PackageSearch,
    title: "Modrinth Integration",
    body: "Search and download compatible mods directly inside the client.",
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
        LowCore
      </span>
      <span className="rounded-full bg-coral/15 px-2 py-0.5 font-display text-[10px] font-bold uppercase tracking-widest text-coral ring-1 ring-coral/30">
        Beta
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
      <div className="relative mx-auto max-w-6xl px-4 pb-20 pt-16 sm:px-6 sm:pt-24">
        <div className="mx-auto max-w-3xl text-center">
          <div className="mb-6 flex flex-wrap items-center justify-center gap-2">
            <span className="chip">Windows 64-bit Native</span>
            <span className="chip chip-mint">
              <ShieldCheck className="h-3.5 w-3.5" />
              VirusTotal 0/62 Clean
            </span>
            <span className="chip">~90MB Footprint</span>
          </div>

          <h1 className="font-display text-5xl font-bold tracking-tight text-foreground sm:text-6xl md:text-7xl">
            Launch Faster.
            <br />
            <span className="bg-gradient-to-r from-coral via-foreground to-foreground bg-clip-text text-transparent">
              Play Smoother.
            </span>
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-muted-foreground">
            A bloat-free, native Minecraft launcher built for pure performance, instance
            isolation, and ultra-low RAM usage. Lightning-fast, easy to use, and it handles
            everything in one place.
          </p>

          <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <a
              href={DOWNLOAD_URL}
              download="LowCoreLauncherSetup.exe"
              className="btn-glow btn-glow-hover group inline-flex items-center gap-3 rounded-xl bg-primary px-7 py-4 text-base font-semibold text-primary-foreground transition-all hover:scale-[1.02] active:scale-[0.98]"
            >
              <DownloadIcon className="h-5 w-5 transition-transform group-hover:translate-y-0.5" />
              <span className="flex flex-col items-start leading-tight">
                <span>Download for Windows (.exe)</span>
                <span className="text-xs font-normal opacity-80">v1.0.0-Beta • Instant Setup</span>
              </span>
            </a>
            <a
              href={DISCORD_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="glass-card card-lift inline-flex items-center gap-2.5 rounded-xl px-6 py-4 text-base font-semibold text-foreground"
            >
              <MessageSquare className="h-5 w-5 text-mint" />
              Join Discord Community
            </a>
          </div>
        </div>

        <div className="relative mx-auto mt-16 max-w-2xl sm:mt-20">
          <div
            className="animate-pulse-glow absolute -inset-8 rounded-[2rem] bg-coral/10 blur-3xl"
            aria-hidden="true"
          />
          <div className="animate-float-soft flex flex-col items-center">
            <div className="glass-card overflow-hidden rounded-t-2xl rounded-b-md shadow-2xl ring-1 ring-border">
              <img
                src="/launcher-hero.png"
                alt="Real LowCore Launcher window: Play tab with isolated instance, account switching, memory allocation and PLAY button"
                width={895}
                height={796}
                className="block w-full"
              />
            </div>
            <div
              className="h-4 w-[106%] rounded-b-2xl bg-gradient-to-b from-secondary to-muted shadow-xl ring-1 ring-border"
              aria-hidden="true"
            />
          </div>
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
              alt="LowCore Launcher Settings tab with client theme, window resolution, logging and custom folder options"
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

function Performance() {
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
      body: "Grab LowCoreLauncherSetup.exe from the release page — about 90MB in total.",
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

        <div className="mt-12 text-center">
          <a
            href={DOWNLOAD_URL}
            download="LowCoreLauncherSetup.exe"
            className="btn-glow btn-glow-hover group inline-flex items-center gap-3 rounded-xl bg-primary px-7 py-4 text-base font-semibold text-primary-foreground transition-all hover:scale-[1.02] active:scale-[0.98]"
          >
            <DownloadIcon className="h-5 w-5 transition-transform group-hover:translate-y-0.5" />
            <span className="flex flex-col items-start leading-tight">
              <span>Download LowCoreLauncherSetup.exe</span>
              <span className="text-xs font-normal opacity-80">v1.0.0-Beta • Windows 64-bit</span>
            </span>
          </a>
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
        <Features />
        <ModsSection />
        <Customization />
        <Performance />
        <Security />
        <Download />
      </main>
      <Footer />
    </div>
  );
}
