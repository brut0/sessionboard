#!/usr/bin/env sh
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOOK="$ROOT/.git/hooks/pre-commit"
mkdir -p "$(dirname "$HOOK")"
cat > "$HOOK" <<'EOF'
#!/usr/bin/env sh
set -eu
python scripts/check_repo_hygiene.py
EOF
chmod +x "$HOOK"
echo "Installed pre-commit hook at $HOOK"
