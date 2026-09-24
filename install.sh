#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd -P)"
STAMP="$(date +%Y%m%d-%H%M%S)"
MANAGED_MARKER=".skills-repo-managed"
INSTALL_CODEX=0
INSTALL_DEVIN=0
INSTALL_CLAUDE=0
SELECTED_HARNESS=0
INCLUDE_EXPERIMENTAL=0

usage() {
  cat <<'EOF'
Usage: ./install.sh [--codex] [--devin] [--claude] [--all] [--experimental]

With no harness option, install stable skills into every detected supported
harness. Codex and Devin share ~/.agents/skills. --experimental additionally
installs skills/experimental entries.
EOF
}

for argument in "$@"; do
  case "$argument" in
    --codex) INSTALL_CODEX=1; SELECTED_HARNESS=1 ;;
    --devin) INSTALL_DEVIN=1; SELECTED_HARNESS=1 ;;
    --claude) INSTALL_CLAUDE=1; SELECTED_HARNESS=1 ;;
    --all) INSTALL_CODEX=1; INSTALL_DEVIN=1; INSTALL_CLAUDE=1; SELECTED_HARNESS=1 ;;
    --experimental) INCLUDE_EXPERIMENTAL=1 ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done

is_windows_shell() {
  case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*) return 0 ;;
    *) return 1 ;;
  esac
}

normalize_absolute_path() {
  local path="$1" part normalized=""
  local -a parts
  IFS='/' read -r -a parts <<< "$path"
  for part in "${parts[@]}"; do
    case "$part" in
      ''|.) ;;
      ..) normalized="${normalized%/*}" ;;
      *) normalized="$normalized/$part" ;;
    esac
  done
  printf '%s\n' "${normalized:-/}"
}

canonicalize_path() {
  local candidate="$1" probe parent suffix="" base
  case "$candidate" in
    /*) probe="$candidate" ;;
    *) probe="$PWD/$candidate" ;;
  esac
  while [ ! -d "$probe" ]; do
    parent="$(dirname "$probe")"
    [ "$parent" != "$probe" ] || return 1
    suffix="/$(basename "$probe")$suffix"
    probe="$parent"
  done
  base="$(cd "$probe" && pwd -P)" || return 1
  normalize_absolute_path "$base$suffix"
}

path_is_within_repo() {
  local resolved
  resolved="$(canonicalize_path "$1")" || return 1
  case "$resolved" in
    "$REPO_ROOT"|"$REPO_ROOT"/*) return 0 ;;
    *) return 1 ;;
  esac
}

symlink_points_into_repo() {
  local destination="$1" target
  target="$(readlink "$destination")" || return 1
  case "$target" in
    /*) path_is_within_repo "$target" ;;
    *) path_is_within_repo "$(dirname "$destination")/$target" ;;
  esac
}

junction_points_into_repo() {
  local destination="$1" win_destination win_repo
  is_windows_shell || return 1
  win_destination="$(cygpath -w "$destination")"
  win_repo="$(cygpath -w "$REPO_ROOT")"
  SKILLS_LINK_PATH="$win_destination" SKILLS_REPO_ROOT="$win_repo" powershell.exe -NoProfile -Command '
    $item = Get-Item -LiteralPath $env:SKILLS_LINK_PATH -Force -ErrorAction Stop
    if (-not $item.LinkType -or -not $item.Target) { exit 1 }
    $target = [string]$item.Target
    if (-not [System.IO.Path]::IsPathRooted($target)) {
      $target = Join-Path $item.Parent.FullName $target
    }
    $resolved = [System.IO.Path]::GetFullPath($target)
    $separators = [char[]]@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
    $repo = [System.IO.Path]::GetFullPath($env:SKILLS_REPO_ROOT).TrimEnd($separators)
    if ($resolved.Equals($repo, [System.StringComparison]::OrdinalIgnoreCase) -or
        $resolved.StartsWith($repo + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) { exit 0 }
    exit 1
  ' >/dev/null 2>&1
}

managed_copy_points_into_repo() {
  local destination="$1" recorded candidate
  [ -f "$destination/$MANAGED_MARKER" ] || return 1
  recorded="$(cat "$destination/$MANAGED_MARKER")"
  candidate="$recorded"
  if is_windows_shell; then
    candidate="$(cygpath -u "$recorded" 2>/dev/null || printf '%s' "$recorded")"
  fi
  path_is_within_repo "$candidate"
}

windows_path_exists() {
  is_windows_shell || return 1
  local win_path
  win_path="$(cygpath -w "$1")"
  SKILLS_INSTALLED_PATH="$win_path" powershell.exe -NoProfile -Command '
    if ($null -ne (Get-Item -LiteralPath $env:SKILLS_INSTALLED_PATH -Force -ErrorAction SilentlyContinue)) { exit 0 }
    exit 1
  ' >/dev/null 2>&1
}

path_exists() {
  [ -e "$1" ] || [ -L "$1" ] || windows_path_exists "$1"
}

remove_managed_path() {
  local destination="$1"
  if junction_points_into_repo "$destination"; then
    cmd.exe //d //c rmdir "$(cygpath -w "$destination")" >/dev/null
  elif [ -L "$destination" ]; then
    rm -f "$destination"
  else
    rm -rf "$destination"
  fi
}

backup_path() {
  local destination="$1" backup="${destination}.bak-${STAMP}" suffix=1
  while path_exists "$backup"; do
    backup="${destination}.bak-${STAMP}-${suffix}"
    suffix=$((suffix + 1))
  done
  echo "Backing up existing $destination to $backup"
  mv "$destination" "$backup"
}

materialize_skill() {
  local source="$1" destination="$2" action="Linked"
  if is_windows_shell; then
    if ! cmd.exe //d //c mklink //J "$(cygpath -w "$destination")" "$(cygpath -w "$source")" >/dev/null 2>&1; then
      cp -R "$source" "$destination"
      printf '%s\n' "$source" > "$destination/$MANAGED_MARKER"
      action="Copied"
    fi
  elif ! ln -s "$source" "$destination" 2>/dev/null; then
    cp -R "$source" "$destination"
    printf '%s\n' "$source" > "$destination/$MANAGED_MARKER"
    action="Copied"
  fi
  echo "$action $destination -> $source"
  if [ "$action" = "Copied" ]; then
    echo "Warning: link creation failed; rerun the installer after repository updates." >&2
  fi
}

install_skill() {
  local source="$1" destination="$2"
  if [ -L "$destination" ] && symlink_points_into_repo "$destination"; then
    remove_managed_path "$destination"
  elif junction_points_into_repo "$destination"; then
    remove_managed_path "$destination"
  elif managed_copy_points_into_repo "$destination"; then
    remove_managed_path "$destination"
  elif path_exists "$destination"; then
    backup_path "$destination"
  fi
  mkdir -p "$(dirname "$destination")"
  materialize_skill "$source" "$destination"
}

managed_path_points_into_repo() {
  local destination="$1"
  { [ -L "$destination" ] && symlink_points_into_repo "$destination"; } ||
    junction_points_into_repo "$destination" ||
    managed_copy_points_into_repo "$destination"
}

reconcile_collection() {
  local destination_root="$1" desired_names="$2" destination name
  for destination in "$destination_root"/*; do
    path_exists "$destination" || continue
    name="${destination##*/}"
    case "$desired_names" in
      *"|$name|"*) continue ;;
    esac
    if managed_path_points_into_repo "$destination"; then
      echo "Removing repository-managed skill absent from desired set: $destination"
      remove_managed_path "$destination"
    fi
  done
}

install_collection() {
  local destination_root="$1" source name desired_names="|"
  mkdir -p "$destination_root"
  for source in "$REPO_ROOT"/skills/*; do
    [ -d "$source" ] || continue
    name="${source##*/}"
    [ "$name" = "experimental" ] && continue
    [ -f "$source/SKILL.md" ] || continue
    desired_names="${desired_names}${name}|"
  done
  if [ "$INCLUDE_EXPERIMENTAL" -eq 1 ]; then
    for source in "$REPO_ROOT"/skills/experimental/*; do
      [ -d "$source" ] || continue
      [ -f "$source/SKILL.md" ] || continue
      name="${source##*/}"
      desired_names="${desired_names}${name}|"
    done
  fi
  reconcile_collection "$destination_root" "$desired_names"
  for source in "$REPO_ROOT"/skills/*; do
    [ -d "$source" ] || continue
    name="${source##*/}"
    [ "$name" = "experimental" ] && continue
    [ -f "$source/SKILL.md" ] || continue
    install_skill "$source" "$destination_root/$name"
  done
  if [ "$INCLUDE_EXPERIMENTAL" -eq 1 ]; then
    for source in "$REPO_ROOT"/skills/experimental/*; do
      [ -d "$source" ] || continue
      [ -f "$source/SKILL.md" ] || continue
      name="${source##*/}"
      install_skill "$source" "$destination_root/$name"
    done
  fi
}

if [ "$SELECTED_HARNESS" -eq 0 ]; then
  if command -v codex >/dev/null 2>&1 || [ -d "${HOME}/.codex" ] || [ -d "${HOME}/.agents" ]; then INSTALL_CODEX=1; fi
  if command -v devin >/dev/null 2>&1 || [ -d "${HOME}/.config/devin" ]; then INSTALL_DEVIN=1; fi
  if command -v claude >/dev/null 2>&1 || [ -d "${HOME}/.claude" ]; then INSTALL_CLAUDE=1; fi
  if [ "$INSTALL_CODEX" -eq 0 ] && [ "$INSTALL_DEVIN" -eq 0 ] && [ "$INSTALL_CLAUDE" -eq 0 ]; then
    echo "No supported harness detected. Use --codex, --devin, --claude, or --all." >&2
    exit 1
  fi
fi

if [ "$INSTALL_CODEX" -eq 1 ] || [ "$INSTALL_DEVIN" -eq 1 ]; then
  install_collection "${HOME}/.agents/skills"
fi
if [ "$INSTALL_DEVIN" -eq 1 ]; then
  reconcile_collection "${HOME}/.config/devin/skills" "|"
fi
if [ "$INSTALL_CLAUDE" -eq 1 ]; then install_collection "${HOME}/.claude/skills"; fi

echo "Install complete."
