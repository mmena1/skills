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
harness. Codex and Devin share ~/.agents/skills. Native reviewer agents that a
selected skill ships are linked into each selected harness's agent directory.
--experimental additionally installs skills/experimental entries.
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

marker_path() {
  if [ -d "$1" ]; then
    printf '%s\n' "$1/$MANAGED_MARKER"
  else
    printf '%s\n' "$1$MANAGED_MARKER"
  fi
}

managed_copy_points_into_repo() {
  marker_points_into_repo "$(marker_path "$1")"
}

marker_points_into_repo() {
  local marker="$1" recorded candidate
  [ -f "$marker" ] || return 1
  recorded="$(cat "$marker")"
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
    cmd.exe //d //c rmdir "$(cygpath -w "$destination")" >/dev/null 2>&1 || rm -f "$destination"
  elif [ -L "$destination" ] || [ ! -d "$destination" ]; then
    rm -f "$destination"
  else
    rm -rf "$destination"
  fi
  rm -f "$destination$MANAGED_MARKER"
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

create_link() {
  local source="$1" destination="$2"
  [ "${SKILLS_INSTALLER_FORCE_COPY:-0}" != "1" ] || return 1
  if ! is_windows_shell; then
    ln -s "$source" "$destination" 2>/dev/null
  elif [ -d "$source" ]; then
    cmd.exe //d //c mklink //J "$(cygpath -w "$destination")" "$(cygpath -w "$source")" >/dev/null 2>&1
  else
    cmd.exe //d //c mklink "$(cygpath -w "$destination")" "$(cygpath -w "$source")" >/dev/null 2>&1
  fi
}

materialize_path() {
  local source="$1" destination="$2" action="Linked"
  if ! create_link "$source" "$destination"; then
    cp -R "$source" "$destination"
    printf '%s\n' "$source" > "$(marker_path "$destination")"
    action="Copied"
  fi
  echo "$action $destination -> $source"
  if [ "$action" = "Copied" ]; then
    echo "Warning: link creation failed; rerun the installer after repository updates." >&2
  fi
}

install_managed_path() {
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
  materialize_path "$source" "$destination"
}

managed_path_points_into_repo() {
  local destination="$1"
  { [ -L "$destination" ] && symlink_points_into_repo "$destination"; } ||
    junction_points_into_repo "$destination" ||
    managed_copy_points_into_repo "$destination"
}

reconcile_collection() {
  local destination_root="$1" desired_names="$2" kind="${3:-skill}" destination name
  for destination in "$destination_root"/*; do
    path_exists "$destination" || continue
    name="${destination##*/}"
    case "$name" in
      *"$MANAGED_MARKER")
        if ! path_exists "${destination%"$MANAGED_MARKER"}" && marker_points_into_repo "$destination"; then
          rm -f "$destination"
        fi
        continue
        ;;
    esac
    case "$desired_names" in
      *"|$name|"*) continue ;;
    esac
    if managed_path_points_into_repo "$destination"; then
      echo "Removing repository-managed $kind absent from desired set: $destination"
      remove_managed_path "$destination"
    fi
  done
}

# Collect selected skill directories into SELECTED_SKILLS. Plain loops keep this
# deterministic under Bash 3.2, whose nested process substitutions can drop output.
collect_selected_skills() {
  local source
  SELECTED_SKILLS=()
  for source in "$REPO_ROOT"/skills/*; do
    [ -d "$source" ] || continue
    [ "${source##*/}" = "experimental" ] && continue
    [ -f "$source/SKILL.md" ] || continue
    SELECTED_SKILLS+=("$source")
  done
  if [ "$INCLUDE_EXPERIMENTAL" -eq 1 ]; then
    for source in "$REPO_ROOT"/skills/experimental/*; do
      [ -d "$source" ] || continue
      [ -f "$source/SKILL.md" ] || continue
      SELECTED_SKILLS+=("$source")
    done
  fi
}

install_collection() {
  local destination_root="$1" source desired_names="|"
  mkdir -p "$destination_root"
  for source in ${SELECTED_SKILLS[@]+"${SELECTED_SKILLS[@]}"}; do
    desired_names="${desired_names}${source##*/}|"
  done
  reconcile_collection "$destination_root" "$desired_names"
  for source in ${SELECTED_SKILLS[@]+"${SELECTED_SKILLS[@]}"}; do
    install_managed_path "$source" "$destination_root/${source##*/}"
  done
}

# Collect into SELECTED_AGENTS the generated native reviewer agents that selected skills
# ship for one harness: Codex <name>.toml files, Devin <name>/AGENT.md directories, and
# Claude <name>.md files.
collect_selected_agents() {
  local harness="$1" skill source
  SELECTED_AGENTS=()
  for skill in ${SELECTED_SKILLS[@]+"${SELECTED_SKILLS[@]}"}; do
    for source in "$skill/harnesses/$harness"/*; do
      case "$harness:$source" in
        codex:*.toml|claude:*.md) [ -f "$source" ] || continue ;;
        devin:*) [ -f "$source/AGENT.md" ] || continue ;;
        *) continue ;;
      esac
      SELECTED_AGENTS+=("$source")
    done
  done
}

install_agents() {
  local harness="$1" destination_root="$2" source desired_names="|"
  collect_selected_agents "$harness"
  for source in ${SELECTED_AGENTS[@]+"${SELECTED_AGENTS[@]}"}; do
    desired_names="${desired_names}${source##*/}|"
  done
  if [ -d "$destination_root" ]; then
    reconcile_collection "$destination_root" "$desired_names" agent
  fi
  [ "${#SELECTED_AGENTS[@]}" -gt 0 ] || return 0
  mkdir -p "$destination_root"
  for source in "${SELECTED_AGENTS[@]}"; do
    install_managed_path "$source" "$destination_root/${source##*/}"
  done
}

devin_agents_root() {
  if is_windows_shell && [ -n "${APPDATA:-}" ]; then
    printf '%s\n' "$(cygpath -u "$APPDATA")/devin/agents"
  else
    printf '%s\n' "${HOME}/.config/devin/agents"
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

collect_selected_skills
if [ "$INSTALL_CODEX" -eq 1 ] || [ "$INSTALL_DEVIN" -eq 1 ]; then
  install_collection "${HOME}/.agents/skills"
fi
if [ "$INSTALL_DEVIN" -eq 1 ]; then
  reconcile_collection "${HOME}/.config/devin/skills" "|"
fi
if [ "$INSTALL_CLAUDE" -eq 1 ]; then install_collection "${HOME}/.claude/skills"; fi
if [ "$INSTALL_CODEX" -eq 1 ]; then install_agents codex "${HOME}/.codex/agents"; fi
if [ "$INSTALL_DEVIN" -eq 1 ]; then install_agents devin "$(devin_agents_root)"; fi
if [ "$INSTALL_CLAUDE" -eq 1 ]; then install_agents claude "${HOME}/.claude/agents"; fi

echo "Install complete."
