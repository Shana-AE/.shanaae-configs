# oc-upgrade — upgrade opencode without hitting the anonymous GitHub API.
# Workaround for https://github.com/anomalyco/opencode/issues/36260
# (opencode upgrade ignores GITHUB_TOKEN and 403s on the /releases/latest call).
#
# Discover the latest tag by following the /releases/latest web redirect
# (no auth, no REST-API rate limit), validate it, then delegate to opencode's
# own official `opencode upgrade <tag>` logic. gh used only as a fallback.
oc-upgrade() {
  emulate -L zsh
  local tag=""
  tag=$(curl -fsSL -o /dev/null -w '%{url_effective}' \
    https://github.com/anomalyco/opencode/releases/latest 2>/dev/null)
  tag="${tag##*/}"
  [[ "$tag" =~ ^v?[0-9]+\.[0-9]+\.[0-9]+$ ]] || tag=""
  if [[ -z "$tag" ]] && command -v gh >/dev/null 2>&1; then
    tag=$(gh release view --repo anomalyco/opencode --json tagName -q .tagName 2>/dev/null)
  fi
  if [[ -z "$tag" ]]; then
    print -u2 "oc-upgrade: could not determine latest version (redirect and gh both failed)."
    return 1
  fi
  print "Latest: $tag  (current: $(opencode --version 2>/dev/null || echo '?'))"
  opencode upgrade "$tag" "$@"
}
