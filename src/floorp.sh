#!/bin/bash
. /app/bin/floorp-profile-root.sh
floorp_select_profile_root || exit 1
export TMPDIR=$XDG_CACHE_HOME/tmp
exec /app/lib/floorp/floorp --name one.ablaze.floorp "$@"
