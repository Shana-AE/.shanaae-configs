// TOKENTRACKER_PLUGIN
// WSL variant: on opencode session updates, trigger a TokenTracker sync that runs
// on the Windows host (TOKENTRACKER_WSL_MODE=both) writing into
// C:\Users\shana\.tokentracker\tracker. The wrapper handles throttling and
// backgrounding so this never blocks the TUI. This file lives in the synced
// ~/.shanaae configs, so the existsSync guard makes it a silent no-op on
// machines that don't have the WSL wrapper (macOS etc.).
import { existsSync } from "node:fs";

const notifyScript = "/home/shanaae/.local/bin/tokentracker-wsl-notify.sh";

export const TokenTrackerPlugin = async ({ $ }) => {
  return {
    event: async ({ event }) => {
      if (!event || event.type !== "session.updated") return;
      try {
        if (!existsSync(notifyScript)) return;
        const proc = $`/usr/bin/env bash ${notifyScript}`.quiet();
        if (proc && typeof proc.catch === "function") proc.catch(() => {});
      } catch (_) {}
    },
  };
};