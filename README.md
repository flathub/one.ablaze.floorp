# Floorp for Flatpak (one.ablaze.floorp)

Flathub: https://flathub.org/apps/one.ablaze.floorp

Browser source code: https://github.com/Floorp-Projects/Floorp

### Based on

https://github.com/flathub/org.mozilla.firefox.BaseApp

https://searchfox.org/mozilla-central/source/taskcluster/docker/firefox-flatpak

## How to install (from Flathub)
```
flatpak install flathub one.ablaze.floorp
```

## How to build
```sh
flatpak-builder build-dir one.ablaze.floorp.yml
```
To test:
```sh
flatpak-builder --run build-dir one.ablaze.floorp.yml floorp
```

## Profile selection

The launcher keeps Flatpak profiles in the application's data directory when
home-directory permission changes. Existing `MOZ_APP_DATA` overrides are kept.
If distinct legacy and XDG profile registries both exist, if a separate host
`.floorp` directory exists, or if a profile directory has data but no registry,
the launcher reports an error on standard error and leaves the data untouched.
An alias of the selected legacy or XDG directory is accepted; sharing only a
registry file between different directories is still ambiguous.
Run `flatpak run one.ablaze.floorp` in a terminal to see the paths in the error.
Back up both profile directories before resolving the ambiguity. A host profile
cannot be accessed after its home-directory permission has been removed.

To inspect one existing Flatpak profile root without merging or moving registries,
first close Floorp, back up both directories, and run one of the following in a
terminal, choosing the directory that already contains the desired `profiles.ini`:

```sh
flatpak run --env=MOZ_APP_DATA="$HOME/.var/app/one.ablaze.floorp/.floorp" one.ablaze.floorp
flatpak run --env=MOZ_APP_DATA="$HOME/.var/app/one.ablaze.floorp/config/floorp" one.ablaze.floorp
```

These are one-run overrides; they do not merge, move, or delete the other root
and do not permanently choose a root. A separate host `~/.floorp` is accessible
only while the sandbox has permission to access it. This change fixes the
profile registry root, not `MOZ_LOCAL_APP_DATA` or the separate cache directory;
cache selection and reuse across permission changes need further validation.

Run the launcher selection tests with `python3 -m unittest discover -s tests`.
`tests/profile_switch_repro.py` exercises a fresh, isolated Flatpak installation
and intentionally exits with failure when the profile switches. It uses Xvfb,
an isolated D-Bus session and timed termination, so it does not establish normal
desktop shutdown or Flatseal behavior.
