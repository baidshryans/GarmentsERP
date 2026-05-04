"""
Reversal and point-in-time restore engine.

Two operations are exposed:

  reverse_transaction(history_transaction_id, dry_run=False)
      Undo every change that was written during one HTTP request (i.e.
      every historical row that shares the same history_transaction_id).
      Restores the previous state of each affected row, atomically.

  restore_to_point(timestamp, retail, scope='all', dry_run=False)
      For each tracked model in `scope`, walk its historical table and
      bring every live row back to the latest snapshot at or before the
      given timestamp. Live rows that were created after the timestamp
      are deleted.

Both operations:
  - run inside a single transaction.atomic() so a failure rolls back
    everything cleanly
  - record a dry-run summary (counts of would-be-modified rows) without
    committing when dry_run=True
  - tag the new historical rows they themselves create with a
    history_change_reason describing the reversal/restore for full
    auditability
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import List

from django.db import transaction
from django.utils.timezone import now as tz_now

from .history_query import get_tracked_models


@dataclass
class RestoreSummary:
    creates: int = 0   # live rows that will be re-created (i.e. they were deleted)
    updates: int = 0   # live rows that will be modified back
    deletes: int = 0   # live rows that will be removed (they were added later)
    blocked: List[str] = field(default_factory=list)   # human-readable reasons for skipped operations
    affected_models: List[str] = field(default_factory=list)

    def as_dict(self):
        return {
            'creates': self.creates,
            'updates': self.updates,
            'deletes': self.deletes,
            'total_changes': self.creates + self.updates + self.deletes,
            'blocked': self.blocked,
            'affected_models': self.affected_models,
        }


# ── Mode 1: reverse a single transaction ─────────────────────────────────────

def reverse_transaction(history_transaction_id, dry_run=False, change_reason_prefix='Reversal'):
    """Undo every historical row tagged with this transaction UUID.

    Algorithm per affected (live_model, live_pk):
      - find the historical row that bears this history_transaction_id
      - find the historical row immediately *before* that one (the prior state)
      - if event was CREATE  (+) → delete the live row
      - if event was UPDATE  (~) → save the prior state back to the live row
      - if event was DELETE  (-) → recreate the live row from the prior state
    """
    summary = RestoreSummary()
    rebuild_plan = defaultdict(list)   # {(live_model, pk): [target_history_row]}

    # 1. Discover the affected rows across every tracked model
    for live_model, historical_model in get_tracked_models():
        if not hasattr(historical_model, 'history_transaction_id'):
            continue

        rows = historical_model.objects.filter(
            history_transaction_id=history_transaction_id
        ).order_by('history_date')
        for r in rows:
            rebuild_plan[(live_model, r.id)].append(r)
            label = f"{live_model._meta.app_label}.{live_model._meta.model_name}"
            if label not in summary.affected_models:
                summary.affected_models.append(label)

    if not rebuild_plan:
        summary.blocked.append(f"No historical rows found for transaction {history_transaction_id}")
        return summary

    # 2. Plan + apply
    with transaction.atomic():
        for (live_model, pk), txn_rows in rebuild_plan.items():
            # The latest history row in this txn represents the post-txn state
            latest_in_txn = txn_rows[-1]
            historical_model = type(latest_in_txn)

            # Find the prior state — newest historical row strictly before this txn
            prior = (
                historical_model.objects
                .filter(id=pk, history_date__lt=latest_in_txn.history_date)
                .exclude(history_transaction_id=history_transaction_id)
                .order_by('-history_date')
                .first()
            )

            if latest_in_txn.history_type == '+':
                # Created in this txn — undo by deleting the live row (if it still exists)
                live_qs = live_model.objects.filter(pk=pk)
                if live_qs.exists():
                    if not dry_run:
                        instance = live_qs.first()
                        # Set change reason on the historical row that the delete will produce
                        instance._change_reason = f"{change_reason_prefix} of {history_transaction_id}"
                        instance.delete()
                    summary.deletes += 1
            elif latest_in_txn.history_type == '~':
                # Updated in this txn — restore the prior snapshot
                if prior is None:
                    summary.blocked.append(
                        f"No prior state for {live_model.__name__} pk={pk} — cannot revert update"
                    )
                    continue
                if not dry_run:
                    inst = prior.instance
                    inst._change_reason = f"{change_reason_prefix} of {history_transaction_id}"
                    inst.save()
                summary.updates += 1
            elif latest_in_txn.history_type == '-':
                # Deleted in this txn — recreate from the prior snapshot
                if prior is None:
                    summary.blocked.append(
                        f"No prior state for {live_model.__name__} pk={pk} — cannot recreate"
                    )
                    continue
                if not dry_run:
                    inst = prior.instance
                    inst._change_reason = f"{change_reason_prefix} of {history_transaction_id}"
                    inst.save()
                summary.creates += 1

        if dry_run:
            transaction.set_rollback(True)

    return summary


# ── Mode 2: system-wide restore to a point in time ───────────────────────────

def restore_to_point(timestamp, retail=None, scope='all', dry_run=False):
    """Roll all tracked rows back to their state at `timestamp`.

    For each tracked model:
      - walk every distinct id whose history overlaps the timestamp
      - take the latest historical row with history_date <= timestamp
      - if the live row exists and differs → restore it
      - if a live row exists but its earliest history is > timestamp → delete it
        (it didn't exist at `timestamp`)
      - if no live row exists but there's a historical row <= timestamp →
        recreate it
    """
    summary = RestoreSummary()
    change_reason = f"Restore to {timestamp.isoformat() if hasattr(timestamp, 'isoformat') else timestamp}"

    with transaction.atomic():
        for live_model, historical_model in get_tracked_models():
            if scope != 'all' and live_model._meta.label not in scope:
                continue

            # Optional retail scope filter
            base_hist = historical_model.objects.all()
            if retail is not None and hasattr(historical_model, 'history_retail_id'):
                base_hist = base_hist.filter(history_retail=retail)

            # All distinct live PKs that ever appeared in this model's history
            distinct_ids = list(base_hist.values_list('id', flat=True).distinct())
            if not distinct_ids:
                continue

            label = f"{live_model._meta.app_label}.{live_model._meta.model_name}"
            if label not in summary.affected_models:
                summary.affected_models.append(label)

            for pk in distinct_ids:
                snapshots = base_hist.filter(id=pk).order_by('history_date')
                snapshot_at_or_before = snapshots.filter(
                    history_date__lte=timestamp
                ).last()

                live = live_model.objects.filter(pk=pk).first()

                if snapshot_at_or_before is None:
                    # The row didn't exist at `timestamp`; if it exists live now, kill it
                    if live is not None:
                        if not dry_run:
                            live._change_reason = change_reason
                            live.delete()
                        summary.deletes += 1
                    continue

                if snapshot_at_or_before.history_type == '-':
                    # Last action at/before timestamp was a delete — should not exist live
                    if live is not None:
                        if not dry_run:
                            live._change_reason = change_reason
                            live.delete()
                        summary.deletes += 1
                    continue

                # Snapshot says the row existed → either restore or create
                if live is None:
                    if not dry_run:
                        inst = snapshot_at_or_before.instance
                        inst._change_reason = change_reason
                        inst.save()
                    summary.creates += 1
                else:
                    if not dry_run:
                        inst = snapshot_at_or_before.instance
                        inst._change_reason = change_reason
                        inst.save()
                    summary.updates += 1

        if dry_run:
            transaction.set_rollback(True)

    return summary
