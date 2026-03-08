"""ContextNotes CLI — start, stop, and analyze reading + annotation sessions.

Usage:
    python cli.py start --url <article-url> [--title <title>] [--interval 3.0]
    python cli.py analyze <session-id>
    python cli.py analyze-file <trace.json>
    python cli.py list
    python cli.py export <session-id> [-o trace.json]
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from capture.session_coordinator import SessionCoordinator
from analysis.thought_progression import ThoughtProgressionAnalyzer
from trace.store import TraceStore


def cmd_start(args):
    """Start a capture session."""
    coordinator = SessionCoordinator(
        article_url=args.url,
        article_title=args.title,
        notebook_name=args.notebook,
        capture_interval=args.interval,
        output_dir=args.output_dir,
    )

    # Graceful shutdown on Ctrl+C
    def handle_sigint(sig, frame):
        print("\nStopping session...")
        coordinator.stop()
        print(f"\nSession ID: {coordinator.session.id}")
        print("Run `python cli.py analyze <session-id>` for thought progression analysis.")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    coordinator.start(duration=args.duration)

    if args.duration:
        # Blocking wait for timed sessions
        import time
        try:
            time.sleep(args.duration)
        except KeyboardInterrupt:
            pass
        coordinator.stop()
        print(f"\nSession ID: {coordinator.session.id}")
    else:
        # Keep main thread alive for indefinite sessions
        print("Press Ctrl+C to stop the session.")
        signal.pause()


def cmd_analyze(args):
    """Run thought progression analysis on a completed session."""
    analyzer = ThoughtProgressionAnalyzer()
    store = TraceStore()

    print(f"Analyzing session {args.session_id}...")
    analytics = analyzer.analyze_session(args.session_id, store=store)

    print(f"\nThought Progression:")
    print(analytics.thought_progression or "(no narrative generated)")

    print(f"\nAnnotations: {len(analytics.annotation_timeline)}")
    for a in analytics.annotation_timeline:
        level = a.cognitive_level
        print(f"  [{level}] {a.motivation}: {a.text[:60]}...")

    if analytics.learning_indicators:
        li = analytics.learning_indicators
        print(f"\nLearning Indicators:")
        print(f"  Generative ratio: {li.generative_ratio:.0%}")
        print(f"  Concept coverage: {li.concept_coverage:.0%}")
        print(f"  Cross-references:  {li.cross_references}")
        print(f"  Total annotations: {li.total_annotations}")
        print(f"  Reading time:      {li.total_reading_minutes:.1f} min")


def cmd_analyze_file(args):
    """Analyze a trace from a JSON file (no Supabase needed)."""
    analyzer = ThoughtProgressionAnalyzer()

    print(f"Analyzing trace file: {args.path}")
    result = analyzer.analyze_trace_file(args.path)

    print(json.dumps(result, indent=2, default=str))


def cmd_list(args):
    """List recent sessions."""
    store = TraceStore()
    result = store.client.table("sessions").select("*").order("started_at", desc=True).limit(20).execute()

    if not result.data:
        print("No sessions found.")
        return

    print(f"{'ID':<38} {'Status':<10} {'Started':<22} {'Article'}")
    print("-" * 100)
    for s in result.data:
        sid = s["id"]
        status = s.get("status", "?")
        started = s.get("started_at", "?")[:19]
        url = s.get("article_url", "?")[:40]
        print(f"{sid:<38} {status:<10} {started:<22} {url}")


def cmd_export(args):
    """Export a full session trace as JSON."""
    store = TraceStore()
    trace = store.get_full_trace(args.session_id)

    output = args.output or f"trace-{args.session_id[:8]}.json"
    with open(output, "w") as f:
        json.dump(trace, f, indent=2, default=str)

    print(f"Exported to {output}")
    event_count = len(trace.get("events", []))
    gaze_count = len(trace.get("gaze_stream", []))
    capture_count = len(trace.get("screen_captures", []))
    print(f"  Events: {event_count}  |  Gaze samples: {gaze_count}  |  Screen captures: {capture_count}")


def main():
    parser = argparse.ArgumentParser(
        description="ContextNotes — multimodal reading-to-notes learning trace system"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # start
    p_start = subparsers.add_parser("start", help="Start a capture session")
    p_start.add_argument("--url", required=True, help="Article URL being read")
    p_start.add_argument("--title", help="Article title")
    p_start.add_argument("--notebook", help="GoodNotes notebook name")
    p_start.add_argument("--interval", type=float, default=3.0, help="Capture interval in seconds")
    p_start.add_argument("--duration", type=float, help="Max session duration in seconds")
    p_start.add_argument("--output-dir", help="Save screenshots to this directory")
    p_start.set_defaults(func=cmd_start)

    # analyze
    p_analyze = subparsers.add_parser("analyze", help="Analyze a completed session")
    p_analyze.add_argument("session_id", help="Session UUID")
    p_analyze.set_defaults(func=cmd_analyze)

    # analyze-file
    p_af = subparsers.add_parser("analyze-file", help="Analyze from a trace JSON file")
    p_af.add_argument("path", help="Path to trace JSON file")
    p_af.set_defaults(func=cmd_analyze_file)

    # list
    p_list = subparsers.add_parser("list", help="List recent sessions")
    p_list.set_defaults(func=cmd_list)

    # export
    p_export = subparsers.add_parser("export", help="Export session trace as JSON")
    p_export.add_argument("session_id", help="Session UUID")
    p_export.add_argument("-o", "--output", help="Output file path")
    p_export.set_defaults(func=cmd_export)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
