#!/usr/bin/env python3
"""Exercise Floorp's default profile across Flatpak home-permission changes.

Requires an isolated Flatpak user installation, Xvfb and dbus-run-session.
This deliberately creates a new HOME and never edits an existing profile.
It supports only the fresh fixture's relative default profile, not arbitrary
existing profiles or absolute paths. Exit 1 indicates the expected marker did
not remain in use. Termination is timed; it does not test normal shutdown.
"""
import configparser
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile

if len(sys.argv) not in (2, 4) or (len(sys.argv) == 4 and sys.argv[2] != "--candidate-helper"):
    sys.exit("usage: profile_switch_repro.py /path/to/isolated/XDG_DATA_HOME [--candidate-helper /path/to/helper]")
installation_data = Path(sys.argv[1]).resolve(strict=True)
candidate = Path(sys.argv[3]).resolve(strict=True) if len(sys.argv) == 4 else None
home = Path(tempfile.mkdtemp(prefix="kan8-profile-test-"))
env = dict(os.environ, HOME=str(home), XDG_DATA_HOME=str(installation_data),
           XDG_CONFIG_HOME=str(home / ".config"), XDG_CACHE_HOME=str(home / ".cache"))
appdata = home / ".var/app/one.ablaze.floorp"
if candidate:
    (appdata / "config").mkdir(parents=True)
    shutil.copyfile(candidate, appdata / "config/codex-kan8-helper.sh")

def launch(label, expose_home):
    # Request a deterministic local page in this fresh-profile fixture. The
    # blank tab is not a session-restore check or a way to disable restoration.
    args = ["dbus-run-session", "--", "xvfb-run", "-a", "timeout", "--kill-after=5s", "15s",
            "flatpak", "run", "--user", "--no-session-bus", "--no-a11y-bus"]
    if expose_home:
        args.append("--filesystem=home")
    if candidate:
        args.extend(["--command=bash", "one.ablaze.floorp", "-c",
                     'source "$XDG_CONFIG_HOME/codex-kan8-helper.sh"; '
                     'floorp_select_profile_root || exit 1; '
                     'export TMPDIR="$XDG_CACHE_HOME/tmp"; '
                     'exec /app/lib/floorp/floorp --name one.ablaze.floorp about:blank'])
    else:
        args.extend(["one.ablaze.floorp", "about:blank"])
    with (home / (label + ".log")).open("wb") as log:
        result = subprocess.run(args, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=30)
    if result.returncode != 124:
        sys.exit(f"{label}: unexpected exit {result.returncode}; see {home}")

def default_profile(registry):
    ini = configparser.ConfigParser()
    if not ini.read(registry):
        sys.exit(f"missing profile registry {registry}; logs at {home}")
    installs = [s for s in ini if s.startswith("Install") and ini[s].get("Default")]
    if len(installs) != 1:
        sys.exit(f"ambiguous install registry {registry}; logs at {home}")
    path = ini[installs[0]]["Default"]
    profiles = [ini[s] for s in ini if s.startswith("Profile") and ini[s].get("Path") == path]
    if len(profiles) != 1 or profiles[0].get("IsRelative") != "1" or Path(path).is_absolute():
        sys.exit(f"unsupported non-fixture profile path in {registry}; logs at {home}")
    return registry.parent / path

launch("baseline", False)
legacy = default_profile(appdata / ".floorp/profiles.ini")
(legacy / "user.js").write_text('user_pref("codex.kan8.marker", "baseline");\n')
launch("home-enabled", True)
alternative_registry = appdata / "config/floorp/profiles.ini"
marker = 'user_pref("codex.kan8.marker", "baseline");'
legacy_prefs = legacy / "prefs.js"
marker_with_home = legacy_prefs.exists() and marker in legacy_prefs.read_text(errors="replace")
if alternative_registry.exists():
    alternate = default_profile(alternative_registry)
    print(f"profile switched: {legacy} -> {alternate}")
else:
    print(f"no alternate registry; marker with home enabled: {marker_with_home}")
launch("home-disabled-again", False)
prefs = (legacy / "prefs.js").read_text(errors="replace")
if marker not in prefs:
    sys.exit(f"baseline marker missing after recovery; logs at {home}")
print(f"baseline marker recovered; evidence: {home}")
if alternative_registry.exists() or not marker_with_home:
    sys.exit(1)
