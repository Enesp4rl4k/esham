#!/usr/bin/env bash
# Kullanım: commit-push.sh "<commit mesajı>" <yol>...
# Verilen yolları (varsa) sahneler; değişiklik varsa commit'ler ve master'a push eder.
# Eşzamanlı push yarışı için 3 deneme (pull --rebase, sonra push). Çıkış: 0 = push edildi ya da değişiklik yok,
# 1 = push başarısız (çağıran adım iş akışını kırmızıya çevirir ve Telegram'a HİÇBİR ŞEY göndermez).
# Çıktı: değişiklik varsa ve push edildiyse stdout'a "pushed", değişiklik yoksa "clean".
set -u
# rebase/autostash da kimlik ister (eski adım git config user.* yapıyordu); depoya yazmadan ortamla verilir.
export GIT_AUTHOR_NAME="esham-bot" GIT_AUTHOR_EMAIL="bot@esham.local"
export GIT_COMMITTER_NAME="esham-bot" GIT_COMMITTER_EMAIL="bot@esham.local"
msg="$1"; shift
for p in "$@"; do
  if [[ -e "$p" ]]; then git add -- "$p"; fi
done
if git diff --staged --quiet; then
  echo "clean"
  exit 0
fi
git commit -q -m "$msg" >&2
for i in 1 2 3; do
  # --autostash: sahnelenmemiş üretim dosyaları (ör. kapı kırıldığında commit'lenmeyen raporlar) rebase'i engellemesin.
  # -X theirs: rebase sırasında "theirs" = bu koşunun commit'i (iş akışı eşzamanlılık grubuyla tek koşu).
  if git pull -q --rebase --autostash -X theirs origin master >&2 && git push -q origin HEAD:master >&2; then
    echo "pushed"
    exit 0
  fi
  git rebase --abort 2>/dev/null || true
  sleep $((i * 5))
done
exit 1
