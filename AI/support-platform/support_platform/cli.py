"""Command-line interface and terminal dashboard.

Usage::

    python -m support_platform.cli triage "I was charged twice"
    python -m support_platform.cli thread          # multi-turn context demo
    python -m support_platform.cli demo            # runs the bad-input suite
    python -m support_platform.cli dashboard
    python -m support_platform.cli metrics
"""

from __future__ import annotations

import argparse
import json
import sys

from .pipeline import SupportPipeline, TicketResult
from .storage import Database

# ANSI colours (dashboard is meant for a dark terminal)
DIM, RED, YELLOW, GREEN, CYAN, BOLD, RESET = (
    "\033[2m", "\033[31m", "\033[33m", "\033[32m", "\033[36m", "\033[1m", "\033[0m",
)

PRIORITY_COLOUR = {"high": RED, "medium": YELLOW, "low": GREEN}


def _print_result(result: TicketResult) -> None:
    a = result.analysis
    d = result.decision
    status = f"{GREEN}OK{RESET}" if result.ok else f"{RED}FALLBACK{RESET}"
    print(f"\n{BOLD}Ticket {result.ticket_id}{RESET}  [{status}]")
    print(f"{DIM}request={result.request_id} attempts={result.attempts} "
          f"latency={result.latency_ms}ms{RESET}")

    if result.error:
        print(f"{RED}! {result.error}{RESET}")
    if result.truncated:
        print(f"{YELLOW}! message was truncated before analysis{RESET}")

    if result.tools:
        print(f"\n  {BOLD}tools used{RESET}")
        for t in result.tools:
            mark = f"{GREEN}ok{RESET}" if t.ok else f"{RED}fail{RESET}"
            detail = t.result_summary if t.ok else t.error
            args = ", ".join(f"{k}={v}" for k, v in t.arguments.items())
            print(f"    {DIM}·{RESET} {t.name}({args}) [{mark}] {DIM}{detail[:90]}{RESET}")

    if a:
        colour = PRIORITY_COLOUR.get(a.priority.value, "")
        print(f"  category        : {a.category.value}")
        print(f"  priority        : {colour}{a.priority.value}{RESET}")
        print(f"  sentiment       : {a.sentiment.value}")
        print(f"  issue           : {a.issue}")
        print(f"  suggested_action: {a.suggested_action}")
        print(f"  requires_human  : {'yes' if a.requires_human else 'no'}")
        print(f"  confidence      : {a.confidence:.2f}")
        if a.entities:
            ents = ", ".join(f"{e.type}={e.value}" for e in a.entities)
            print(f"  entities        : {ents}")
        print(f"  draft_response  : {a.draft_response[:300]}")

    if d:
        print(f"\n  {BOLD}business rules{RESET}")
        print(f"  action          : {CYAN}{d.action.value}{RESET}  (SLA {d.sla_hours}h)")
        if d.overrode_model:
            was = []
            if d.model_priority and d.model_priority != d.priority:
                was.append(f"priority {d.model_priority.value} -> {d.priority.value}")
            if d.model_requires_human is not None and d.model_requires_human != d.requires_human:
                was.append(
                    f"requires_human {str(d.model_requires_human).lower()} -> "
                    f"{str(d.requires_human).lower()}"
                )
            print(f"  {YELLOW}overrode model  : {'; '.join(was)}{RESET}")
        if d.fired_rules:
            for name, reason in zip(d.fired_rules, d.reasons):
                print(f"    {DIM}·{RESET} {name}: {DIM}{reason}{RESET}")
        else:
            print(f"    {DIM}(no rules fired){RESET}")


def cmd_triage(args: argparse.Namespace) -> int:
    pipeline = SupportPipeline()
    result = pipeline.process(args.message, ticket_id=args.ticket, customer=args.customer)
    if args.json:
        print(json.dumps(result.as_dict(), indent=2))
    else:
        _print_result(result)
        print(f"\n{DIM}metrics: {pipeline.summary()}{RESET}")
    return 0 if result.ok else 1


def cmd_thread(args: argparse.Namespace) -> int:
    """Demonstrates that follow-up messages resolve against earlier context."""
    pipeline = SupportPipeline()
    turns = args.messages or [
        "My payment failed.",
        "It happened three times.",
        "Here's the error code: ERR_CARD_DECLINED_51",
    ]

    ticket_id = None
    for i, text in enumerate(turns, 1):
        print(f"\n{CYAN}--- turn {i}: {text}{RESET}")
        result = pipeline.process(text, ticket_id=ticket_id, customer=args.customer)
        ticket_id = result.ticket_id
        _print_result(result)

    print(f"\n{BOLD}Stored conversation{RESET}")
    for msg in pipeline.conversation(ticket_id or ""):
        print(f"  {DIM}{msg['role']:<12}{RESET} {msg['content'][:100]}")
    print(f"\n{DIM}metrics: {pipeline.summary()}{RESET}")
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    """Runs the bad-input suite so failure handling is visible end to end."""
    pipeline = SupportPipeline()
    cases: list[tuple[str, object]] = [
        ("empty", ""),
        ("whitespace only", "   \n\t  "),
        ("too short", "hi"),
        ("wrong type", {"body": "not a string"}),
        ("binary noise", b"\x00\x01\x02\x03\xff\xfe"),
        ("unsupported language", "Hola, me cobraron dos veces la suscripcion, por favor reembolso."),
        ("extremely long", "My app keeps crashing. " + ("stack trace line. " * 3000)),
    ]
    for label, payload in cases:
        print(f"\n{CYAN}=== {label} ==={RESET}")
        result = pipeline.process(payload, customer="demo")
        _print_result(result)
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    db = Database()
    rows = db.dashboard_rows(limit=args.limit)
    counts = db.queue_counts()

    print(f"\n{BOLD}SUPPORT QUEUE{RESET}")
    print(f"{DIM}{'-' * 108}{RESET}")
    if counts:
        chips = "  ".join(
            f"{PRIORITY_COLOUR.get(p, '')}{p}: {n}{RESET}" for p, n in sorted(counts.items())
        )
        print(f"  {chips}\n")

    header = f"{'TICKET':<14}{'PRIORITY':<10}{'CATEGORY':<16}{'SENT':<10}{'HUMAN':<7}{'ISSUE'}"
    print(f"{BOLD}{header}{RESET}")
    print(f"{DIM}{'-' * 108}{RESET}")

    for r in rows:
        priority = r["priority"] or "-"
        colour = PRIORITY_COLOUR.get(priority, "")
        human = "yes" if r["requires_human"] else "no"
        issue = (r["issue"] or "")[:44]
        print(
            f"{r['id']:<14}{colour}{priority:<10}{RESET}{(r['category'] or '-'):<16}"
            f"{(r['sentiment'] or '-'):<10}{human:<7}{issue}"
        )

    if not rows:
        print(f"{DIM}  (no tickets yet -- run 'triage' or 'demo' first){RESET}")

    print()
    return cmd_metrics(args)


def cmd_metrics(args: argparse.Namespace) -> int:
    db = Database()
    m = db.metrics_summary()
    print(f"{BOLD}LLM METRICS (all time){RESET}")
    print(f"{DIM}{'-' * 108}{RESET}")
    print(
        f"  calls={m['calls']}  success_rate={m['success_rate']}  retries={m['retries']}\n"
        f"  avg_latency={m['avg_latency_ms']}ms  max_latency={round(m['max_latency_ms'], 1)}ms\n"
        f"  tokens in={m['prompt_tokens']} out={m['completion_tokens']} total={m['total_tokens']}\n"
        f"  modelled cost=${m['cost_usd']:.6f}"
    )
    print()
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from .webapp import serve

    serve(host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="support_platform.cli", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    t = sub.add_parser("triage", help="analyse a single message")
    t.add_argument("message")
    t.add_argument("--ticket", default=None, help="append to an existing ticket")
    t.add_argument("--customer", default="unknown")
    t.add_argument("--json", action="store_true")
    t.set_defaults(func=cmd_triage)

    th = sub.add_parser("thread", help="multi-turn conversation demo")
    th.add_argument("messages", nargs="*")
    th.add_argument("--customer", default="demo")
    th.set_defaults(func=cmd_thread)

    d = sub.add_parser("demo", help="bad-input handling demo")
    d.set_defaults(func=cmd_demo)

    db = sub.add_parser("dashboard", help="show the ticket queue")
    db.add_argument("--limit", type=int, default=25)
    db.set_defaults(func=cmd_dashboard)

    mt = sub.add_parser("metrics", help="show cost/latency metrics")
    mt.set_defaults(func=cmd_metrics)

    sv = sub.add_parser("serve", help="run the web dashboard")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)
    sv.set_defaults(func=cmd_serve)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\ninterrupted")
        return 130


if __name__ == "__main__":
    sys.exit(main())
