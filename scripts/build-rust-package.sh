#!/usr/bin/env bash
set -e

function announce() {
    echo "================================================================================"
    echo "$@"
    echo "================================================================================"
}

# go to the root of the repo
cd $(dirname $(readlink -f $0))/..

# build with colcon and source
announce "Building and sourcing colcon-cargo"
colcon build
source install/setup.sh

# now build a sample rust package
announce "Building and sourcing sample Ruts app"
cd test/rust-sample-package
colcon build
source install/setup.sh

# is the rust package properly installed?
output=$(app 2>&1)
[[ "$output"=="Hello, world!" ]] || {
    echo "Didn't get the expected output."
    echo "Output:  $output"
}
