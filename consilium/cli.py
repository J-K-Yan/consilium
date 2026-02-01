#!/usr/bin/env python3
"""
Consilium CLI tool.

Commands:
    consilium balance [username]     Show credit balances
    consilium verify                 Verify ledger integrity
    consilium rebuild                Rebuild ledger from GitHub
    consilium show <entry_num>       Show a specific ledger entry
"""

import argparse
import os
import sys

from .ledger import Ledger
from .rebuild import rebuild_from_github, verify_ledger_against_github


def cmd_balance(args):
    """Show credit balances."""
    ledger = Ledger(args.ledger_dir)

    if not ledger.index_path.exists():
        print("No ledger found. Run 'consilium rebuild' first.")
        return 1

    balances = ledger.get_balances()

    if not balances:
        print("No credit balances recorded yet.")
        return 0

    if args.username:
        # Show specific user
        credit = balances.get(args.username, 0.0)
        print(f"@{args.username}: {credit:.1f} credit")
    else:
        # Show leaderboard
        sorted_balances = sorted(balances.items(), key=lambda x: x[1], reverse=True)

        print("=" * 40)
        print("Consilium Credit Leaderboard")
        print("=" * 40)
        print(f"{'Rank':<6} {'Contributor':<20} {'Credit':>10}")
        print("-" * 40)

        for i, (username, credit) in enumerate(sorted_balances[:args.limit], 1):
            print(f"{i:<6} @{username:<19} {credit:>10.1f}")

        print("-" * 40)
        print(f"Total entries: {ledger.get_entry_count()}")

    return 0


def cmd_verify(args):
    """Verify ledger integrity."""
    ledger = Ledger(args.ledger_dir)

    if not ledger.index_path.exists():
        print("No ledger found.")
        return 1

    print("Verifying local chain integrity...")
    is_valid, error = ledger.verify_chain()

    if is_valid:
        print("✓ Local chain is valid")
        print(f"  Entries: {ledger.get_entry_count()}")
        print(f"  Head hash: {ledger.get_head_hash()}")
    else:
        print(f"✗ Chain verification failed: {error}")
        return 1

    # Optionally verify against GitHub
    if args.github:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            print("\nSkipping GitHub verification (GITHUB_TOKEN not set)")
            return 0

        if not args.repo:
            print("\nSkipping GitHub verification (--repo not specified)")
            return 0

        owner, repo = args.repo.split("/")
        print(f"\nVerifying against GitHub ({args.repo})...")

        is_valid, discrepancies = verify_ledger_against_github(
            token=token,
            owner=owner,
            repo=repo,
            ledger_dir=args.ledger_dir,
        )

        if is_valid:
            print("✓ Ledger matches GitHub comments")
        else:
            print("✗ Discrepancies found:")
            for d in discrepancies:
                print(f"  - {d}")
            return 1

    return 0


def cmd_rebuild(args):
    """Rebuild ledger from GitHub."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN environment variable required")
        return 1

    if not args.repo:
        print("Error: --repo owner/repo required")
        return 1

    owner, repo = args.repo.split("/")

    print(f"Rebuilding ledger from {args.repo}...")

    result = rebuild_from_github(
        token=token,
        owner=owner,
        repo=repo,
        ledger_dir=args.ledger_dir,
        incremental=not args.full,
    )

    print(f"\nEntries found: {result.entries_found}")
    print(f"Entries added: {result.entries_added}")

    if result.warnings:
        print("\nWarnings:")
        for w in result.warnings:
            print(f"  ⚠ {w}")

    if result.errors:
        print("\nErrors:")
        for e in result.errors:
            print(f"  ✗ {e}")
        return 1

    if result.success:
        print("\n✓ Rebuild successful")
        return 0
    else:
        print("\n✗ Rebuild completed with errors")
        return 1


def cmd_show(args):
    """Show a specific ledger entry."""
    ledger = Ledger(args.ledger_dir)

    entry = ledger.get_entry(args.entry_num)
    if not entry:
        print(f"Entry {args.entry_num} not found")
        return 1

    if args.json:
        print(entry.to_json_payload())
    else:
        print(f"Entry #{args.entry_num}")
        print("=" * 40)
        print(f"PR:        #{entry.pr_number}")
        print(f"Outcome:   {entry.outcome}")
        print(f"Source:    {entry.source}")
        print(f"Timestamp: {entry.timestamp}")
        print(f"Hash:      {entry.hash}")
        print(f"Prev Hash: {entry.prev_hash}")
        if entry.comment_id:
            print(f"Comment:   {entry.comment_id}")
        print("\nDistribution:")
        for username, credit in sorted(entry.distribution.items(), key=lambda x: -x[1]):
            print(f"  @{username}: {credit:.1f}")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Consilium - Multi-agent collaboration credit protocol",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--ledger-dir", "-d",
        default="ledger",
        help="Path to ledger directory (default: ledger)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # balance command
    balance_parser = subparsers.add_parser("balance", help="Show credit balances")
    balance_parser.add_argument("username", nargs="?", help="Show balance for specific user")
    balance_parser.add_argument("--limit", "-n", type=int, default=20, help="Number of entries to show")

    # verify command
    verify_parser = subparsers.add_parser("verify", help="Verify ledger integrity")
    verify_parser.add_argument("--github", "-g", action="store_true", help="Also verify against GitHub")
    verify_parser.add_argument("--repo", "-r", help="GitHub repo (owner/repo)")

    # rebuild command
    rebuild_parser = subparsers.add_parser("rebuild", help="Rebuild ledger from GitHub")
    rebuild_parser.add_argument("--repo", "-r", required=True, help="GitHub repo (owner/repo)")
    rebuild_parser.add_argument("--full", "-f", action="store_true", help="Full rebuild (not incremental)")

    # show command
    show_parser = subparsers.add_parser("show", help="Show a ledger entry")
    show_parser.add_argument("entry_num", type=int, help="Entry number to show")
    show_parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    commands = {
        "balance": cmd_balance,
        "verify": cmd_verify,
        "rebuild": cmd_rebuild,
        "show": cmd_show,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
