"""Giden kutusu ve yayın kapısı komutları (``python -m esham.main …``).

İş akışı (``.github/workflows/esham-schedule.yml``) sırası:
  bot koşusu (gönderim yok) → ``report-gate`` → ``commit-push`` → derleme/dağıtım →
  ``git-sync`` → ``send-outbox --ci --phase claim [--deployed-sha]`` → ``commit-push`` →
  ``send-outbox --ci --phase deliver`` → ``commit-push``.

Yerel kullanım: ``send-outbox`` varsayılan olarak KURU çalışır (yalnız listeler, dosyaya dokunmaz); gerçek
gönderim ``--send`` ister ve YALNIZ yerel koşuların kayıtlarını gönderir. İş akışıyla aynı anda kullanmayın.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

from .config import PROJECT_ROOT


def _emit(**kv) -> None:
    print(", ".join(f"{k}={v}" for k, v in kv.items()))
    out = os.getenv("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            for k, v in kv.items():
                fh.write(f"{k}={v}\n")


def cmd_send_outbox(args: argparse.Namespace) -> None:
    from .publishing.outbox import preview_outbox, send_outbox

    if not args.ci and not args.send:
        entries = preview_outbox()
        print(f"KURU ÇALIŞTIRMA: {len(entries)} yerel kayıt gönderilecekti (gerçek gönderim için --send):")
        for e in entries:
            print(f"  - {e['key']}: {e['text'][:80]!r}")
        return
    result = send_outbox(phase=args.phase, ci=args.ci, deployed_sha=args.deployed_sha or "")
    _emit(**result)


def cmd_outbox_status(_: argparse.Namespace) -> None:
    from .publishing.outbox import Outbox

    _emit(undeployed=Outbox().undeployed())


def cmd_commit_push(args: argparse.Namespace) -> None:
    from .git_sync import GitSyncError, commit_push

    try:
        result = commit_push(args.message, args.paths)
    except GitSyncError as exc:
        print(f"::error title=Push başarısız::{exc}")
        sys.exit(1)
    _emit(result=result)


def cmd_git_sync(_: argparse.Namespace) -> None:
    from .git_sync import GitSyncError, sync_with_master

    try:
        _emit(sync=sync_with_master())
    except GitSyncError as exc:
        print(f"::error title=Master ile eşitlenemedi::{exc}")
        sys.exit(1)


def _write_head_state_with_marker() -> bool:
    """Kod kırık: koşunun durum/kutu değişiklikleri atılır, master'daki sürüme işaret eklenir."""
    from .config import settings
    from .publish_gate import code_broken_marker
    from .publishing.outbox import outbox_path
    from .report_gate import git_head_content

    head = git_head_content(PROJECT_ROOT)

    def rel(p):
        return p.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()

    state_file = settings.state_file
    raw = head(rel(state_file))
    head_state = json.loads(raw.decode("utf-8")) if raw else {}
    new_state, first_today = code_broken_marker(head_state, time.strftime("%Y-%m-%d"))
    state_file.write_text(json.dumps(new_state, ensure_ascii=False, indent=2), encoding="utf-8")
    box = outbox_path()
    raw_box = head(rel(box))
    if raw_box is None:
        if box.exists():
            box.unlink()
    else:
        box.write_bytes(raw_box)
    return first_today


def cmd_report_gate(args: argparse.Namespace) -> None:
    from .publish_gate import handle_gate_failure
    from .report_gate import run_gate
    from .state import get_state

    res = run_gate(PROJECT_ROOT)
    if res.status == "code_broken":
        first_today = _write_head_state_with_marker()
        _emit(status="code_broken", excluded=0, alert="true" if first_today else "false")
        print("::error title=Kod/test kırık::Web testleri yeni raporlar OLMADAN da kırılıyor. Hiçbir rapor "
              "commit'lenmedi, Telegram'a hiçbir şey gönderilmedi, hiçbir bildirim sayacı artmadı; bildirimler "
              "sonraki koşuda yeniden denenecek. Kodu/testleri düzeltin.")
        sys.exit(3)
    state = get_state()
    state.delete("code_gate_broken")  # kapı yeniden yeşil: kod kırık işareti kalkar
    if res.status == "partial":
        r = handle_gate_failure(args.reason, res.bad_slugs)
        print(f"::error title=Kapıdan geçemeyen rapor::{len(res.bad)} rapor ayrıldı (commit'lenmedi, gönderilmedi): "
              f"{', '.join(res.bad)}. Yeniden denenecek bildirim: {len(r['retry'])}, bırakılan: {len(r['given_up'])}. "
              "Kalan raporlar yayınlanıyor.")
    _emit(status=res.status, excluded=len(res.bad), alert="false")


def register(sub) -> None:
    so = sub.add_parser("send-outbox", help="Giden kutusu: yerelde varsayılan KURU çalıştırma; --send ile gerçek gönderim")
    so.add_argument("--phase", choices=["claim", "deliver", "all"], default="all",
                    help="claim: bekleyenleri bu koşu adına işaretle (gönderme); deliver: işaretlenenleri gönder")
    so.add_argument("--send", action="store_true", help="Yerel: GERÇEKTEN gönder (yalnız yerel koşuların kayıtları)")
    so.add_argument("--ci", action="store_true", help="Yalnız iş akışı: tüm kayıtlar, dağıtım işareti zorunlu")
    so.add_argument("--deployed-sha", default="", help="Yalnız iş akışı: başarılı dağıtımın commit'i")
    so.set_defaults(func=cmd_send_outbox)

    sub.add_parser("outbox-status", help="Dağıtım bekleyen kayıt sayısı").set_defaults(func=cmd_outbox_status)

    cp = sub.add_parser("commit-push", help="İş akışı: yolları commit'le, push et (giden kutusu anahtar bazında birleşir)")
    cp.add_argument("--message", required=True)
    cp.add_argument("paths", nargs="+")
    cp.set_defaults(func=cmd_commit_push)

    sub.add_parser("git-sync", help="İş akışı: master'ın güncel ucuna eşitle").set_defaults(func=cmd_git_sync)

    rg = sub.add_parser("report-gate", help="Yayın kapısı: yeni raporları web testlerinden rapor başına geçir")
    rg.add_argument("--reason", default="web testleri kırıldı", help="failed_disclosures'a yazılacak neden")
    rg.set_defaults(func=cmd_report_gate)


CI_FUNCS = (cmd_send_outbox, cmd_outbox_status, cmd_commit_push, cmd_git_sync, cmd_report_gate)
