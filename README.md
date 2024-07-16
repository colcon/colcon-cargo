# colcon-cargo

[![CI](https://github.com/colcon/colcon-cargo/actions/workflows/ci.yaml/badge.svg?branch=main&event=push)](https://github.com/colcon/colcon-cargo/actions/workflows/ci.yaml?query=branch%3Amain+event%3Apush)

An extension for [colcon-core](https://github.com/colcon/colcon-core) to
support Rust projects built with Cargo.

## Install
```sh
$ pip3 install --user --upgrade git+https://github.com/colcon/colcon-cargo.git
```

## Usage / Minimal example

<details>
<summary>Build a sample workspace</summary>
<br>

```sh
$ mkdir ws/
$ cd ws/
$ cargo init hello_world
$ cargo init hello_world2
$ tree .

.
├── hello-world
│   ├── Cargo.toml
│   └── src
│       └── main.rs
└── hello-world2
    ├── Cargo.toml
    └── src
        └── main.rs

4 directories, 4 files

```

</details>

Verify that cargo detects the Rust packages:

```sh
$ colcon list

hello-world     hello-world     (cargo)
hello-world2    hello-world2    (cargo)
```

Build them with Cargo:

```sh
$ colcon build

Starting >>> hello_world
Starting >>> hello_world_2
Finished <<< hello_world_2 [1.84s]
Finished <<< hello_world [1.94s]

Summary: 2 packages finished [2.34s]
```

Source the generated `install/` directory and execute:

```sh
$ source install/setup.bash
$ hello-world

Hello, world!

$ hello-world2

Hello, world!
```

### Testing

Test the packages with cargo:

```sh
$ colcon test
Starting >>> hello_world_2
Starting >>> hello_world
Finished <<< hello_world [0.24s]                                           
Finished <<< hello_world_2 [0.25s]

Summary: 2 packages finished [0.39s]
```

Inspect the test results (`cargo test` and `cargo fmt --check`).
They should all succeed for the empty templates:

```sh
$ colcon test-result --all
build/hello_world_2/cargo_test.xml: 2 tests, 0 errors, 0 failures, 0 skipped
build/hello_world/cargo_test.xml: 2 tests, 0 errors, 0 failures, 0 skipped

Summary: 4 tests, 0 errors, 0 failures, 0 skipped
```
