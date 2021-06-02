# colcon-cargo

[![CI](https://github.com/colcon/colcon-cargo/actions/workflows/ci.yml/badge.svg)](https://github.com/colcon/colcon-cargo/actions/workflows/ci.yml)

An extension for [colcon-core](https://github.com/colcon/colcon-core) to
support Rust projects built with Cargo.

## Basic Set Up
This introduction assumes the following dependencies are already installed:
- python >= 3.5
- rust/cargo are installed
- colcon (comes with ros2 core distribution)

#### Install colcon_cargo
`pip install -U git+https://github.com/colcon/colcon-cargo.git`
#### Create two cargo crates
Navigate to a workspace where you want to start creating packages and run the following commands:
```
cargo new hello_world
cargo new hello_world_2
```

#### Build with colcon
```colcon build```

You should get output that looks like this:
```
Starting >>> hello_world
Starting >>> hello_world_2
Finished <<< hello_world_2 [1.84s]
Finished <<< hello_world [1.94s]

Summary: 2 packages finished [2.34s]
```